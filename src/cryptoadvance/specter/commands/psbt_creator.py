import json
from json.decoder import JSONDecodeError
import logging
from math import isnan

import requests
from cryptoadvance.specter.util.psbt import SpecterPSBT
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.common import str2bool

from ..helpers import normalize_address
from ..util.descriptor import AddChecksum, Descriptor

logger = logging.getLogger(__name__)


class PsbtCreator:
    """A class to create PSBTs easily out of stuff coming from the frontend
    For an overview of the overall workflow, checkout e.g.
    https://github.com/bitcoin/bitcoin/blob/master/doc/psbt.md
    """

    def __init__(
        self,
        specter,
        wallet,
        ui_option,
        request_form=None,
        recipients_txt=None,
        recipients_amount_unit=None,
        request_json=None,
    ):
        """
        * depending of ui_option = (ui|text) Fill the payment-details in either of these:
          * request_form: For details on the structure of the data for each recipient (amounts, addresses, etc.) see below at paymentinfo_from_ui
          * recipients_txt: expects the payment-details in textblock "recipients" and recipients_amount_unit for all
            amounts in recipients_txt either "sats" or "btc"
        * in both cases, the request_form also contains:
          * "substract": optional (default: False), Boolean whether to substract the fee from the amounts, otherwise additional input gets created
          * "subtract_from": index on which address to substract the fee from
          * fee_options:
            * "dynamic": get the fee from "fee_rate_dynamic"
            * "fee_rate": directly get the fee
          * "rbf": "on" or "off" "boolean" whether to replace-by-fee
          * "estimate_fee"
        """
        # Good to have some values for error-reporting
        self.ui_option = ui_option
        self.request_form = request_form
        self.request_json = request_json

        if ui_option == "ui":
            (
                self.addresses,
                self.labels,
                self.amounts,
                self.amount_units,
            ) = PsbtCreator.paymentinfo_from_ui(
                specter, wallet, request_form=request_form
            )
        elif ui_option == "text":
            if recipients_txt is None or recipients_amount_unit is None:
                raise SpecterError(
                    "recipients_txt and recipients_amount_unit is mandatory"
                )
            (
                self.addresses,
                self.labels,
                self.amounts,
                self.amount_units,
            ) = PsbtCreator.paymentinfo_from_text(
                specter,
                wallet,
                recipients_txt=recipients_txt,
                recipients_amount_unit=recipients_amount_unit,
            )
        elif ui_option == "json":
            if request_json is None:
                raise SpecterError("request_json is mandatory")
            (
                self.addresses,
                self.labels,
                self.amounts,
                self.amount_units,
            ) = PsbtCreator.paymentinfo_from_json(
                specter, wallet, request_json=request_json
            )
        else:
            raise SpecterError(
                f"Unknown ui_option: {ui_option}. Valid ones are ui|text|json"
            )
        # normalizing
        self.addresses = [normalize_address(addr) for addr in self.addresses]
        # get kwargs
        if ui_option == "ui" or ui_option == "text":
            self.kwargs = PsbtCreator.kwargs_from_request_form(request_form)
        elif ui_option == "json":
            self.kwargs = PsbtCreator.kwargs_from_request_json(request_json)
        if specter.is_liquid:
            self.kwargs["assets"] = self.amount_units
        self.validate_before_creation()

    def validate_before_creation(self):
        if self.kwargs["fee_rate"] == None:
            if self.ui_option == "ui" or self.ui_option == "text":
                additional_data = self.request_form
            elif self.ui_option == "json":
                additional_data = self.request_json

            raise Exception(
                f"Fee Rate could not be calculated and is now None. This is not supported right now and probably unintended anyway(ui_option = {self.ui_option}).\nrequest={additional_data}\nkwargs={self.kwargs}",
                additional_data,
            )

    def create_psbt(self, wallet: Wallet) -> dict:
        """creates the PSBT via the wallet and modifies it for if substract is true
        If there was a "estimate_fee" in the request_form, the PSBT will not get persisted
        """
        self.psbt_as_object: SpecterPSBT = wallet.createpsbt(
            self.addresses, self.amounts, **self.kwargs
        )
        self.psbt = self.psbt_as_object.to_dict()
        if self.psbt is None:
            raise SpecterError(
                "Probably you don't have enough funds, or something else..."
            )
        else:
            # calculate new amount if we need to subtract
            if self.kwargs["subtract"]:
                for v in self.psbt["tx"]["vout"]:
                    if self.addresses[0] in v["scriptPubKey"].get(
                        "addresses", [""]
                    ) or self.addresses[0] == v["scriptPubKey"].get("address", ""):
                        self.amounts[0] = v["value"]
        return self.psbt

    @classmethod
    def paymentinfo_from_ui(cls, specter, wallet, request_form):
        """Calculates the correct format needed by wallet.createpsbt() out of a request form.
        The recipient_dicts part in the form is a list of dicts and looks like this:
        [{'unit': 'btc', 'amount': 1, 'btc_amount': 1, 'recipient_id': 0, 'label': '', 'address': 'bcrt1q ... 58qwn'},
        {'unit': 'btc', 'amount': 2, 'btc_amount': 2, 'recipient_id': 1, 'label': '', 'address': 'bcrt1q ... vaa3p'},
        {'unit': 'btc', 'amount': 3, 'btc_amount': 3, 'recipient_id': 2, 'label': '', 'address': 'bcrt1q ... n0a85'}]

        Returns (addresses, labels, amounts, amount_units) (all arrays)
        """
        addresses = []
        labels = []
        amounts = []
        amount_units = []

        recipient_dicts = json.loads(request_form["recipient_dicts"])
        print(recipient_dicts)
        for recipient_dict in recipient_dicts:
            addresses.append(recipient_dict["address"])
            amount = 0.0
            try:
                amount = float(recipient_dict["btc_amount"])
            except ValueError:
                pass
            if isnan(amount):
                amount = 0.0
            amounts.append(amount)
            unit = recipient_dict["unit"]
            if specter.is_liquid and unit in ["sat", "btc"]:
                unit = specter.default_asset
            amount_units.append(unit)
            labels.append(recipient_dict["label"])
            if recipient_dict["label"] != "":
                wallet.setlabel(addresses[-1], labels[-1])

        return addresses, labels, amounts, amount_units

    @classmethod
    def paymentinfo_from_text(
        cls, specter, wallet, recipients_txt, recipients_amount_unit
    ):
        """calculates the correct format needed by wallet.createpsbt() out of a request-form
        out of a textbox holding addresses and amounts.
        """
        addresses = []
        labels = []
        amounts = []
        amount_units = []
        for output in recipients_txt.splitlines():
            try:
                if output.isspace() or output == "":
                    continue
                addresses.append(output.split(",")[0].strip())
                if recipients_amount_unit == "sat":
                    amounts.append(round(float(output.split(",")[1].strip()) / 1e8, 8))
                elif recipients_amount_unit == "btc":
                    amounts.append(float(output.split(",")[1].strip()))
                else:
                    raise SpecterError(
                        f"Unknown recipients_amount_unit: {recipients_amount_unit}"
                    )
                labels.append("")
                amount_units.append(recipients_amount_unit)
            except IndexError as ie:
                logger.error(f"line does not match expected pattern: '{output}'")
        return addresses, labels, amounts, amount_units

    @classmethod
    def paymentinfo_from_json(cls, specter, wallet, request_json):
        """calculates the correct format needed by wallet.createpsbt() out of a json
        Example:
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
            "subtract_from": "1",
            "fee_rate": "64",
            "rbf": true,
        }
        returns something like  (addresses, labels, amounts, amount_units) (all arrays)
        """
        addresses = []
        labels = []
        amounts = []
        amount_units = []
        try:
            if isinstance(request_json, dict):
                json_data = request_json
            else:
                json_data = json.loads(request_json)

        except JSONDecodeError as e:
            raise SpecterError(f"Error parsing json: {e}")
        for recipient in json_data["recipients"]:
            try:
                addresses.append(recipient["address"])
                try:
                    amount = float(recipient["amount"])
                    if recipient["unit"] == "sat":
                        amounts.append(round(amount / 1e8, 8))
                    elif recipient["unit"] == "btc":
                        amounts.append(amount)
                    else:
                        if specter.is_liquid:
                            if len(recipient["unit"]) == 64:
                                amounts.append(amount)
                            else:
                                raise SpecterError(
                                    f"Non-compliant json: Unknown unit {recipient['unit']}. Accepted: sat, btc or 64-char hex asset id."
                                )
                        else:
                            raise SpecterError(
                                f"Non-compliant json: Unknown unit {recipient['unit']}. This could be caused by using a special name for your Elements regtest."
                            )
                except ValueError as e:
                    raise SpecterError(
                        f"Could not parse amount {recipient.get('amount')} because {e}"
                    )
                unit = recipient["unit"]
                if specter.is_liquid and unit in ["sat", "btc"]:
                    unit = specter.default_asset
                amount_units.append(unit)

                label = recipient.get("label", "")
                labels.append(label)
                if label != "":
                    wallet.setlabel(recipient["address"], label)
            except KeyError as ke:
                raise SpecterError(f"Data missing in json: {ke}")
        return addresses, labels, amounts, amount_units

    def kwargs_from_request_form(request_form):
        """calculates the needed kwargs fow wallet.createpsbt() out of a request_form"""
        # Who pays the fees?
        subtract = str2bool(request_form.get("subtract", False))
        subtract_from = request_form.get("subtract_from", 0)
        # subtract_from is an empty string in the form request if "Subtract fees from amount" is not checked in the UI
        subtract_from = int(subtract_from) if subtract_from else 0
        fee_option = request_form.get("fee_option")
        fee_rate = None
        if fee_option:
            if "dynamic" in fee_option:
                if request_form.get("fee_rate_dynamic"):
                    fee_rate = float(request_form.get("fee_rate_dynamic"))
                else:
                    raise Exception(
                        "fee_option is dynamic but no fee_rate_dynamic given",
                        request_form,
                    )
            else:
                if request_form.get("fee_rate"):
                    fee_rate = float(request_form.get("fee_rate"))
                else:
                    raise Exception(
                        "fee_option is manual but no fee_rate given", request_form
                    )
        rbf = str2bool(request_form.get("rbf", False))
        # workaround for making the tests work with a dict
        if hasattr(request_form, "getlist"):
            coins = [coin.split(",") for coin in request_form.getlist("coinselect")]
            # convert to tuples
            selected_coins = [
                {"txid": txid.strip(), "vout": int(vout)} for txid, vout in coins
            ]
        else:
            selected_coins = []
        rbf_tx_id = request_form.get("rbf_tx_id", "")
        kwargs = {
            "subtract": subtract,
            "subtract_from": subtract_from,
            "fee_rate": fee_rate,
            "rbf": rbf,
            "selected_coins": selected_coins,
            # determines whether the psbt gets persisted
            "readonly": "estimate_fee" in request_form,
            "rbf_edit_mode": (rbf_tx_id != ""),
        }
        return kwargs

    @classmethod
    def kwargs_from_request_json(cls, request_json):
        """calculates the needed kwargs fow wallet.createpsbt() out of a request_json"""
        # Who pays the fees?
        try:
            if isinstance(request_json, dict):
                json_data = request_json
            else:
                json_data = json.loads(request_json)

        except JSONDecodeError as e:
            raise SpecterError(f"Error parsing json: {e}")
        subtract = bool(json_data.get("subtract", False))
        subtract_from = int(json_data.get("subtract_from", 0))

        fee_rate = float(json_data.get("fee_rate", None))
        rbf = bool(json_data.get("rbf", False))
        rbf_tx_id = json_data.get("rbf_tx_id", "")
        kwargs = {
            "subtract": subtract,
            "subtract_from": subtract_from,
            "fee_rate": fee_rate,
            "rbf": rbf,
            "selected_coins": [],
            "readonly": False,  # determines whether the psbt gets persisted
            "rbf_edit_mode": (rbf_tx_id != ""),
        }
        return kwargs

    def __repr__(self) -> str:
        status = "created" if hasattr(self, "psbt") else "initialized"
        return f"<{self.__class__.__name__} amountSum={sum(self.amounts) } {status}>"
