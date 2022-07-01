import logging
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.util.descriptor import Descriptor
from cryptoadvance.specter.commands.psbt_creator import PsbtCreator
from mock import MagicMock, call, patch


def test_PsbtCreator_ui(caplog):
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
        "amount_unit_text": "btc",
        "subtract_from": "0",
        "fee_option": "dynamic",
        "fee_rate": "",
        "fee_rate_dynamic": "64",
        "rbf": "on",
        "action": "createpsbt",
        "recipient_dicts": '[{"unit":"btc","amount":0.1,"recipient_id":0,"address":"BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8","label":"someLabel","btc_amount":"0.1"},'
        '{"unit":"sat","amount":111211,"recipient_id":1,"address":"bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a","label":"someOtherLabel","btc_amount":"0.00111211"},'
        '{"unit":"btc","amount":0.003,"recipient_id":2,"address":"bcrt1qfvkcy2keql72s8ev87ek93uxuq3xxsx9l0n03r","label":"<script>console.log(\'I escaped\')</script>","btc_amount":"0.003"}]',
    }

    psbt_creator: PsbtCreator = PsbtCreator(
        specter_mock, wallet_mock, "ui", request_form=request_form_data
    )

    assert psbt_creator.addresses == [
        "bcrt1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
        "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
        "bcrt1qfvkcy2keql72s8ev87ek93uxuq3xxsx9l0n03r",
    ]
    assert psbt_creator.amounts == [0.1, 0.00111211, 0.003]
    assert psbt_creator.labels == [
        "someLabel",
        "someOtherLabel",
        "<script>console.log('I escaped')</script>",
    ]
    assert psbt_creator.amount_units == ["btc", "sat", "btc"]
    assert psbt_creator.kwargs == {
        "fee_rate": 64.0,
        "rbf": True,
        "rbf_edit_mode": False,
        "readonly": False,
        "selected_coins": [],
        "subtract": False,
        "subtract_from": 0,
    }

    psbt_creator.create_psbt(wallet_mock)


def test_PsbtCreator_text(caplog):
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
        "subtract_from": "0",
        "fee_option": "dynamic",
        "fee_rate": "",
        "fee_rate_dynamic": "64",
        "rbf": "on",
        "action": "createpsbt",
    }

    recipients_txt = """
BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8, 0.1
bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a, 0.5
    """

    psbt_creator: PsbtCreator = PsbtCreator(
        specter_mock,
        wallet_mock,
        "text",
        request_form=request_form_data,
        recipients_txt=recipients_txt,
        recipients_amount_unit="btc",
    )

    assert psbt_creator.addresses == [
        "bcrt1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
        "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
    ]
    assert psbt_creator.amounts == [0.1, 0.5]
    # no labeling for the text-option
    # assert psbt_creator.labels == ["someLabel", "someOtherLabel"]
    assert psbt_creator.amount_units == ["btc", "btc"]
    assert psbt_creator.kwargs == {
        "fee_rate": 64.0,
        "rbf": True,
        "rbf_edit_mode": False,
        "readonly": False,
        "selected_coins": [],
        "subtract": False,
        "subtract_from": 0,
    }

    psbt_creator.create_psbt(wallet_mock)


def test_PsbtCreator_json(caplog):
    caplog.set_level(logging.DEBUG)
    specter_mock = MagicMock()
    # non liquid and default asset btc (for unit-calculation)
    specter_mock.is_liquid = False
    specter_mock.default_asset = "btc"

    wallet_mock = MagicMock()
    specter_mock.chain = "regtest"
    # Let's mock the request.form which behaves like a dict but also needs getlist()
    request_json = """
        {
            "recipients" : [
                { 
                    "address": "BCRT1qgc6h85z43g3ss2dl5zdrzrp3ef6av4neqcqhh8",
                    "amount": 0.1,
                    "unit": "btc",
                    "label": "someLabel"
                },
                {
                    "address": "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
                    "amount": 111211,
                    "unit": "sat",
                    "label": "someOtherLabel"
                }
            ],
            "rbf_tx_id": "",
            "subtract_from": "0",
            "fee_rate": "64",
            "rbf": true
        }
    """

    psbt_creator: PsbtCreator = PsbtCreator(
        specter_mock, wallet_mock, "json", request_json=request_json
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
        "selected_coins": [],
        "subtract": False,
        "subtract_from": 0,
    }

    psbt_creator.create_psbt(wallet_mock)
