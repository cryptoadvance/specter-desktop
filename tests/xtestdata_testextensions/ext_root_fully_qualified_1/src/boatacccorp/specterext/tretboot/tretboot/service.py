import logging

from cryptoadvance.specter.services.service import (
    Service,
    devstatus_alpha,
    devstatus_prod,
)

# A SpecterError can be thrown and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from cryptoadvance.specter.wallet import Wallet

logger = logging.getLogger(__name__)


class TretbootService(Service):
    id = "tretboot"
    name = "Tretboot Service"
    icon = "tretboot/img/ghost.png"
    logo = "tretboot/img/tretboot_logo.jpeg"
    desc = "Where a Tretboot grows bigger."
    has_blueprint = True
    blueprint_module = "boatacccorp.specterext.tretboot.controller"
    devstatus = devstatus_alpha
    piggyback = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    # ServiceEncryptedStorage field names for this service
    # Those will end up as keys in a json-file
    SPECTER_WALLET_ALIAS = "wallet"

    @classmethod
    def get_associated_wallet(cls) -> Wallet:
        """Get the Specter `Wallet` that is currently associated with this service"""
        service_data = cls.get_current_user_service_data()
        if not service_data or cls.SPECTER_WALLET_ALIAS not in service_data:
            # Service is not initialized; nothing to do
            return
        try:
            return app.specter.wallet_manager.get_by_alias(
                service_data[cls.SPECTER_WALLET_ALIAS]
            )
        except SpecterError as e:
            logger.debug(e)
            # Referenced an unknown wallet
            # TODO: keep ignoring or remove the unknown wallet from service_data?
            return
