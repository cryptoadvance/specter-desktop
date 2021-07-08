import logging

from cryptoadvance.specter.api.rest.base import (
    AdminResource,
    rest_resource,
)
from flask import current_app as app
from datetime import datetime

logger = logging.getLogger(__name__)


@rest_resource
class ResourceSpecter(AdminResource):
    """/api/v1alpha/specter"""

    endpoints = ["/v1alpha/specter"]

    def get(self):
        specter_data = app.specter

        return_dict = {
            "data_folder": specter_data.data_folder,
            "config": specter_data.config,
            "info": specter_data.info,
            "network_info": specter_data.network_info,
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
        return return_dict
