import datetime
import logging
import pytz

from flask import current_app as app
from flask_babel import lazy_gettext as _
from typing import List

from ..service import Service, devstatus_beta
from cryptoadvance.specter.addresslist import Address
from cryptoadvance.specter.wallet import Wallet

logger = logging.getLogger(__name__)



class SwanService(Service):
    id = "swan"
    name = "Swan"
    icon = "img/swan_icon.svg"
    logo = "img/swan_logo.svg"
    desc = "Auto-withdraw to your Specter wallet"
    has_blueprint = True
    devstatus = devstatus_beta

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 1

    # Service-specific constants
    MIN_PENDING_AUTOWITHDRAWAL_ADDRS = 10


    @property
    def is_access_token_valid(self):
        api_data = self.get_current_user_service_data()
        if not api_data or not api_data.get("expires"):
            return False
        
        return datetime.fromtimestamp(api_data["expires"]) > datetime.datetime.now(tz=pytz.utc)

    @classmethod
    def get_associated_wallet(cls) -> Wallet:
        service_data = cls.get_current_user_service_data()
        if not service_data or "wallet" not in service_data:
            # Service is not initialized; nothing to do
            return
        
        return app.specter.wallet_manager.get_by_alias(service_data["wallet"])


    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """
            Configures the Service to use the specified Wallet to receive Swan
            autowithdrawals. Removes any unused reserved addresses if this is a different
            wallet.
        """
        service_data = cls.get_current_user_service_data()
        if "wallet" in service_data and service_data["wallet"] != wallet.alias:
            # We have to remove the current Wallet (and its pending autowithdrawal addrs)
            super().unreserve_addresses(wallet)
        
        service_data["wallet"] = wallet.alias
        cls.update_current_user_service_data(service_data)


    @classmethod
    def update(cls):
        """
            * Check for autowithdrawals paid to addrs reserved for Swan.
            * Add more pending autowithdrawal addrs if we're under the threshold.
        """
        # Which Wallet has been configured to receive Swan autowithdrawals?
        wallet = cls.get_associated_wallet()
        if not wallet:
            # Swan autowithdrawals to Specter aren't set up yet; nothing to do.
            return

        # Scan the Wallet for any new Swan autowithdrawals
        reserved_addresses: List[Address] = wallet.get_reserved_addresses(service_id=cls.id, unused_only=False)
        for addr_obj in reserved_addresses:
            if addr_obj["used"] and addr_obj["label"] == cls.default_address_label:
                # This addr has received an autowithdrawal since we last checked
                addr_obj.set_label(str(_("Swan autowithdrawal")))
        
        num_pending_autowithdrawal_addrs = len([addr_obj for addr_obj in reserved_addresses if not addr_obj["used"]])
        if num_pending_autowithdrawal_addrs < cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS:
            logger.debug("Need to send more addrs to Swan")
            cls.reserve_addresses(wallet)


    @classmethod
    def reserve_addresses(cls, wallet: Wallet, label: str = None, num_addresses: int = 10) -> List[str]:
        """
            Overrides base classmethod to add Swan-specific Wallet management and Swan
            API call.
        """
        # Import here to avoid circular import issues
        from . import api as swan_api

        # Update Addresses as reserved/associated with Swan in our Wallet
        addresses = super().reserve_addresses(wallet=wallet, label=label, num_addresses=num_addresses)

        # Set the wallet as the currently configured Wallet for Swan; Also clears out any
        #   prior unused reserved addresses if this is a different Wallet. 
        cls.set_associated_wallet(wallet)

        # Send the address list update to the Swan API
        swan_label = _("Specter autowithdrawal to {}".format(wallet.name))
        swan_api.update_autowithdrawal_addresses(addresses=addresses, label=swan_label)

        return addresses
