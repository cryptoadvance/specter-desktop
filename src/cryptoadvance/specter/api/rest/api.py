import logging
import json

import cryptoadvance.specter as specter
from cryptoadvance.specter.api.rest.base import (
    AdminResource,
    BaseResource,
    SecureResource,
    rest_resource,
)
from cryptoadvance.specter.api.security import require_admin, verify_password
from flask_restful import reqparse
from flask import current_app as app
from datetime import datetime
from ...specter_error import SpecterError

from .. import auth

logger = logging.getLogger(__name__)


@rest_resource
class ResourceSpecter(SecureResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/specter"]

    def get(self):
        specter_data = app.specter

        return_dict = {
            "data_folder": specter_data.data_folder,
            "file_config": specter_data.file_config,
            "config": specter_data.config,
            "is_configured": specter_data._is_configured,
            "is_running": specter_data._is_running,
            "info": specter_data._info,
            "network_info": specter_data._network_info,
            "device_manager_datafolder": specter_data.device_manager.data_folder,
            "devices_names": specter_data.device_manager.devices_names,
            "wallets_names": specter_data.wallet_manager.wallets_names,
            "last_update": datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
        }

        # Include alias list for easy lookup between names and alias
        # Maybe there's a better way to create this
        wallets_alias = []
        alias_name = {}
        name_alias = {}
        for wallet in return_dict["wallets_names"]:
            alias = specter_data.wallet_manager.wallets[wallet].alias
            wallets_alias.append(alias)
            alias_name[alias] = wallet
            name_alias[wallet] = alias
        return_dict["alias_name"] = alias_name
        return_dict["name_alias"] = name_alias
        return_dict["wallets_alias"] = wallets_alias
        return json.dumps(return_dict)


@rest_resource
class ResourceTXlist(SecureResource):
    """/api/v1alpha/full_txlist"""

    endpoints = ["/v1alpha/full_txlist/"]

    def get(self):
        try:
            validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs")
            idx = 0
            tx_len = 1
            tx_list = []
            while tx_len > 0:
                transactions = app.specter.wallet_manager.full_txlist(
                    idx, validate_merkle_proofs
                )
                tx_list.append(transactions)
                tx_len = len(transactions)
                idx += 1
            # Flatten the list
            flat_list = []
            for element in tx_list:
                for dic_item in element:
                    flat_list.append(dic_item)

        except SpecterError as se:
            message = "API error: %s" % se
            app.logger.error(message)
            flat_list = message
        return json.dumps(flat_list)


@rest_resource
class ResourceWallet(SecureResource):
    """/api/v1alpha/wallet_info/<wallet_alias>/"""

    endpoints = ["/v1alpha/wallet_info/<wallet_alias>/"]

    def get(self, wallet_alias):
        try:
            wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        except SpecterError as se:
            message = "API error: %s" % se
            app.logger.error(message)
            return json.dumps(message)

        wallet.get_balance()
        wallet.check_utxo()
        wallet.check_unused()

        return_dict = {}
        address_index = wallet.address_index
        validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs")

        tx_list = []
        idx = 0
        tx_len = 1
        while tx_len > 0:
            transactions = wallet.txlist(
                idx, validate_merkle_proofs=validate_merkle_proofs
            )
            tx_list.append(transactions)
            tx_len = len(transactions)
            idx += 1

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

        return safe_serialize(return_dict)
