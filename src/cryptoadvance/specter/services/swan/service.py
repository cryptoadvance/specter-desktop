import datetime
import json
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


    @classmethod
    def is_access_token_valid(cls):
        service_data = cls.get_current_user_service_data()
        if not service_data or not service_data.get("expires"):
            return False
        return service_data["expires"] > datetime.datetime.now(tz=pytz.utc).timestamp()

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
            Reserves addresses for the Service, sets the associated Wallet, and
            removes any prior reserved addresses in the previous associated Wallet.

            Overrides base classmethod to add Swan-specific Wallet management.
        """
        # Update Addresses as reserved/associated with Swan in our Wallet
        addresses = super().reserve_addresses(wallet=wallet, label=label, num_addresses=num_addresses)

        # Set the wallet as the currently configured Wallet for Swan; Also clears out any
        #   prior unused reserved addresses if this is a different Wallet. 
        cls.set_associated_wallet(wallet)

        return addresses


    @classmethod
    def sync_swan_data(cls):
        from . import api as swan_api
        """
        Called when the user completes the OAuth2 link with Swan.

        Specter data:
        * ServiceEncryptedStorage:
            - "swan_wallet_id": Swan API's internal notion of a wallet, keyed on `walletId`
            - "wallet": Specter Wallet.alias that's currently configured to receive auto-withdrawals
        
        Swan API data:
        * `/wallets`
            - "walletId": Should be the same as "swan_wallet_id" above.
            - "metadata: {
                "specter_wallet_alias": Should be the same as "wallet" (Specter Wallet.alias) above
            }

        User could be:
        * A first-time Specter-Swan integration (so no local or Swan API wallet data)
        * Re-linking on a previously linked Specter instance (some/all existing data)
        * Linking a new Specter instance but had previously linked on a different Specter instance; the previously linked Specter wallet may or may not be present (need to resync data)
        """
        service_data = cls.get_current_user_service_data()
        if "swan_wallet_id" in service_data:
            # This user has previously/currently linked to Swan on this instance
            swan_wallet_id = service_data.get("swan_wallet_id")

            # Confirm that the Swan walletId exists
            details = swan_api.get_wallet_details(swan_wallet_id)
            if details and "item" in details and "metadata" in details["item"] and "specter_wallet_alias" in details["item"]["metadata"]:
                wallet_alias = details["item"]["metadata"]["specter_wallet_alias"]
                if wallet_alias in app.specter.wallet_manager.wallets:
                    # All is good; we've matched Swan's wallet data with a Specter Wallet that we recognize.
                    return
                else:
                    # Swan is out of sync with Specter; the Wallet.alias we had been using no longer exists.
                    # TODO: Alert the user and route them to settings to select a new Wallet?
                    raise Exception(f"Swan configured to send to unknown wallet: {wallet_alias}")
            else:
                # Specter's `swan_wallet_id` is out of sync; doesn't exist on Swan's side
                del service_data["swan_wallet_id"]
                cls.set_current_user_service_data(service_data)
        else:
            # This Specter instance has no idea if there might already be Wallet data on the Swan side
            pass

