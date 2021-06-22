import logging
import json

from cryptoadvance.specter.api.rest.base import (
    SecureResource,
    rest_resource,
)
from flask_restful import reqparse, abort
from flask import current_app as app
from ...wallet import Wallet
from ...util.fee_estimation import get_fees

from .. import auth

from ...specter_error import SpecterError

logger = logging.getLogger(__name__)

parser = reqparse.RequestParser()
parser.add_argument("address", help="the address to send the funds to", required=True)
parser.add_argument("amount", help="the amount to send", required=True)


@rest_resource
class ResourcePsbt(SecureResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/wallets/<wallet_alias>/psbt"]

    def get(self, wallet_alias):
        # ToDo: check whether the user has access to the wallet
        user = auth.current_user()
        logger.debug(f"User: {user}")
        try:
            wallet: Wallet = app.specter.user_manager.get_user(
                user
            ).wallet_manager.get_by_alias(wallet_alias)
            pending_psbts = wallet.pending_psbts
            return pending_psbts or []
        except SpecterError as se:
            logger.error(f"while psbt-api-call: {se}")
            return abort(403)
        except Exception as e:
            logger.error(e)
            logger.debug(
                f" all wallets: {app.specter.user_manager.get_user(user).wallet_manager.wallets_names}"
            )
            return abort(500)

    def post(self, wallet_alias):
        try:
            wallet: Wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
            data = parser.parse_args()

            addresses = [data["address"]]
            amounts = [data["amount"]]
            fee_rate = get_fees(app.specter, app.config)

            psbt = wallet.createpsbt(
                addresses,
                amounts,
                fee_rate=fee_rate,
            )
            if psbt is None:
                err = "Probably you don't have enough funds, or something else..."

        except Exception as e:
            err = e
            app.logger.error(e)
            return {"result": "error"}
        return {"result": "ok"}
