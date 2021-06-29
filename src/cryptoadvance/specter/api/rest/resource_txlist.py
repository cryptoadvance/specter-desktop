import logging
import json
from cryptoadvance.specter.api.rest.base import (
    AdminResource,
    rest_resource,
)
from flask import current_app as app
from ...specter_error import SpecterError

from ...util.fee_estimation import get_fees

logger = logging.getLogger(__name__)


@rest_resource
class ResourceTXlist(AdminResource):
    """/api/v1alpha/full_txlist"""

    endpoints = ["/v1alpha/specter/full_txlist/"]

    def get(self):
        try:
            validate_merkle_proofs = app.specter.config.get("validate_merkle_proofs")
            idx = 0
            tx_len = 1
            tx_list = []
            transactions = app.specter.wallet_manager.full_txlist(
                fetch_transactions=False, validate_merkle_proofs=validate_merkle_proofs
            )
            tx_list.append(transactions)
            # Flatten the list
            flat_list = []
            for element in tx_list:
                for dic_item in element:
                    flat_list.append(dic_item)

        except SpecterError as se:
            message = "API error: %s" % se
            app.logger.error(message)
            flat_list = message
        return flat_list
