"""Node-free regressions for the small transaction-correctness fixes.

Covers:
- bumpfee reduces the change output, not whatever index the loop ended on
- missing change descriptor is derived from the receive descriptor
- transaction output dicts resolve addresses / OP_RETURN labels
- explorer broadcasts only clear pending state on a matching txid
- the "recipient amount reduced" warning survives PSBT serialization
"""

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from embit import bip32, networks, script
from embit.descriptor import Descriptor
from embit.psbt import PSBT
from embit.script import Script
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from flask import Flask
from jinja2 import Environment

from cryptoadvance.specter.util.psbt import SpecterPSBT, SpecterTx
from cryptoadvance.specter.wallet.wallet import Wallet

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src/cryptoadvance/specter/templates"

NET = networks.NETWORKS["regtest"]
HD_ROOT = bip32.HDKey.from_seed(b"\x11" * 32)
RECV_DESC = f"wpkh({HD_ROOT.to_public().to_string()}/0/*)"
DESCRIPTOR = Descriptor.from_string(RECV_DESC)


def make_pending_psbt():
    """A pending hot-wallet style PSBT paying 900 sats out of a 1000 sat UTXO."""
    tx = Transaction(
        vin=[TransactionInput(b"\x01" * 32, 0)],
        vout=[TransactionOutput(900, DESCRIPTOR.derive(1).script_pubkey())],
    )
    psbt = PSBT(tx)
    psbt.inputs[0].witness_utxo = TransactionOutput(
        1000, DESCRIPTOR.derive(0).script_pubkey()
    )
    return SpecterPSBT(psbt, DESCRIPTOR, NET)


def explorer_app():
    flask_app = Flask(__name__)
    flask_app.secret_key = "test"
    flask_app.csrf = SimpleNamespace(exempt=lambda f: f)
    with flask_app.app_context():
        api = import_module(
            "cryptoadvance.specter.server_endpoints.wallets.wallets_api"
        )
    wallet = MagicMock()
    wallet.rpc.testmempoolaccept.return_value = [{"allowed": True}]
    session = MagicMock()
    flask_app.specter = SimpleNamespace(
        wallet_manager=SimpleNamespace(get_by_alias=lambda alias: wallet),
        chain="main",
        requests_session=lambda force_tor: session,
    )
    flask_app.config["EXPLORERS_LIST"] = {
        "MEMPOOL_SPACE": {"url": "https://example.org/"}
    }
    return flask_app, api, wallet, session


def call_explorer_broadcast(flask_app, api, tx="deadbeef"):
    with flask_app.test_request_context(
        "/wallet/w/broadcast_blockexplorer/",
        method="POST",
        data={"tx": tx, "explorer": "mempool", "use_tor": "false"},
    ):
        with patch.object(api, "_", side_effect=lambda message: message):
            return api.broadcast_blockexplorer.__wrapped__("w").get_json()


@pytest.mark.parametrize(
    "status,body,expected_txid",
    [
        (400, "rejected by explorer", "a" * 64),
        (200, "not-a-txid", "a" * 64),
        (200, "a" * 64, "b" * 64),
    ],
)
def test_explorer_broadcast_failure_keeps_pending_psbts(status, body, expected_txid):
    flask_app, api, wallet, session = explorer_app()
    session.post.return_value = MagicMock(status_code=status, text=body)
    wallet.rpc.decoderawtransaction.return_value = {"txid": expected_txid}

    result = call_explorer_broadcast(flask_app, api)

    assert result["success"] is False
    assert body not in result["error"]
    wallet.delete_spent_pending_psbts.assert_not_called()


def test_explorer_broadcast_html_response_is_not_reflected():
    flask_app, api, wallet, session = explorer_app()
    payload = '<img src=x onerror="alert(1)">'
    session.post.return_value = MagicMock(status_code=400, text=payload)
    wallet.rpc.decoderawtransaction.return_value = {"txid": "a" * 64}

    result = call_explorer_broadcast(flask_app, api)

    assert result["success"] is False
    assert "400" in result["error"]
    assert payload not in result["error"]
    assert "<" not in result["error"]
    wallet.delete_spent_pending_psbts.assert_not_called()


def test_explorer_exception_html_is_not_reflected():
    flask_app, api, wallet, session = explorer_app()
    payload = '<img src=x onerror="alert(1)">'
    session.post.side_effect = RuntimeError(payload)

    with patch.object(api, "handle_exception"):
        result = call_explorer_broadcast(flask_app, api)

    assert result["success"] is False
    assert payload not in result["error"]
    assert "<" not in result["error"]
    wallet.delete_spent_pending_psbts.assert_not_called()


def test_explorer_broadcast_matching_txid_clears_pending_psbts():
    flask_app, api, wallet, session = explorer_app()
    session.post.return_value = MagicMock(status_code=200, text="a" * 64 + "\n")
    wallet.rpc.decoderawtransaction.return_value = {"txid": "A" * 64}

    result = call_explorer_broadcast(flask_app, api)

    assert result["success"] is True
    wallet.delete_spent_pending_psbts.assert_called_once_with(["deadbeef"])


def make_rbf_wallet(output_values, change_flags, fee=100, size=100):
    wallet = Wallet.__new__(Wallet)
    outputs = [SimpleNamespace(value=value) for value in output_values]
    scopes = [SimpleNamespace(is_change=flag) for flag in change_flags]
    psbt = SimpleNamespace(
        outputs=scopes,
        psbt=SimpleNamespace(outputs=outputs),
        fee=fee,
        full_size=size,
        to_dict=MagicMock(return_value={"fee_rate": 10}),
    )
    wallet.psbt_from_txid = MagicMock(return_value=psbt)
    wallet.save_pending_psbt = MagicMock()
    return wallet, psbt


# fee_delta = fee_rate * full_size - fee = 10 * 100 - 100 = 900
@pytest.mark.parametrize(
    "values,flags,expected",
    [
        ([5000, 2000], [True, False], [4100, 2000]),
        ([2000, 5000, 2000], [False, True, False], [2000, 4100, 2000]),
    ],
)
def test_bumpfee_reduces_change_output_not_last_output(values, flags, expected):
    wallet, psbt = make_rbf_wallet(values, flags)

    result = wallet.bumpfee("txid", 10)

    assert [out.value for out in psbt.psbt.outputs] == expected
    assert not result.get("recipient_amount_reduced")
    assert psbt.recipient_amount_reduced is False
    wallet.save_pending_psbt.assert_called_once_with(psbt)


def test_bumpfee_without_change_flags_reduced_recipient_amount():
    wallet, psbt = make_rbf_wallet([2000], [False])

    wallet.bumpfee("txid", 10)

    assert psbt.psbt.outputs[0].value == 1100
    assert psbt.recipient_amount_reduced is True


def test_missing_change_descriptor_is_derived_from_receive_descriptor():
    receive = RECV_DESC + "#deadbeef"
    assert Wallet.merge_descriptors(receive, None) == RECV_DESC.replace(
        "/0/*", "/{0,1}/*"
    )


def test_output_dict_resolves_addresses_and_op_return():
    address = DESCRIPTOR.derive(3).address(NET)
    payment = TransactionOutput(1000, script.address_to_scriptpubkey(address))
    op_return = TransactionOutput(0, Script(b"\x6a\x01\x01"))
    tx = SpecterTx(SimpleNamespace(network=NET), Transaction(vout=[payment, op_return]))

    outputs = tx.to_dict()["vout"]

    assert outputs[0]["scriptPubKey"]["addresses"] == [address]
    assert outputs[1]["scriptPubKey"]["addresses"] == ["OP_RETURN 6a0101"]


def test_recipient_reduction_warning_survives_pending_psbt_round_trip():
    pending = make_pending_psbt()
    pending.recipient_amount_reduced = True

    stored = pending.to_dict()
    assert stored["recipient_amount_reduced"] is True

    reopened = SpecterPSBT.from_dict(stored, DESCRIPTOR, NET)
    assert reopened.recipient_amount_reduced is True
    assert reopened.to_dict()["recipient_amount_reduced"] is True


def test_no_warning_flag_for_ordinary_transactions():
    stored = make_pending_psbt().to_dict()
    assert "recipient_amount_reduced" not in stored
    assert (
        SpecterPSBT.from_dict(stored, DESCRIPTOR, NET).recipient_amount_reduced is False
    )


def test_sign_page_renders_persisted_recipient_reduction_warning():
    source = (TEMPLATES / "wallet/send/sign/wallet_send_sign_psbt.jinja").read_text()
    block = source.split('<div class="tx_info">', 1)[1].split(
        "{% for i in range(psbt['address']|length) %}", 1
    )[0]
    render = Environment().from_string(block).render

    warning = "reduces the recipient's payment"
    assert warning in render(
        psbt={"recipient_amount_reduced": True}, _=lambda text: text
    )
    assert warning not in render(psbt={}, _=lambda text: text)
