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

    # ServiceEncryptedStorage field names for Swan
    SPECTER_WALLET_ALIAS = "wallet"
    SWAN_WALLET_ID = "swan_wallet_id"
    ACCESS_TOKEN = "access_token"
    ACCESS_TOKEN_EXPIRES = "expires"
    REFRESH_TOKEN = "refresh_token"
    AUTOWITHDRAWAL_THRESHOLD = "withdrawal_threshold"


    @classmethod
    def is_access_token_valid(cls):
        service_data = cls.get_current_user_service_data()
        if not service_data or not service_data.get(cls.ACCESS_TOKEN_EXPIRES):
            return False
        return service_data[cls.ACCESS_TOKEN_EXPIRES] > datetime.datetime.now(tz=pytz.utc).timestamp()


    # TODO: Shouldn't need to check this after exiting Beta
    @classmethod
    def has_refresh_token(cls):
        return cls.REFRESH_TOKEN in cls.get_current_user_service_data()


    @classmethod
    def get_associated_wallet(cls) -> Wallet:
        """ Get the Specter `Wallet` that is currently associated with Swan auto-withdrawals """
        service_data = cls.get_current_user_service_data()
        if not service_data or cls.SPECTER_WALLET_ALIAS not in service_data:
            # Service is not initialized; nothing to do
            return
        return app.specter.wallet_manager.get_by_alias(service_data[cls.SPECTER_WALLET_ALIAS])


    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """ Set the Specter `Wallet` that is currently associated with Swan auto-withdrawals """
        cls.update_current_user_service_data({cls.SPECTER_WALLET_ALIAS: wallet.alias})



    @classmethod
    def reserve_addresses(cls, wallet: Wallet, label: str = None, num_addresses: int = 10) -> List[str]:
        """
            * Reserves addresses for Swan auto-withdrawals
            * Sets the associated Specter `Wallet` that will receive auto-withdrawals
            * Removes any existing unused reserved addresses in the previously associated `Wallet`
            * Performs matching cleanup and update on the Swan side

            Overrides base classmethod to add Swan-specific functionality & data management.
        """
        from . import client as swan_client
        # Update Addresses as reserved (aka "associated") with Swan in our Wallet
        addresses = super().reserve_addresses(wallet=wallet, label=label, num_addresses=num_addresses)

        # Clear out any prior unused reserved addresses if this is a different Wallet
        cur_wallet = cls.get_associated_wallet()
        if cur_wallet and cur_wallet != wallet:
            super().unreserve_addresses(cur_wallet)

        # Store our `Wallet` as the current one for Swan auto-withdrawals
        cls.set_associated_wallet(wallet)

        # Send the new list to Swan (DELETES any unused ones; creates a new SWAN_WALLET_ID if needed)
        swan_client.update_autowithdrawal_addresses(specter_wallet_name=wallet.name, specter_wallet_alias=wallet.alias, addresses=addresses)

        return addresses


    @classmethod
    def set_autowithdrawal_settings(cls, wallet: Wallet, btc_threshold: str):
        """
            btc_threshold: "0", "0.01", "0.025", or "0.05"

            Performs a lot of maintenance behind the scenes in order to keep Specter's
            internal data in sync (e.g. resetting previously reserved addresses) and the same
            in the api to keep Swan's notion of a wallet and list of addrs in sync.
        """
        from . import client as swan_client

        # Reserve auto-withdrawal addresses for this Wallet; clear out an unused ones in a prior wallet
        cls.reserve_addresses(wallet=wallet, num_addresses=cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS)

        # Send the autowithdrawal threshold
        swan_client.set_autowithdrawal(btc_threshold=btc_threshold)



    @classmethod
    def sync_swan_data(cls):
        """
        Called when the user completes the OAuth2 link with Swan.

        User could be:
        * A first-time Specter-Swan integration (so no local or Swan API wallet data)
        * Re-linking on a previously linked Specter instance (some/all existing data)
        * Linking a new Specter instance but had previously linked on a different Specter instance; the previously linked Specter wallet may or may not be present (need to resync data)
        """
        from . import client as swan_client

        service_data = cls.get_current_user_service_data()
        if cls.SWAN_WALLET_ID in service_data:
            # This user has previously/currently linked to Swan on this instance
            swan_wallet_id = service_data.get(SwanService.SWAN_WALLET_ID)

            # Confirm that the Swan walletId exists
            details = swan_client.get_wallet_details(swan_wallet_id)
            if details and "item" in details and "metadata" in details["item"] and "specter_wallet_alias" in details["item"]["metadata"]:
                wallet_alias = details["item"]["metadata"]["specter_wallet_alias"]
                if wallet_alias in app.specter.wallet_manager.wallets:
                    # All is good; we've matched Swan's wallet data with a Specter `Wallet` that we recognize.
                    if wallet_alias != service_data.get(SwanService.SPECTER_WALLET_ALIAS):
                        cls.update_current_user_service_data({SwanService.SPECTER_WALLET_ALIAS: wallet_alias})
                    return
                else:
                    # Swan is out of sync with Specter; the SPECTER_WALLET_ALIAS we had
                    # been using doesn't exist on this Specter instance.
                    # TODO: Alert the user and route them to settings to select a new Wallet?
                    raise Exception(f"Swan configured to send to unknown wallet: {wallet_alias}.")
            else:
                # Specter's `swan_wallet_id` is out of sync; doesn't exist on Swan's side.
                # Clear the local SPECTER_WALLET_ALIAS and continue below to try to find one.
                del service_data[SwanService.SWAN_WALLET_ID]
                cls.set_current_user_service_data(service_data)

        # This Specter instance has no idea if there might already be wallet data on the Swan side.
        # Fetch all Swan wallets, if any exist. 
        wallet_entries = swan_client.get_wallets().get("list")
        if not wallet_entries:
            # No Swan data at all yet. Nothing to do.
            return

        swan_wallet_id = None
        for wallet_entry in wallet_entries:
            swan_wallet_id = wallet_entry["id"]
            specter_wallet_alias = wallet_entry["metadata"].get("specter_wallet_alias")
            if specter_wallet_alias in app.specter.wallet_manager.wallets:
                # All is good; we've matched Swan's wallet data with a Specter `Wallet` that we recognize.
                # Use this Swan walletId going forward.
                cls.update_current_user_service_data({
                    SwanService.SWAN_WALLET_ID: swan_wallet_id,
                    SwanService.SPECTER_WALLET_ALIAS: specter_wallet_alias,
                })
                return
        
        # We didn't find a matching Specter `Wallet`. Clear out any nonsense settings in our local data.
        if SwanService.SPECTER_WALLET_ALIAS in service_data:
            del service_data[SwanService.SPECTER_WALLET_ALIAS]
            SwanService.set_current_user_service_data(service_data)

        # Did we at least get a Swan walletId that we can update later?
        if swan_wallet_id:
            cls.update_current_user_service_data({
                SwanService.SWAN_WALLET_ID: swan_wallet_id,
            })



    @classmethod
    def update(cls):
        """
            Periodic or at-login call to check our Swan address status and send more when
            needed.
            * Check for autowithdrawals paid to addrs reserved for Swan.
            * Add more pending autowithdrawal addrs if we're under the threshold.
        """
        # Which Specter `Wallet` has been configured to receive Swan autowithdrawals?
        wallet = cls.get_associated_wallet()
        if not wallet:
            # Swan autowithdrawals to Specter aren't set up yet; nothing to do.
            logger.debug("No associated wallet. Swan autowithdrawals are not set up yet.")
            return

        # Scan the Wallet for any new Swan autowithdrawals
        reserved_addresses: List[Address] = wallet.get_associated_addresses(service_id=cls.id, unused_only=False)
        for addr_obj in reserved_addresses:
            if addr_obj["used"] and addr_obj["label"] == cls.default_address_label:
                # This addr has received an autowithdrawal since we last checked
                logger.debug(f"Updating address label for {json.dumps(addr_obj, indent=4)}")
                addr_obj.set_label(str(_("Swan autowithdrawal")))
        
        num_pending_autowithdrawal_addrs = len([addr_obj for addr_obj in reserved_addresses if not addr_obj["used"]])
        if num_pending_autowithdrawal_addrs < cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS:
            from . import client as swan_client
            logger.debug("Need to send more addrs to Swan")

            # TODO: In Beta we can't assume we have a refresh_token; remove these two lines once we have a refresh_token
            if not cls.has_refresh_token() and num_pending_autowithdrawal_addrs <= 2:
                raise swan_client.SwanApiRefreshTokenException("We don't have a refresh_token")

            cls.reserve_addresses(wallet=wallet, num_addresses=cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS)

