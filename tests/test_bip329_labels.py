import json
import logging
import threading
from types import MethodType
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from embit import ec
from embit import script
from embit.liquid.addresses import address as liquid_address
from embit.liquid.addresses import to_unconfidential
from embit.liquid.networks import NETWORKS
from embit.liquid.transaction import LTransaction, LTransactionInput, LTransactionOutput
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from flask import Flask, url_for

from cryptoadvance.specter.liquid.addresslist import LAddress, LAddressList
from cryptoadvance.specter.liquid.wallet import LWallet
from cryptoadvance.specter.server_endpoints.wallets import wallets as wallets_module
from cryptoadvance.specter.server_endpoints.wallets.wallets import (
    settings_importaddresslabels,
    settings_exportbip329labels,
)
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import bip329
from cryptoadvance.specter.wallet.addresslist import Address, AddressList
from cryptoadvance.specter.wallet.bip329 import parse_bip329_jsonl
from cryptoadvance.specter.wallet.wallet import FrozenStateConflictError, Wallet


ADDRESS_A = "bc1q34aq5drpuwy3wgl9lhup9892qp6svr8ldzyy7c"
ADDRESS_B = "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
UNKNOWN_ADDRESS = "bc1q9e8t4v8z6y6w2k4q5m8v7y3u2s5d4f3g2h1j0k"
TXID_A = "01" * 32
TXID_B = "02" * 32
TXID_C = "03" * 32


class StubAddressList(dict):
    get_labels = AddressList.get_labels

    def set_labels(self, values):
        for value in values:
            if value["address"] in self:
                self[value["address"]].set_label(value["label"])


class StubWallet(Wallet):
    @property
    def rpc(self):
        return self._rpc

    def check_utxo(self):
        self.check_utxo_calls += 1
        if self.refreshed_utxos is not None:
            self._full_utxo = list(self.refreshed_utxos)

    @property
    def recv_descriptor(self):
        return "recv-descriptor"

    @property
    def change_descriptor(self):
        return "change-descriptor"

    @property
    def devices(self):
        return []

    @property
    def blockheight(self):
        return 100


class StubLiquidWallet(LWallet, StubWallet):
    pass


def make_address(address, index, label=None, change=False):
    return Address(
        MagicMock(),
        address=address,
        index=index,
        change=change,
        label=label,
        used=True,
        service_id=None,
    )


def make_wallet(addresses, utxos=None, frozen=None, wallet_cls=StubWallet):
    wallet = wallet_cls.__new__(wallet_cls)
    wallet._addresses = StubAddressList(
        {address.address: address for address in addresses}
    )
    wallet._transactions = {}
    wallet._full_utxo = list(utxos or [])
    wallet.refreshed_utxos = None
    wallet.check_utxo_calls = 0
    wallet._utxo_state_lock = threading.RLock()
    wallet.frozen_utxo = list(frozen or [])
    wallet.pending_psbts = {}
    wallet.core_locked_outpoints = {
        f"{utxo['txid']}:{utxo['vout']}" for utxo in (utxos or []) if utxo.get("locked")
    }
    wallet.lockunspent_error = None
    wallet._rpc = MagicMock()

    def listlockunspent():
        return [
            {"txid": outpoint.split(":")[0], "vout": int(outpoint.split(":")[1])}
            for outpoint in sorted(wallet.core_locked_outpoints)
        ]

    def lockunspent(unlock, outputs):
        if wallet.lockunspent_error is not None:
            raise wallet.lockunspent_error
        for output in outputs:
            outpoint = f"{output['txid']}:{output['vout']}"
            if unlock:
                wallet.core_locked_outpoints.discard(outpoint)
            else:
                wallet.core_locked_outpoints.add(outpoint)
        return True

    wallet._rpc.listlockunspent.side_effect = listlockunspent
    wallet._rpc.lockunspent.side_effect = lockunspent
    wallet.commit_calls = 0
    wallet.commit_error = None

    def persist_wallet_file(self):
        self.commit_calls += 1
        if self.commit_error is not None:
            raise self.commit_error

    wallet._persist_wallet_file = MethodType(persist_wallet_file, wallet)
    wallet.fullpath = "unused-wallet.json"
    wallet.update_balance = MagicMock()
    wallet.name = "Savings Wallet"
    wallet.alias = "savings_wallet"
    wallet.description = ""
    wallet.address_type = "bech32"
    wallet.address = ADDRESS_A
    wallet.address_index = 0
    wallet.change_address = ADDRESS_B
    wallet.change_index = 0
    wallet.keypool = 20
    wallet.change_keypool = 20
    wallet.keys = []
    wallet.sigs_required = 1

    return wallet


def parse_export(wallet):
    exported = wallet.export_bip329_labels()
    assert exported.endswith("\n") or exported == ""
    return [json.loads(line) for line in exported.splitlines()]


def test_legacy_export_is_unchanged():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 3, "Alice"), make_address(ADDRESS_B, 4, "Exchange")]
    )

    assert wallet.export_labels() == {
        "Alice": [ADDRESS_A],
        "Exchange": [ADDRESS_B],
    }
    assert wallet.to_json(for_export=True)["labels"] == {
        "Alice": [ADDRESS_A],
        "Exchange": [ADDRESS_B],
    }
    assert parse_export(wallet) == [
        {"type": "addr", "ref": ADDRESS_A, "label": "Alice"},
        {"type": "addr", "ref": ADDRESS_B, "label": "Exchange"},
    ]


def test_generated_display_labels_are_not_exported():
    receiving = make_address(ADDRESS_A, 4)
    change = make_address(ADDRESS_B, 8, change=True)
    wallet = make_wallet([receiving, change])

    assert receiving.label == "Address #4"
    assert change.label == "Change #8"
    assert wallet.export_labels() == {}
    assert wallet.export_bip329_labels() == ""


def test_export_labeled_and_frozen_outputs_as_deterministic_jsonl():
    label = 'München – Rücklage ₿ "quoted" \\ path\nnext'
    frozen_unlabeled = f"{TXID_C}:2"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0, label), make_address(ADDRESS_B, 8, change=True)],
        utxos=[
            {"txid": TXID_B, "vout": 1, "address": ADDRESS_A, "label": "ignored"},
            {"txid": TXID_A, "vout": 0, "address": ADDRESS_A},
            {"txid": TXID_C, "vout": 2, "address": ADDRESS_B},
        ],
        frozen=[f"{TXID_B}:1", frozen_unlabeled],
    )

    records = parse_export(wallet)

    assert records == [
        {"type": "addr", "ref": ADDRESS_A, "label": label},
        {"type": "output", "ref": f"{TXID_A}:0", "label": label},
        {
            "type": "output",
            "ref": f"{TXID_B}:1",
            "label": label,
            "spendable": False,
        },
        {"type": "output", "ref": frozen_unlabeled, "spendable": False},
    ]
    assert "München – Rücklage ₿" in wallet.export_bip329_labels()
    assert "Change #8" not in wallet.export_bip329_labels()


def test_bip329_export_snapshot_blocks_concurrent_freeze():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0, "Alice")],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    export_refreshed_utxos = threading.Event()
    allow_export_to_finish = threading.Event()
    freeze_started = threading.Event()
    freeze_reached_core = threading.Event()
    original_check_utxo = wallet.check_utxo
    original_listlockunspent = wallet._rpc.listlockunspent.side_effect
    results = {}
    errors = []

    def paused_check_utxo():
        original_check_utxo()
        export_refreshed_utxos.set()
        if not allow_export_to_finish.wait(timeout=5):
            raise RuntimeError("test timed out waiting to resume export")

    def observed_listlockunspent():
        if threading.current_thread().name == "concurrent-export-freeze":
            freeze_reached_core.set()
        return original_listlockunspent()

    def export():
        try:
            results["records"] = parse_export(wallet)
        except Exception as e:
            errors.append(e)

    def freeze():
        freeze_started.set()
        try:
            results["freeze"] = wallet.set_frozen_state(outpoint, True)
        except Exception as e:
            errors.append(e)

    wallet.check_utxo = paused_check_utxo
    wallet._rpc.listlockunspent.side_effect = observed_listlockunspent
    export_thread = threading.Thread(target=export, name="concurrent-export")
    freeze_thread = threading.Thread(target=freeze, name="concurrent-export-freeze")
    try:
        export_thread.start()
        assert export_refreshed_utxos.wait(timeout=5)
        freeze_thread.start()
        assert freeze_started.wait(timeout=5)
        assert not freeze_reached_core.wait(timeout=0.2)
    finally:
        allow_export_to_finish.set()
        export_thread.join(timeout=5)
        if freeze_thread.ident is not None:
            freeze_thread.join(timeout=5)

    assert not export_thread.is_alive()
    assert not freeze_thread.is_alive()
    assert errors == []
    assert results == {
        "records": [
            {"type": "addr", "ref": ADDRESS_A, "label": "Alice"},
            {"type": "output", "ref": outpoint, "label": "Alice"},
        ],
        "freeze": True,
    }
    assert freeze_reached_core.is_set()
    assert wallet.frozen_utxo == [outpoint]


def test_bip329_download_is_separate_utf8_jsonl_attachment():
    wallet = make_wallet([make_address(ADDRESS_A, 0, "München ₿")])
    wallet.alias = "savings_wallet"
    flask_app = Flask(__name__)
    flask_app.specter = SimpleNamespace(
        wallet_manager=SimpleNamespace(get_by_alias=lambda alias: wallet)
    )

    with flask_app.test_request_context():
        response = settings_exportbip329labels.__wrapped__(wallet.alias)

    assert response.mimetype == "application/x-ndjson"
    assert "charset=utf-8" in response.content_type
    assert response.headers["Cache-Control"] == "no-store"
    assert "savings_wallet-labels.jsonl" in response.headers["Content-Disposition"]
    assert "München ₿" in response.get_data(as_text=True)


def test_existing_wallet_settings_endpoint_resolves_to_settings_page():
    flask_app = Flask(__name__)
    flask_app.register_blueprint(wallets_module.wallets_endpoint)

    with flask_app.test_request_context():
        assert url_for("wallets_endpoint.settings", wallet_alias="savings") == (
            "/wallet/savings/settings/"
        )
        assert (
            url_for(
                "wallets_endpoint.settings",
                wallet_alias="savings",
                rescan_blockchain=True,
            )
            == "/wallet/savings/settings/?rescan_blockchain=True"
        )
        assert (
            url_for("wallets_endpoint.settings_rescan_get", wallet_alias="savings")
            == "/wallet/savings/settings/rescan"
        )


def test_warning_only_bip329_import_is_not_flashed_as_success(monkeypatch):
    wallet = make_wallet([make_address(ADDRESS_A, 0)])
    flashes = []
    built_endpoints = []
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-only"
    flask_app.specter = SimpleNamespace(
        wallet_manager=SimpleNamespace(get_by_alias=lambda alias: wallet)
    )
    monkeypatch.setattr(wallets_module, "_", lambda message: message)
    monkeypatch.setattr(
        wallets_module,
        "flash",
        lambda message, category=None: flashes.append((category, message)),
    )

    def fake_url_for(endpoint, **values):
        built_endpoints.append(endpoint)
        return "/wallet/{}/settings".format(values["wallet_alias"])

    monkeypatch.setattr(wallets_module, "url_for", fake_url_for)

    with flask_app.test_request_context(
        method="POST",
        data={
            "action": "import_address_labels",
            "address_labels_data": json.dumps(
                {"type": "addr", "ref": UNKNOWN_ADDRESS, "label": "Not ours"}
            ),
        },
    ):
        response = settings_importaddresslabels.__wrapped__(wallet.alias)

    assert len(flashes) == 1
    assert flashes[0][0] == "warning"
    assert "not imported" in flashes[0][1]
    assert not any(message.startswith("Successfully") for category, message in flashes)
    assert built_endpoints == ["wallets_endpoint.settings"]
    assert response.location == "/wallet/{}/settings".format(wallet.alias)


def test_unicode_and_json_escaping_round_trip():
    label = 'München – Rücklage ₿ "quoted" \\ path\nnext'
    utxo = {"txid": TXID_A, "vout": 0, "address": ADDRESS_A}
    source = make_wallet([make_address(ADDRESS_A, 0, label)], [utxo])
    destination = make_wallet([make_address(ADDRESS_A, 0)], [utxo])

    report = destination.import_address_labels(
        source.export_bip329_labels(), return_report=True
    )

    assert destination._addresses[ADDRESS_A]["label"] == label
    assert report.is_bip329
    assert report.conflicting_records == 0


def test_import_addr_unknown_records_and_unknown_fields():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])
    data = "\n".join(
        [
            json.dumps(
                {
                    "type": "addr",
                    "ref": ADDRESS_A,
                    "label": "Alice",
                    "future": {"ignored": True},
                }
            ),
            json.dumps({"type": "addr", "ref": UNKNOWN_ADDRESS, "label": "Not ours"}),
            json.dumps({"type": "future-type", "ref": "anything", "label": "x"}),
        ]
    )

    report = wallet.import_bip329_labels(data)

    assert wallet._addresses[ADDRESS_A]["label"] == "Alice"
    assert report.imported_address_labels == 1
    assert report.ignored_records == 2


def test_output_labels_are_never_collapsed_into_address_labels():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A}],
    )

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": f"{TXID_A}:0", "label": "Alice"})
    )

    assert wallet._addresses[ADDRESS_A]["label"] is None
    assert report.imported_address_labels == 0
    assert report.unsupported_output_labels == 1


def test_spent_and_unspent_output_labels_on_reused_address_are_not_collapsed():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_B, "vout": 1, "address": ADDRESS_A}],
    )
    report = wallet.import_bip329_labels(
        "\n".join(
            [
                json.dumps({"type": "output", "ref": f"{TXID_A}:0", "label": "Alice"}),
                json.dumps({"type": "output", "ref": f"{TXID_B}:1", "label": "Bob"}),
            ]
        )
    )

    assert wallet._addresses[ADDRESS_A]["label"] is None
    assert report.ignored_records == 1
    assert report.unsupported_output_labels == 1


def test_addr_label_import_is_independent_of_unsupported_output_label():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A}],
    )
    data = "\n".join(
        [
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"}),
            json.dumps({"type": "output", "ref": f"{TXID_A}:0", "label": "Bob"}),
        ]
    )

    report = wallet.import_bip329_labels(data)

    assert wallet._addresses[ADDRESS_A]["label"] == "Alice"
    assert report.imported_address_labels == 1
    assert report.unsupported_output_labels == 1


def test_matching_addr_and_output_records_are_idempotent():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A}],
    )
    data = "\n".join(
        [
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"}),
            json.dumps({"type": "output", "ref": f"{TXID_A}:0", "label": "Alice"}),
        ]
    )

    first = wallet.import_bip329_labels(data)
    second = wallet.import_bip329_labels(data)

    assert wallet._addresses[ADDRESS_A]["label"] == "Alice"
    assert first.conflicting_records == second.conflicting_records == 0
    assert first.unsupported_output_labels == second.unsupported_output_labels == 1
    assert first.imported_address_labels == 1
    assert second.imported_address_labels == 0
    assert second.ignored_records == 1


def test_conflict_reporting_counts_all_affected_records():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])
    data = "\n".join(
        [
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"}),
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Bob"}),
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"}),
        ]
    )

    report = wallet.import_bip329_labels(data)

    assert wallet._addresses[ADDRESS_A]["label"] is None
    assert report.conflicting_records == 3


def test_different_origins_do_not_choose_a_label_for_the_selected_wallet():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])
    data = "\n".join(
        [
            json.dumps(
                {
                    "type": "addr",
                    "ref": ADDRESS_A,
                    "label": "Alice",
                    "origin": "wpkh([deadbeef/84'/0'/0'])",
                }
            ),
            json.dumps(
                {
                    "type": "addr",
                    "ref": ADDRESS_A,
                    "label": "Bob",
                    "origin": "wpkh([cafebabe/84'/0'/1'])",
                }
            ),
        ]
    )

    report = wallet.import_bip329_labels(data)

    assert wallet._addresses[ADDRESS_A]["label"] is None
    assert report.imported_address_labels == 0
    assert report.conflicting_records == 2


def test_non_string_origin_is_malformed_and_does_not_change_state():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])

    report = wallet.import_bip329_labels(
        json.dumps(
            {
                "type": "addr",
                "ref": ADDRESS_A,
                "label": "Alice",
                "origin": {"unexpected": "object"},
            }
        )
    )

    assert wallet._addresses[ADDRESS_A]["label"] is None
    assert report.imported_address_labels == 0
    assert report.malformed_records == 1


def test_import_spendable_false_and_true_uses_existing_frozen_state():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A}],
    )

    freeze = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )
    duplicate = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )
    thaw = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": True})
    )

    assert freeze.updated_frozen_utxos == 1
    assert duplicate.updated_frozen_utxos == 0
    assert thaw.updated_frozen_utxos == 1
    assert wallet.frozen_utxo == []


def test_concurrent_frozen_state_transactions_are_serialized_per_wallet():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": True}],
        frozen=[outpoint],
    )
    unfreeze_reached_core = threading.Event()
    allow_unfreeze_to_commit = threading.Event()
    freeze_started = threading.Event()
    freeze_reached_state_read = threading.Event()
    original_listlockunspent = wallet._rpc.listlockunspent.side_effect
    original_lockunspent = wallet._rpc.lockunspent.side_effect
    results = {}
    errors = []

    def observed_listlockunspent():
        if threading.current_thread().name == "concurrent-freeze":
            freeze_reached_state_read.set()
        return original_listlockunspent()

    def paused_lockunspent(unlock, outputs):
        result = original_lockunspent(unlock, outputs)
        if threading.current_thread().name == "concurrent-unfreeze" and unlock:
            unfreeze_reached_core.set()
            if not allow_unfreeze_to_commit.wait(timeout=5):
                raise RuntimeError("test timed out waiting to resume unfreeze")
        return result

    def change_state(name, frozen):
        if frozen:
            freeze_started.set()
        try:
            results[name] = wallet.set_frozen_state(outpoint, frozen)
        except Exception as e:
            errors.append(e)

    wallet._rpc.listlockunspent.side_effect = observed_listlockunspent
    wallet._rpc.lockunspent.side_effect = paused_lockunspent
    unfreeze_thread = threading.Thread(
        target=change_state,
        args=("unfreeze", False),
        name="concurrent-unfreeze",
    )
    freeze_thread = threading.Thread(
        target=change_state,
        args=("freeze", True),
        name="concurrent-freeze",
    )

    unfreeze_thread.start()
    assert unfreeze_reached_core.wait(timeout=5)
    freeze_thread.start()
    assert freeze_started.wait(timeout=5)
    assert not freeze_reached_state_read.wait(timeout=0.2)
    allow_unfreeze_to_commit.set()
    unfreeze_thread.join(timeout=5)
    freeze_thread.join(timeout=5)

    assert not unfreeze_thread.is_alive()
    assert not freeze_thread.is_alive()
    assert freeze_reached_state_read.is_set()
    assert errors == []
    assert results == {"unfreeze": True, "freeze": True}
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}


def test_legacy_freeze_toggle_uses_the_wallet_utxo_state_lock():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    toggle_started = threading.Event()
    toggle_finished = threading.Event()

    def toggle():
        toggle_started.set()
        wallet.toggle_freeze_utxo([outpoint])
        toggle_finished.set()

    wallet._utxo_state_lock.acquire()
    toggle_thread = threading.Thread(target=toggle)
    try:
        toggle_thread.start()
        assert toggle_started.wait(timeout=5)
        assert not toggle_finished.wait(timeout=0.2)
    finally:
        wallet._utxo_state_lock.release()
    toggle_thread.join(timeout=5)

    assert not toggle_thread.is_alive()
    assert toggle_finished.is_set()
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}


def test_legacy_ui_unfreeze_preserves_pending_psbt_lock():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": True}],
        frozen=[outpoint],
    )
    wallet.pending_psbts = {
        "pending": SimpleNamespace(utxo_dict=lambda: [{"txid": TXID_A, "vout": 0}])
    }

    with pytest.raises(FrozenStateConflictError, match="pending PSBT input"):
        wallet.toggle_freeze_utxo([outpoint])

    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    assert wallet.commit_calls == 0
    wallet._rpc.lockunspent.assert_not_called()


@pytest.mark.parametrize("initially_frozen", [False, True])
@pytest.mark.parametrize("rpc_failure", ["exception", "false"])
def test_legacy_ui_toggle_rpc_failure_keeps_core_and_local_state(
    initially_frozen, rpc_failure
):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [
            {
                "txid": TXID_A,
                "vout": 0,
                "address": ADDRESS_A,
                "locked": initially_frozen,
            }
        ],
        frozen=[outpoint] if initially_frozen else [],
    )
    if rpc_failure == "exception":
        wallet.lockunspent_error = RuntimeError("simulated RPC failure")
    else:
        wallet._rpc.lockunspent.side_effect = None
        wallet._rpc.lockunspent.return_value = False

    with pytest.raises(SpecterError, match="frozen UTXO state"):
        wallet.toggle_freeze_utxo([outpoint])

    assert (outpoint in wallet.frozen_utxo) == initially_frozen
    assert (outpoint in wallet.core_locked_outpoints) == initially_frozen
    assert wallet.commit_calls == 0
    wallet._rpc.lockunspent.assert_called_once()


def test_pending_psbt_save_is_serialized_against_freeze():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.save_to_file = MagicMock()
    psbt = SimpleNamespace(
        txid="pending",
        utxo_dict=lambda: [{"txid": TXID_A, "vout": 0}],
    )
    save_reached_core = threading.Event()
    allow_save_to_finish = threading.Event()
    freeze_reached_transaction = threading.Event()
    original_lockunspent = wallet._rpc.lockunspent.side_effect
    original_set_frozen_state = wallet._set_frozen_state
    errors = []

    def paused_lockunspent(unlock, outputs):
        result = original_lockunspent(unlock, outputs)
        if threading.current_thread().name == "pending-save":
            save_reached_core.set()
            if not allow_save_to_finish.wait(timeout=5):
                raise RuntimeError("test timed out waiting to finish pending save")
        return result

    def observed_set_frozen_state(self, ref, frozen):
        freeze_reached_transaction.set()
        return original_set_frozen_state(ref, frozen)

    def save_pending():
        try:
            wallet.save_pending_psbt(psbt)
        except Exception as e:
            errors.append(e)

    def freeze():
        try:
            wallet.set_frozen_state(outpoint, True)
        except Exception as e:
            errors.append(e)

    wallet._rpc.lockunspent.side_effect = paused_lockunspent
    wallet._set_frozen_state = MethodType(observed_set_frozen_state, wallet)
    save_thread = threading.Thread(target=save_pending, name="pending-save")
    freeze_thread = threading.Thread(target=freeze, name="concurrent-freeze")

    save_thread.start()
    assert save_reached_core.wait(timeout=5)
    freeze_thread.start()
    assert not freeze_reached_transaction.wait(timeout=0.2)
    allow_save_to_finish.set()
    save_thread.join(timeout=5)
    freeze_thread.join(timeout=5)

    assert not save_thread.is_alive()
    assert not freeze_thread.is_alive()
    assert freeze_reached_transaction.is_set()
    assert len(errors) == 1
    assert isinstance(errors[0], FrozenStateConflictError)
    assert set(wallet.pending_psbts) == {"pending"}
    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == {outpoint}


def test_general_wallet_save_cannot_overwrite_new_pending_psbt_snapshot(monkeypatch):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet._persist_wallet_file = MethodType(Wallet._persist_wallet_file, wallet)
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"pending_psbts": sorted(self.pending_psbts)},
        wallet,
    )
    psbt = SimpleNamespace(
        txid="pending",
        utxo_dict=lambda: [{"txid": TXID_A, "vout": 0}],
    )
    old_snapshot_reached_writer = threading.Event()
    allow_old_snapshot_write = threading.Event()
    pending_save_started = threading.Event()
    pending_save_finished = threading.Event()
    persisted_snapshots = []
    errors = []

    def write_snapshot(content, path):
        if threading.current_thread().name == "general-wallet-save":
            old_snapshot_reached_writer.set()
            if not allow_old_snapshot_write.wait(timeout=5):
                raise RuntimeError("test timed out waiting to write old snapshot")
        persisted_snapshots.append(content)

    def general_save():
        try:
            wallet.save_to_file()
        except Exception as e:
            errors.append(e)

    def save_pending():
        pending_save_started.set()
        try:
            wallet.save_pending_psbt(psbt)
        except Exception as e:
            errors.append(e)
        finally:
            pending_save_finished.set()

    monkeypatch.setattr(
        "cryptoadvance.specter.wallet.wallet.write_json_file_without_callback",
        write_snapshot,
    )
    monkeypatch.setattr(
        "cryptoadvance.specter.wallet.wallet.storage_callback", MagicMock()
    )
    general_thread = threading.Thread(target=general_save, name="general-wallet-save")
    pending_thread = threading.Thread(target=save_pending, name="pending-save")

    general_thread.start()
    assert old_snapshot_reached_writer.wait(timeout=5)
    pending_thread.start()
    assert pending_save_started.wait(timeout=5)
    assert not pending_save_finished.wait(timeout=0.2)
    assert wallet.pending_psbts == {}
    allow_old_snapshot_write.set()
    general_thread.join(timeout=5)
    pending_thread.join(timeout=5)

    assert not general_thread.is_alive()
    assert not pending_thread.is_alive()
    assert errors == []
    assert persisted_snapshots == [
        {"pending_psbts": []},
        {"pending_psbts": ["pending"]},
    ]
    assert set(wallet.pending_psbts) == {"pending"}
    assert wallet.core_locked_outpoints == {outpoint}


def test_pending_psbt_delete_is_serialized_against_unfreeze():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": True}],
        frozen=[outpoint],
    )
    wallet.pending_psbts = {
        "pending": SimpleNamespace(utxo_dict=lambda: [{"txid": TXID_A, "vout": 0}])
    }
    delete_reached_save = threading.Event()
    allow_delete_to_finish = threading.Event()
    unfreeze_reached_transaction = threading.Event()
    original_set_frozen_state = wallet._set_frozen_state
    errors = []

    def paused_save(self):
        delete_reached_save.set()
        if not allow_delete_to_finish.wait(timeout=5):
            raise RuntimeError("test timed out waiting to finish pending delete")

    def observed_set_frozen_state(self, ref, frozen):
        unfreeze_reached_transaction.set()
        return original_set_frozen_state(ref, frozen)

    def delete_pending():
        try:
            wallet.delete_pending_psbt("pending")
        except Exception as e:
            errors.append(e)

    def unfreeze():
        try:
            wallet.set_frozen_state(outpoint, False)
        except Exception as e:
            errors.append(e)

    wallet.save_to_file = MethodType(paused_save, wallet)
    wallet._set_frozen_state = MethodType(observed_set_frozen_state, wallet)
    delete_thread = threading.Thread(target=delete_pending, name="pending-delete")
    unfreeze_thread = threading.Thread(target=unfreeze, name="concurrent-unfreeze")

    delete_thread.start()
    assert delete_reached_save.wait(timeout=5)
    assert wallet.pending_psbts == {}
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    unfreeze_thread.start()
    assert not unfreeze_reached_transaction.wait(timeout=0.2)
    allow_delete_to_finish.set()
    delete_thread.join(timeout=5)
    unfreeze_thread.join(timeout=5)

    assert not delete_thread.is_alive()
    assert not unfreeze_thread.is_alive()
    assert unfreeze_reached_transaction.is_set()
    assert errors == []
    assert wallet.pending_psbts == {}
    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == set()


def test_deleting_pending_psbt_keeps_lock_for_frozen_outpoint():
    outpoint = f"{TXID_A}:0"
    utxo = {"txid": TXID_A, "vout": 0}
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{**utxo, "address": ADDRESS_A, "locked": True}],
        frozen=[outpoint],
    )
    wallet.save_to_file = MagicMock()
    wallet.pending_psbts = {
        "first": SimpleNamespace(utxo_dict=lambda: [utxo]),
    }

    wallet.delete_pending_psbt("first")

    assert wallet.pending_psbts == {}
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    wallet._rpc.lockunspent.assert_not_called()


def test_deleting_pending_psbt_keeps_lock_for_other_pending_psbt():
    outpoint = f"{TXID_A}:0"
    utxo = {"txid": TXID_A, "vout": 0}
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{**utxo, "address": ADDRESS_A, "locked": True}],
    )
    wallet.save_to_file = MagicMock()
    wallet.pending_psbts = {
        "first": SimpleNamespace(utxo_dict=lambda: [utxo]),
        "second": SimpleNamespace(utxo_dict=lambda: [utxo]),
    }

    wallet.delete_pending_psbt("first")

    assert set(wallet.pending_psbts) == {"second"}
    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == {outpoint}
    wallet._rpc.lockunspent.assert_not_called()


def test_deleting_last_pending_psbt_unlocks_unowned_outpoint():
    outpoint = f"{TXID_A}:0"
    utxo = {"txid": TXID_A, "vout": 0}
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{**utxo, "address": ADDRESS_A, "locked": True}],
    )
    wallet.save_to_file = MagicMock()
    wallet.pending_psbts = {
        "pending": SimpleNamespace(utxo_dict=lambda: [utxo]),
    }

    wallet.delete_pending_psbt("pending")

    assert wallet.pending_psbts == {}
    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == set()
    wallet._rpc.lockunspent.assert_called_once_with(True, [utxo])


def test_spendable_false_repairs_missing_core_lock_for_frozen_utxo():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
        frozen=[outpoint],
    )

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    assert report.updated_frozen_utxos == 1
    assert report.failed_records == 0


@pytest.mark.parametrize(
    "initially_frozen,initially_locked,spendable",
    [(False, False, False), (True, True, True)],
)
def test_frozen_state_rpc_failure_does_not_mutate_or_report_success(
    initially_frozen, initially_locked, spendable
):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [
            {
                "txid": TXID_A,
                "vout": 0,
                "address": ADDRESS_A,
                "locked": initially_locked,
            }
        ],
        frozen=[outpoint] if initially_frozen else [],
    )
    wallet.lockunspent_error = RuntimeError("simulated RPC failure")

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": spendable})
    )

    assert (outpoint in wallet.frozen_utxo) == initially_frozen
    assert (outpoint in wallet.core_locked_outpoints) == initially_locked
    assert report.updated_frozen_utxos == 0
    assert report.failed_records == 1
    assert wallet.commit_calls == 0


def test_frozen_state_false_rpc_result_does_not_mutate_or_report_success():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet._rpc.lockunspent.side_effect = None
    wallet._rpc.lockunspent.return_value = False

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == set()
    assert report.updated_frozen_utxos == 0
    assert report.failed_records == 1
    assert wallet.commit_calls == 0


def test_frozen_state_wallet_write_failure_rolls_back_core_memory_and_file():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"frozen_utxo": list(self.frozen_utxo)},
        wallet,
    )
    committed_snapshots = []

    def fail_commit_then_restore(self):
        committed_snapshots.append(self.to_json())
        if len(committed_snapshots) == 1:
            raise SpecterError("simulated wallet write failure")

    wallet._persist_wallet_file = MethodType(fail_commit_then_restore, wallet)

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == set()
    assert report.updated_frozen_utxos == 0
    assert report.failed_records == 1
    assert committed_snapshots == [
        {"frozen_utxo": [outpoint]},
        {"frozen_utxo": []},
    ]
    assert [call.args[0] for call in wallet._rpc.lockunspent.call_args_list] == [
        False,
        True,
    ]


def test_frozen_state_post_commit_balance_failure_keeps_committed_state(tmp_path):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.fullpath = str(tmp_path / "wallet.json")
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"frozen_utxo": list(self.frozen_utxo)},
        wallet,
    )
    wallet.update_balance = MethodType(lambda self: None, wallet)
    wallet._persist_wallet_file = MethodType(Wallet._persist_wallet_file, wallet)
    wallet.save_to_file = MethodType(Wallet.save_to_file, wallet)
    wallet.save_to_file()
    with open(wallet.fullpath, encoding="utf-8") as wallet_file:
        original_wallet_json = json.load(wallet_file)

    def fail_update_balance(self):
        raise SpecterError("simulated post-write balance failure")

    wallet.update_balance = MethodType(fail_update_balance, wallet)

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    with open(wallet.fullpath, encoding="utf-8") as wallet_file:
        committed_wallet_json = json.load(wallet_file)
    assert original_wallet_json == {"frozen_utxo": []}
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    assert committed_wallet_json == {"frozen_utxo": [outpoint]}
    assert report.updated_frozen_utxos == 1
    assert report.failed_records == 0
    assert [call.args[0] for call in wallet._rpc.lockunspent.call_args_list] == [
        False,
    ]


def test_frozen_state_post_commit_callback_failure_keeps_committed_state(
    caplog, monkeypatch, tmp_path
):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.fullpath = str(tmp_path / "wallet.json")
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"frozen_utxo": list(self.frozen_utxo)},
        wallet,
    )
    wallet._persist_wallet_file = MethodType(Wallet._persist_wallet_file, wallet)
    wallet.update_balance = MagicMock()

    def fail_callback(mode="write", path=None):
        raise SpecterError("simulated post-commit callback failure")

    monkeypatch.setattr(
        "cryptoadvance.specter.wallet.wallet.storage_callback", fail_callback
    )
    caplog.set_level(logging.ERROR)

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    with open(wallet.fullpath, encoding="utf-8") as wallet_file:
        assert json.load(wallet_file) == {"frozen_utxo": [outpoint]}
    assert wallet.frozen_utxo == [outpoint]
    assert wallet.core_locked_outpoints == {outpoint}
    assert report.updated_frozen_utxos == 1
    assert report.failed_records == 0
    wallet.update_balance.assert_called_once_with()
    assert "post-persistence callback failed" in caplog.text
    assert outpoint not in caplog.text


def test_frozen_state_failed_file_rollback_logs_critical_without_metadata(caplog):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"frozen_utxo": list(self.frozen_utxo)},
        wallet,
    )

    def fail_commit_and_restore(self):
        raise SpecterError("simulated persisted-state rollback failure")

    wallet._persist_wallet_file = MethodType(fail_commit_and_restore, wallet)
    caplog.set_level(logging.CRITICAL)

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == set()
    assert report.failed_records == 1
    assert "manual wallet state verification is required" in caplog.text
    assert outpoint not in caplog.text
    assert [call.args[0] for call in wallet._rpc.lockunspent.call_args_list] == [
        False,
        True,
    ]


def test_frozen_state_failed_core_rollback_logs_critical_without_metadata(caplog):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    wallet.to_json = MethodType(
        lambda self, for_export=False: {"frozen_utxo": list(self.frozen_utxo)},
        wallet,
    )
    committed_snapshots = []

    def fail_commit_then_restore(self):
        committed_snapshots.append(self.to_json())
        if len(committed_snapshots) == 1:
            raise SpecterError("simulated wallet write failure")

    wallet._persist_wallet_file = MethodType(fail_commit_then_restore, wallet)

    def fail_rollback(unlock, outputs):
        if unlock:
            raise RuntimeError("simulated rollback failure")
        wallet.core_locked_outpoints.add(outpoint)
        return True

    wallet._rpc.lockunspent.side_effect = fail_rollback
    caplog.set_level(logging.CRITICAL)

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )

    assert wallet.frozen_utxo == []
    assert wallet.core_locked_outpoints == {outpoint}
    assert report.failed_records == 1
    assert committed_snapshots == [
        {"frozen_utxo": [outpoint]},
        {"frozen_utxo": []},
    ]
    assert "manual wallet lock verification is required" in caplog.text
    assert outpoint not in caplog.text


def test_bip329_spendable_does_not_touch_pending_psbt_input():
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": True}],
    )
    wallet.pending_psbts = {
        "pending": SimpleNamespace(utxo_dict=lambda: [{"txid": TXID_A, "vout": 0}])
    }

    freeze = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": False})
    )
    thaw = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": True})
    )

    assert wallet.frozen_utxo == []
    assert freeze.updated_frozen_utxos == thaw.updated_frozen_utxos == 0
    assert freeze.conflicting_records == thaw.conflicting_records == 1


@pytest.mark.parametrize("spendable", [False, True])
def test_bip329_does_not_change_an_unknown_core_lock(spendable):
    outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": True}],
    )

    report = wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": outpoint, "spendable": spendable})
    )

    assert wallet.frozen_utxo == []
    assert report.updated_frozen_utxos == 0
    assert report.conflicting_records == 1


def test_import_and_export_refresh_stale_utxo_cache():
    refreshed_utxo = {
        "txid": TXID_A,
        "vout": 0,
        "address": ADDRESS_A,
        "locked": False,
    }
    export_wallet = make_wallet([make_address(ADDRESS_A, 0, "Alice")])
    export_wallet.refreshed_utxos = [refreshed_utxo]

    exported = parse_export(export_wallet)

    assert export_wallet.check_utxo_calls == 1
    assert {"type": "output", "ref": f"{TXID_A}:0", "label": "Alice"} in exported

    import_wallet = make_wallet([make_address(ADDRESS_A, 0)])
    import_wallet.refreshed_utxos = [refreshed_utxo]
    report = import_wallet.import_bip329_labels(
        json.dumps({"type": "output", "ref": f"{TXID_A}:0", "spendable": False})
    )

    assert import_wallet.check_utxo_calls == 1
    assert import_wallet.frozen_utxo == [f"{TXID_A}:0"]
    assert report.updated_frozen_utxos == 1


def test_locked_utxo_keeps_address_amount_and_bip329_output():
    """Core/Spectrum listunspent omits locks; the outpoint must still export."""
    amount_sats = 38759
    amount = amount_sats * 1e-8
    raw_tx = Transaction(
        vin=[TransactionInput(bytes(32), 0)],
        vout=[
            TransactionOutput(amount_sats, script.address_to_scriptpubkey(ADDRESS_A))
        ],
    )
    txid = raw_tx.txid().hex()
    outpoint = f"{txid}:0"
    wallet = make_wallet([make_address(ADDRESS_A, 0, "Alice")])
    wallet.check_utxo = MethodType(Wallet.check_utxo, wallet)
    wallet.manager = SimpleNamespace(chain="main")
    wallet._transactions = MagicMock()
    wallet._transactions.get_transactions.return_value = [
        {"txid": txid, "time": 1, "address": ADDRESS_A, "label": "Alice"}
    ]
    wallet._rpc.listunspent.return_value = [
        {"txid": txid, "vout": 0, "address": ADDRESS_A, "amount": amount}
    ]
    wallet._rpc.gettransaction.return_value = {
        "details": [{"vout": 0, "address": ADDRESS_A, "amount": amount}],
        "hex": str(raw_tx),
    }

    wallet.check_utxo()
    assert len(wallet.full_utxo) == 1
    assert wallet.full_utxo[0]["locked"] is False

    # Both Bitcoin Core and Spectrum exclude locked outputs from listunspent.
    wallet.core_locked_outpoints.add(outpoint)
    wallet.frozen_utxo.append(outpoint)
    wallet._rpc.listunspent.return_value = []
    wallet.check_utxo()

    assert len(wallet.full_utxo) == 1
    assert wallet.full_utxo[0]["locked"] is True
    assert wallet.full_utxo[0]["address"] == ADDRESS_A
    assert wallet.full_utxo[0]["amount"] == amount
    assert {
        "type": "output",
        "ref": outpoint,
        "label": "Alice",
        "spendable": False,
    } in parse_export(wallet)


def test_locked_utxo_uses_actual_output_when_transaction_details_show_send():
    """A negative send detail is not the locked, wallet-owned output."""
    amount_sats = 38759
    raw_tx = Transaction(
        vin=[TransactionInput(bytes(32), 0)],
        vout=[
            TransactionOutput(amount_sats, script.address_to_scriptpubkey(ADDRESS_A))
        ],
    )
    txid = raw_tx.txid().hex()
    outpoint = f"{txid}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 1, "Alice"), make_address(ADDRESS_B, 0)]
    )
    wallet.check_utxo = MethodType(Wallet.check_utxo, wallet)
    wallet.manager = SimpleNamespace(chain="main")
    wallet._transactions = MagicMock()
    wallet._transactions.get_transactions.return_value = [
        {"txid": txid, "time": 1, "address": ADDRESS_B, "label": ""}
    ]
    wallet.core_locked_outpoints.add(outpoint)
    wallet.frozen_utxo.append(outpoint)
    wallet._rpc.listunspent.return_value = []
    wallet._rpc.gettransaction.return_value = {
        "details": [
            {
                "vout": 0,
                "category": "send",
                "address": ADDRESS_B,
                "amount": -0.00039759,
            }
        ],
        "hex": str(raw_tx),
    }

    wallet.check_utxo()

    assert len(wallet.full_utxo) == 1
    assert wallet.full_utxo[0]["address"] == ADDRESS_A
    assert wallet.full_utxo[0]["amount"] == amount_sats * 1e-8
    assert {
        "type": "output",
        "ref": outpoint,
        "label": "Alice",
        "spendable": False,
    } in parse_export(wallet)


def make_locked_confidential_liquid_wallet():
    amount_sats = 38759
    output_script = script.address_to_scriptpubkey(ADDRESS_A)
    blinding_key = ec.PrivateKey(bytes([1]) * 32).get_public_key()
    address = liquid_address(output_script, blinding_key, NETWORKS["liquidtestnet"])
    other_address = liquid_address(
        script.address_to_scriptpubkey(ADDRESS_B),
        blinding_key,
        NETWORKS["liquidtestnet"],
    )
    raw_tx = LTransaction(
        vin=[LTransactionInput(bytes(32), 0)],
        vout=[
            LTransactionOutput(bytes(32), bytes([8]) + bytes([2]) * 32, output_script)
        ],
    )
    assert not isinstance(raw_tx.vout[0].value, int)
    txid = raw_tx.txid().hex()
    outpoint = f"{txid}:0"
    wallet = make_wallet(
        [make_address(address, 0, "Liquid reserve")], wallet_cls=StubLiquidWallet
    )
    liquid_addresses = LAddressList("unused-liquid-addresses.csv", wallet._rpc)
    liquid_addresses[address] = LAddress(
        wallet._rpc,
        address=address,
        index=0,
        change=False,
        label="Liquid reserve",
        used=True,
        service_id=None,
    )
    liquid_addresses._update_scripts()
    wallet._addresses = liquid_addresses
    wallet.check_utxo = MethodType(Wallet.check_utxo, wallet)
    wallet.manager = SimpleNamespace(chain="liquidtestnet")
    wallet._transactions = MagicMock()
    wallet._transactions.get_transactions.return_value = [
        {"txid": txid, "time": 1, "address": address, "label": "Liquid reserve"}
    ]
    wallet.core_locked_outpoints.add(outpoint)
    wallet.frozen_utxo.append(outpoint)
    wallet._rpc.listunspent.return_value = []
    return wallet, raw_tx, address, other_address, outpoint, amount_sats


def test_locked_confidential_liquid_utxo_uses_unblinded_wallet_detail():
    (
        wallet,
        raw_tx,
        address,
        other_address,
        outpoint,
        amount_sats,
    ) = make_locked_confidential_liquid_wallet()
    wallet._rpc.gettransaction.return_value = {
        "hex": str(raw_tx),
        "details": [
            {
                "vout": 0,
                "category": "send",
                "address": other_address,
                "amount": -0.00039759,
            },
            {
                "vout": 0,
                "category": "receive",
                "address": address,
                "amount": amount_sats * 1e-8,
            },
        ],
    }
    wallet._rpc.decoderawtransaction.side_effect = AssertionError(
        "Wallet detail already supplies the unblinded output"
    )

    wallet.check_utxo()

    assert len(wallet.full_utxo) == 1
    assert wallet.full_utxo[0]["address"] == address
    assert wallet.full_utxo[0]["amount"] == amount_sats * 1e-8
    assert {
        "type": "output",
        "ref": outpoint,
        "label": "Liquid reserve",
        "spendable": False,
    } in parse_export(wallet)


def test_locked_confidential_liquid_change_uses_unblinding_decoder():
    (
        wallet,
        raw_tx,
        address,
        _,
        _,
        amount_sats,
    ) = make_locked_confidential_liquid_wallet()
    wallet._rpc.gettransaction.return_value = {"hex": str(raw_tx), "details": []}
    wallet._rpc.decoderawtransaction.return_value = {
        "vout": [
            {
                "value": amount_sats * 1e-8,
                "scriptPubKey": {"addresses": [to_unconfidential(address)]},
            }
        ]
    }

    wallet.check_utxo()

    assert wallet.full_utxo[0]["address"] == address
    assert wallet.full_utxo[0]["amount"] == amount_sats * 1e-8
    wallet._rpc.decoderawtransaction.assert_called_once_with(str(raw_tx))


def test_unknown_and_conflicting_outpoint_state_do_not_create_wallet_state():
    known_outpoint = f"{TXID_A}:0"
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A}],
    )
    data = "\n".join(
        [
            json.dumps({"type": "output", "ref": f"{TXID_B}:5", "spendable": False}),
            json.dumps({"type": "output", "ref": known_outpoint, "spendable": False}),
            json.dumps({"type": "output", "ref": known_outpoint, "spendable": True}),
        ]
    )

    report = wallet.import_bip329_labels(data)

    assert wallet.frozen_utxo == []
    assert report.ignored_records == 1
    assert report.conflicting_records == 2


def test_malformed_lines_and_values_fail_safely_but_valid_lines_import():
    wallet = make_wallet(
        [make_address(ADDRESS_A, 0)],
        [{"txid": TXID_A, "vout": 0, "address": ADDRESS_A, "locked": False}],
    )
    data = "\n".join(
        [
            "not json",
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": ["bad"]}),
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "München ₿"}),
            json.dumps(
                {"type": "output", "ref": "not-an-outpoint", "spendable": False}
            ),
            json.dumps(
                {
                    "type": "output",
                    "ref": f"{TXID_A}:0",
                    "label": ["bad"],
                    "spendable": False,
                }
            ),
        ]
    )

    records, parse_report = parse_bip329_jsonl(data)
    assert records is not None
    report = wallet.import_bip329_labels(records, parse_report)

    assert wallet._addresses[ADDRESS_A]["label"] == "München ₿"
    assert wallet.frozen_utxo == []
    assert report.malformed_records == 4


def test_bip329_size_limits(monkeypatch):
    monkeypatch.setattr(bip329, "MAX_BIP329_FILE_SIZE", 20)
    with pytest.raises(ValueError, match="too large"):
        parse_bip329_jsonl(
            json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"})
        )

    legacy_records, legacy_report = parse_bip329_jsonl(
        json.dumps({ADDRESS_A: "x" * 100})
    )
    assert legacy_records is None
    assert not legacy_report.is_bip329

    monkeypatch.setattr(bip329, "MAX_BIP329_FILE_SIZE", 1000)
    monkeypatch.setattr(bip329, "MAX_BIP329_LINE_SIZE", 120)
    records, report = parse_bip329_jsonl(
        json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "x" * 121})
        + "\n"
        + json.dumps({"type": "addr", "ref": ADDRESS_A, "label": "Alice"})
    )
    assert len(records) == 1
    assert report.malformed_records == 1


def test_bip329_size_limit_does_not_restrict_legacy_imports(monkeypatch):
    monkeypatch.setattr(bip329, "MAX_BIP329_FILE_SIZE", 20)
    wallet = make_wallet([make_address(ADDRESS_A, 0)])
    label = "legacy-" + "x" * 100

    imported = wallet.import_address_labels(json.dumps({ADDRESS_A: label}))

    assert imported == 1
    assert wallet._addresses[ADDRESS_A]["label"] == label


def test_legacy_json_with_type_key_is_not_misdetected_as_bip329():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])

    report = wallet.import_address_labels(
        json.dumps({"type": "addr", ADDRESS_A: "Alice"}),
        return_report=True,
    )

    assert not report.is_bip329
    assert report.imported_address_labels == 1
    assert wallet._addresses[ADDRESS_A]["label"] == "Alice"


def test_document_with_only_unknown_future_type_is_detected_and_ignored():
    wallet = make_wallet([make_address(ADDRESS_A, 0)])

    report = wallet.import_address_labels(
        json.dumps({"type": "future-type", "ref": "future-ref", "label": "Alice"}),
        return_report=True,
    )

    assert report.is_bip329
    assert report.imported_address_labels == 0
    assert report.ignored_records == 1
    assert wallet._addresses[ADDRESS_A]["label"] is None


@pytest.mark.parametrize("payload", ["[]", '{"address": ["not a label"]}', "not json"])
def test_malformed_legacy_imports_raise_safely_without_changing_labels(payload):
    wallet = make_wallet([make_address(ADDRESS_A, 0)])

    with pytest.raises(SpecterError):
        wallet.import_address_labels(payload)

    assert wallet._addresses[ADDRESS_A]["label"] is None


@pytest.mark.parametrize(
    "payload,expected",
    [
        (json.dumps({ADDRESS_A: "Electrum"}), "Electrum"),
        (
            json.dumps({"alias": "wallet", "labels": {"Specter": [ADDRESS_A]}}),
            "Specter",
        ),
        ("Address,Label\n{},CSV".format(ADDRESS_A), "CSV"),
    ],
)
def test_existing_label_import_formats_still_work(payload, expected):
    wallet = make_wallet([make_address(ADDRESS_A, 0)])

    imported = wallet.import_address_labels(payload)

    assert imported == 1
    assert wallet._addresses[ADDRESS_A]["label"] == expected
