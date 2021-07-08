import json
import logging

from cryptoadvance.specter.api.rest.base import AdminResource, rest_resource
from flask import current_app as app

from .. import auth

logger = logging.getLogger(__name__)


@rest_resource
class ResourceTXlist(AdminResource):
    """/api/v1alpha/full_txlist"""

    endpoints = ["/v1alpha/specter/full_txlist/"]

    def get(self):
        user = auth.current_user()
        wallet_manager = app.specter.user_manager.get_user(user).wallet_manager
        validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs")
        idx = 0
        tx_len = 1
        tx_list = []
        transactions = wallet_manager.full_txlist(
            fetch_transactions=False, validate_merkle_proofs=validate_merkle_proofs
        )
        tx_list.append(transactions)
        # Flatten the list
        flat_list = []
        for element in tx_list:
            for dic_item in element:
                flat_list.append(dic_item)
        return flat_list
