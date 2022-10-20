import logging
import base64
from json import dumps

from .base import (
    SecureResource,
    rest_resource,
)

from flask import current_app as app, request, Response
from ...wallet import Wallet
from ...commands.psbt_creator import PsbtCreator
from ...specter_error import SpecterError
from .. import token_auth

logger = logging.getLogger(__name__)


@rest_resource
class ResourcePsbt(SecureResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/wallets/<wallet_alias>/psbt"]

    def get(self, wallet_alias):
        user = token_auth.current_user()
        wallet_manager = app.specter.user_manager.get_user(user).wallet_manager
        # Check that the wallet belongs to the user from Basic Auth
        try:
            wallet = wallet_manager.get_by_alias(wallet_alias)
        except SpecterError as se:
            # ToDo: Be more specific here. How do we know that this SpecterError is a fit to that message?
            logger.warning(
                f"User user {user} denied access to {wallet_alias} because of {se}"
            )
            error_message = dumps(
                {"message": "The wallet does not belong to the user in the request."}
            )
            return Response(error_message, 403)
        pending_psbts = wallet.pending_psbts_dict()
        return {"result": pending_psbts or {}}

    def post(self, wallet_alias):
        user = token_auth.current_user()
        wallet: Wallet = app.specter.user_manager.get_user(
            user
        ).wallet_manager.get_by_alias(wallet_alias)
        logger.debug(f"Got a post request for creating a psbt: {request.json}")
        psbt_creator = PsbtCreator(
            app.specter, wallet, "json", request_json=request.json
        )
        psbt = psbt_creator.create_psbt(wallet)
        return {"result": psbt}
