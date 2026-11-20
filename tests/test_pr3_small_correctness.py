"""Node-free regressions for explorer broadcasts and transaction display paths."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from importlib import import_module

import pytest
from embit import networks, script
from embit.transaction import Transaction, TransactionOutput
from flask import Flask

from cryptoadvance.specter.commands.psbt_creator import PsbtCreator
from cryptoadvance.specter.util.psbt import SpecterTx
from cryptoadvance.specter.wallet.wallet import Wallet


@pytest.mark.parametrize("unit,amount", [("sat", 0.00001), ("btc", 1.0)])
def test_liquid_text_batch_uses_default_asset(unit, amount):
    specter = SimpleNamespace(is_liquid=True, default_asset="ab" * 32)
    creator = PsbtCreator(
        specter,
        MagicMock(),
        "text",
        request_form={"fee_option": "manual", "fee_rate": "1"},
        recipients_txt=f"address,{'1000' if unit == 'sat' else '1'}",
        recipients_amount_unit=unit,
    )
    assert creator.amounts == [amount]
    assert creator.kwargs["assets"] == [specter.default_asset]


def test_vout_dict_contains_address_and_op_return():
    address = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    output = TransactionOutput(1000, script.address_to_scriptpubkey(address))
    op_return = TransactionOutput(0, script.Script(b"\x6a\x01\x01"))
    tx = SpecterTx(
        SimpleNamespace(network=networks.NETWORKS["main"]),
        Transaction(vout=[output, op_return]),
    )
    outputs = tx.to_dict()["vout"]
    assert outputs[0]["scriptPubKey"]["addresses"] == [address]
    assert outputs[1]["scriptPubKey"]["addresses"] == ["OP_RETURN 6a0101"]


def test_subtract_fee_updates_selected_recipient_not_first():
    creator = PsbtCreator(
        SimpleNamespace(is_liquid=False),
        MagicMock(),
        "text",
        request_form={
            "fee_option": "manual",
            "fee_rate": "1",
            "subtract": "true",
            "subtract_from": "1",
        },
        recipients_txt="first,1\nsecond,2",
        recipients_amount_unit="btc",
    )
    wallet = MagicMock()
    wallet.createpsbt.return_value.to_dict.return_value = {
        "tx": {
            "vout": [
                {"value": 1, "scriptPubKey": {"addresses": ["first"]}},
                {"value": 1.999, "scriptPubKey": {"addresses": ["second"]}},
            ]
        }
    }
    creator.create_psbt(wallet)
    assert creator.amounts == [1, 1.999]


def test_missing_change_descriptor_is_derived_from_receive_descriptor():
    receive = "wpkh([00000000/84h/0h/0h]xpub661MyMwAqRbcFfake/0/*)#oldchecksum"
    with patch.object(Wallet.DescriptorCls, "from_string", return_value=object()):
        assert Wallet.merge_descriptors(receive, None) == receive.split("#")[0].replace(
            "/0/*", "/{0,1}/*"
        )


def explorer_app():
    flask_app = Flask(__name__)
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


@pytest.mark.parametrize(
    "status,body", [(400, "rejected by explorer"), (200, "not-a-txid")]
)
def test_explorer_rejection_keeps_pending_psbts(status, body):
    flask_app, wallets_api, wallet, session = explorer_app()
    session.post.return_value = MagicMock(status_code=status, text=body)
    with flask_app.test_request_context(
        "/wallet/w/broadcast_blockexplorer/",
        method="POST",
        data={"tx": "deadbeef", "explorer": "mempool", "use_tor": "false"},
    ):
        with patch.object(wallets_api, "_", side_effect=lambda message: message):
            result = wallets_api.broadcast_blockexplorer.__wrapped__("w").get_json()
    assert result["success"] is False
    assert body in result["error"]
    wallet.delete_spent_pending_psbts.assert_not_called()


def test_successful_explorer_broadcast_clears_pending_psbts():
    flask_app, wallets_api, wallet, session = explorer_app()
    session.post.return_value = MagicMock(status_code=200, text="a" * 64)
    with flask_app.test_request_context(
        "/wallet/w/broadcast_blockexplorer/",
        method="POST",
        data={"tx": "deadbeef", "explorer": "mempool", "use_tor": "false"},
    ):
        result = wallets_api.broadcast_blockexplorer.__wrapped__("w").get_json()
    assert result["success"] is True
    wallet.delete_spent_pending_psbts.assert_called_once_with(["deadbeef"])
