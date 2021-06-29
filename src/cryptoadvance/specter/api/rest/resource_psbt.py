import logging
import json

from .base import (
    SecureResource,
    rest_resource,
)
from flask_restful import abort
from flask import current_app as app, request
from ...wallet import Wallet
from ...util.fee_estimation import get_fees
from ...util.psbt_creator import PsbtCreator

from .. import auth

from ...specter_error import SpecterError

logger = logging.getLogger(__name__)


@rest_resource
class ResourcePsbt(SecureResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/wallets/<wallet_alias>/psbt"]

    def get(self, wallet_alias):
        # ToDo: check whether the user has access to the wallet
        user = auth.current_user()
        try:
            wallet: Wallet = app.specter.user_manager.get_user(
                user
            ).wallet_manager.get_by_alias(wallet_alias)
            pending_psbts = wallet.pending_psbts
            return {"result": pending_psbts or []}
        except SpecterError as se:
            logger.error(se)
            if str(se).startswith(f"Wallet {wallet_alias} does not exist!"):
                return abort(403, message=f"Wallet {wallet_alias} does not exist")
            logger.error(se)
            return abort(500)
        except Exception as e:
            app.logger.exception(e)
            return abort(
                500,
                message="Can't tell you the reason of the issue. Please check the logs",
            )

    def post(self, wallet_alias):
        user = auth.current_user()
        try:
            wallet: Wallet = app.specter.user_manager.get_user(
                user
            ).wallet_manager.get_by_alias(wallet_alias)
            logger.debug(f"Got a post request for creating a psbt: {request.json}")
            psbt_creator = PsbtCreator(
                app.specter, wallet, "json", request_json=request.json
            )
            psbt_creator.create_psbt(wallet)
            return {"result": psbt_creator.psbt}
        except SpecterError as se:
            logger.error(se)
            if str(se).startswith(f"Wallet {wallet_alias} does not exist!"):
                return abort(403, message=f"Wallet {wallet_alias} does not exist")
            if str(se).endswith(
                "does not have sufficient funds to make the transaction."
            ):
                logger.error(
                    f"Available Walletbalance for {wallet_alias}: {wallet.get_balance().get('available')}"
                )
                return abort(
                    412,
                    message=f"Wallet does not have sufficient funds to make the transaction.",
                )
            return abort(500)
        except Exception as e:
            app.logger.exception(e)
            return abort(
                500,
                message="Can't tell you the reason of the issue. Please check the logs",
            )
