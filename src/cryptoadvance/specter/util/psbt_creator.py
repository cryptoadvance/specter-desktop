import json
import logging
from math import isnan

import requests
from cryptoadvance.specter.specter_error import SpecterError

from ..helpers import is_testnet
from .descriptor import AddChecksum, Descriptor

logger = logging.getLogger(__name__)


class PsbtCreator:
    """A class to create PSBTs easily out of stuff coming from the frontend"""

    def __init__(
        self,
        specter,
        wallet,
        ui_option,
        request_form=None,
        recipients_txt=None,
        recipients_amount_unit=None,
        substract=None,
        substract_from=1,
    ):
        """
        * depending of ui_option = (ui|text) Fill the payment-details in either of these:
          * request_form: expects the payment-details in a dict request_form:
             { "address_1":"bc1...","btc_amount_1":"0.2", "amount_unit_1":"btc", "label_1":"someLabel","address_2": ...}
          * recipients_txt: expects the payment-details in textblock "recipients" and recipients_amount_unit for all
            amounts in recipients_txt either "sats" or "btc"
        * in both cases, the request_form also contains:
          * "substract": optional (default: False), Boolean whether to substract the fee from the amounts, otherwise additional input gets created
          * "substract_from": index on which address to substract the fee from
          * fee_options:
            * "dynamic": get the fee from "fee_rate_dynamic"
            * "fee_rate": directly get the fee
          * "rbf": "on" or "off" "boolean" whether to replace-by-fee
          * "estimate_fee"
        """
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
        # normalizing
        self.addresses = [
            address.lower()
            if address.startswith(("BC1", "TB1", "BCRT1", "EL1", "ERT1", "EX1", "LQ1"))
            else address
            for address in self.addresses
        ]
        # get kwargs
        self.kwargs = PsbtCreator.kwargs_from_request_form(request_form)
        if specter.is_liquid:
            self.kwargs["assets"] = self.amount_units

    def create_psbt(self, wallet):
        """creates the PSBT via the wallet and modifies it for if substract is true
        If there was a "estimate_fee" in the request_form, the PSBT will not get persisted
        """
        try:
            self.psbt = wallet.createpsbt(self.addresses, self.amounts, **self.kwargs)
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
        except Exception as e:
            logger.exception(e)
            raise SpecterError(f"{e} ... check the logs for the stacktrace")

    @classmethod
    def paymentinfo_from_ui(cls, specter, wallet, request_form):
        """calculates the correct format needed by wallet.createpsbt() out of a request-form
        returns something like  (addresses, labels, amounts, amount_units) (all arrays)
        """
        i = 0
        addresses = []
        labels = []
        amounts = []
        amount_units = []
        while "address_{}".format(i) in request_form:
            logger.debug(f"ssss {request_form['address_0']}")
            addresses.append(request_form["address_{}".format(i)])
            amount = 0.0
            try:
                amount = float(request_form["btc_amount_{}".format(i)])
            except ValueError:
                pass
            if isnan(amount):
                amount = 0.0
            amounts.append(amount)
            unit = request_form["amount_unit_{}".format(i)]
            if specter.is_liquid and unit in ["sat", "btc"]:
                unit = specter.default_asset
            amount_units.append(unit)
            labels.append(request_form["label_{}".format(i)])
            if request_form["label_{}".format(i)] != "":
                wallet.setlabel(addresses[i], labels[i])
            i += 1
        return addresses, labels, amounts, amount_units

    @classmethod
    def paymentinfo_from_text(
        cls, specter, wallet, recipients_txt, recipients_amount_unit
    ):
        """calculates the correct format needed by wallet.createpsbt() out of a request-form
        out of a textbox holding addresses and amounts.
        """
        i = 0
        addresses = []
        labels = []
        amounts = []
        amount_units = []
        for output in recipients_txt.splitlines():
            addresses.append(output.split(",")[0].strip())
            if recipients_amount_unit == "sat":
                amounts.append(float(output.split(",")[1].strip()) / 1e8)
            elif recipients_amount_unit == "btc":
                amounts.append(float(output.split(",")[1].strip()))
            else:
                raise SpecterError(
                    f"Unknown recipients_amount_unit: {recipients_amount_unit}"
                )
            labels.append("")

    def kwargs_from_request_form(request_form):
        """calculates the needed kwargs fow wallet.createpsbt() out of a request_form"""
        # Who pays the fees?
        subtract = bool(request_form.get("subtract", False))
        subtract_from = int(request_form.get("subtract_from", 1))
        fee_options = request_form.get("fee_options")
        fee_rate = None
        if fee_options:
            if "dynamic" in fee_options:
                fee_rate = float(request_form.get("fee_rate_dynamic"))
            else:
                if request_form.get("fee_rate"):
                    fee_rate = float(request_form.get("fee_rate"))
        rbf = bool(request_form.get("rbf", False))
        # workaround for making the tests work with a dict
        if hasattr(request_form, "getlist"):
            selected_coins = request_form.getlist("coinselect")
        else:
            selected_coins = None
        rbf_tx_id = request_form.get("rbf_tx_id", "")
        kwargs = {
            "subtract": subtract,
            "subtract_from": subtract_from - 1,
            "fee_rate": fee_rate,
            "rbf": rbf,
            "selected_coins": selected_coins,
            "readonly": "estimate_fee"
            in request_form,  # determines whether the psbt gets persisted
            "rbf_edit_mode": (rbf_tx_id != ""),
        }
        return kwargs
