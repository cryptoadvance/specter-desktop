import logging
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.util.descriptor import Descriptor
from cryptoadvance.specter.util.psbt_creator import PsbtCreator
from mock import MagicMock, call, patch


def test_PsbtCreator(caplog):
    caplog.set_level(logging.DEBUG)
    specter_mock = MagicMock()
    # non liquid and default asset btc (for unit-calculation)
    specter_mock.is_liquid = False
    specter_mock.default_asset = "btc"

    wallet_mock = MagicMock()
    specter_mock.chain = "regtest"
    # Let's mock the request.form which behaves like a dict but also needs getlist()
    request_form_data = {
        "rbf_tx_id": "",
        "address_0": "BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",  # will need normalisation
        "label_0": "someLabel",
        "amount_0": "0.1",
        "btc_amount_0": "0.1",
        "amount_unit_0": "btc",
        "address_1": "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
        "label_1": "someOtherLabel",
        "amount_1": "111211",
        "btc_amount_1": "0.00111211",
        "amount_unit_1": "sat",
        "amount_unit_text": "btc",
        "subtract_from": "1",
        "fee_options": "dynamic",
        "fee_rate": "",
        "fee_rate_dynamic": "64",
        "rbf": "on",
        "action": "createpsbt",
    }

    psbt_creator: PsbtCreator = PsbtCreator(
        specter_mock, wallet_mock, "ui", request_form=request_form_data
    )

    assert psbt_creator.addresses == [
        "bcrt1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
        "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
    ]
    assert psbt_creator.amounts == [0.1, 0.00111211]
    assert psbt_creator.labels == ["someLabel", "someOtherLabel"]
    assert psbt_creator.amount_units == ["btc", "sat"]
    assert psbt_creator.kwargs == {
        "fee_rate": 64.0,
        "rbf": True,
        "rbf_edit_mode": False,
        "readonly": False,
        "selected_coins": None,
        "subtract": False,
        "subtract_from": 0,
    }

    psbt_creator.create_psbt(wallet_mock)
