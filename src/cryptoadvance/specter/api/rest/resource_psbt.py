import logging

from .base import (
    SecureResource,
    rest_resource,
)
from flask import current_app as app, request
from ...wallet import Wallet
from ...util.psbt_creator import PsbtCreator

from .. import auth

logger = logging.getLogger(__name__)


@rest_resource
class ResourcePsbt(SecureResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/wallets/<wallet_alias>/psbt"]

    def get(self, wallet_alias):
        # ToDo: check whether the user has access to the wallet
        user = auth.current_user()
        wallet: Wallet = app.specter.user_manager.get_user(
            user
        ).wallet_manager.get_by_alias(wallet_alias)
        pending_psbts = wallet.pending_psbts
        return {"result": pending_psbts or []}

    def post(self, wallet_alias):
        user = auth.current_user()
        wallet: Wallet = app.specter.user_manager.get_user(
            user
        ).wallet_manager.get_by_alias(wallet_alias)
        logger.debug(f"Got a post request for creating a psbt: {request.json}")
        psbt_creator = PsbtCreator(
            app.specter, wallet, "json", request_json=request.json
        )
        psbt_creator.create_psbt(wallet)
        return {"result": psbt_creator.psbt}
