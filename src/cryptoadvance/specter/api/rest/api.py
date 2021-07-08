import logging
import json

import cryptoadvance.specter as specter
from ...wallet import Wallet
from .base import (
    SecureResource,
    rest_resource,
)
from ..security import require_admin, verify_password
from flask_restful import abort
from flask import current_app as app
from datetime import datetime
from ...specter_error import SpecterError

from ...util.fee_estimation import get_fees

from .. import auth
from .resource_healthz import ResourceLiveness, ResourceReadyness
from .resource_psbt import ResourcePsbt
from .resource_specter import ResourceSpecter
from .resource_txlist import ResourceTXlist

logger = logging.getLogger(__name__)


@rest_resource
class ResourceWallet(SecureResource):

    endpoints = ["/v1alpha/wallets/<wallet_alias>/"]

    def get(self, wallet_alias):
        user = auth.current_user()
        try:
            wallet: Wallet = app.specter.user_manager.get_user(
                user
            ).wallet_manager.get_by_alias(wallet_alias)
        except SpecterError as se:
            logger.error(se)
            if str(se).startswith(f"Wallet {wallet_alias} does not exist!"):
                return abort(403, message=f"Wallet {wallet_alias} does not exist")
            logger.error(se)
            return abort(500)

        wallet.get_balance()
        wallet.check_utxo()
        wallet.check_unused()

        return_dict = {}
        address_index = wallet.address_index
        validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs")
        tx_list = []
        idx = 0
        tx_len = 1
        transactions = app.specter.wallet_manager.full_txlist(
            fetch_transactions=False, validate_merkle_proofs=validate_merkle_proofs
        )
        tx_list.append(transactions)

        # Flatten the list
        flat_list = []
        for element in tx_list:
            for dic_item in element:
                flat_list.append(dic_item)

        # Check if scanning
        scan = wallet.rescan_progress
        return_dict[wallet_alias] = wallet.__dict__
        return_dict["txlist"] = flat_list
        return_dict["scan"] = scan
        return_dict["address_index"] = address_index
        return_dict["utxo"] = wallet.utxo

        # Serialize only objects that are json compatible
        # This will exclude classes and methods
        def safe_serialize(obj):
            def default(o):
                return f"{type(o).__qualname__}"

            return json.dumps(obj, default=default)

        return json.loads(safe_serialize(return_dict))
