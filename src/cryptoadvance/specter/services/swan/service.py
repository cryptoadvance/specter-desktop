import datetime
import json
import logging
import pytz

from flask import current_app as app, request
from flask_babel import lazy_gettext as _
from typing import List
from cryptoadvance.specter.services.swan.client import SwanClient
from cryptoadvance.specter.specter_error import SpecterError

from cryptoadvance.specter.user import User

from ..service import Service, devstatus_prod
from cryptoadvance.specter.addresslist import Address
from cryptoadvance.specter.wallet import Wallet
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SwanService(Service):
    id = "swan"
    name = "Swan"
    icon = "swan/img/swan_icon.svg"
    logo = "swan/img/swan_logo.svg"
    desc = "Auto-withdraw to your Specter wallet"
    has_blueprint = True
    isolated_client = False
    devstatus = devstatus_prod

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
    AUTOWITHDRAWAL_ID = "autowithdrawal_id"
    AUTOWITHDRAWAL_THRESHOLD = "withdrawal_threshold"

    @classmethod
    def client(cls) -> SwanClient:
        if hasattr(cls, "_client"):
            return cls._client
        try:
            cls._client = SwanClient(
                urlparse(request.url).netloc,
                cls.get_current_user_service_data().get(cls.ACCESS_TOKEN),
                cls.get_current_user_service_data().get(cls.ACCESS_TOKEN_EXPIRES),
                cls.get_current_user_service_data().get(cls.REFRESH_TOKEN),
            )
        except Exception as e:
            raise e
        return cls._client

    @classmethod
    def is_access_token_valid(cls):
        service_data = cls.get_current_user_service_data()
        if not service_data or not service_data.get(cls.ACCESS_TOKEN_EXPIRES):
            return False
        return (
            service_data[cls.ACCESS_TOKEN_EXPIRES]
            > datetime.datetime.now(tz=pytz.utc).timestamp()
        )

    @classmethod
    def store_new_api_access_data(cls):
        new_api_data = {
            cls.ACCESS_TOKEN: cls.client().access_token,
            cls.ACCESS_TOKEN_EXPIRES: cls.client().access_token_expires,
        }
        if cls.client().refresh_token:
            new_api_data[cls.REFRESH_TOKEN] = cls.client().refresh_token
        logger.debug(f"Storing: {new_api_data}")
        cls.update_current_user_service_data(new_api_data)

    @classmethod
    def has_refresh_token(cls):
        return cls.REFRESH_TOKEN in cls.get_current_user_service_data()

    @classmethod
    def get_associated_wallet(cls) -> Wallet:
        """Get the Specter `Wallet` that is currently associated with Swan auto-withdrawals"""
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

    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """Set the Specter `Wallet` that is currently associated with Swan auto-withdrawals"""
        cls.update_current_user_service_data({cls.SPECTER_WALLET_ALIAS: wallet.alias})

    @classmethod
    def reserve_addresses(
        cls, wallet: Wallet, label: str = None, num_addresses: int = 10
    ) -> List[str]:
        """
        * Reserves addresses for Swan auto-withdrawals
        * Sets the associated Specter `Wallet` that will receive auto-withdrawals
        * Removes any existing unused reserved addresses in the previously associated `Wallet`
        * Performs matching cleanup and update on the Swan side

        Overrides base classmethod to add Swan-specific functionality & data management.
        """
        from . import client as swan_client

        # Update Addresses as reserved (aka "associated") with Swan in our Wallet
        addresses = super().reserve_addresses(
            wallet=wallet, label=label, num_addresses=num_addresses
        )

        # Clear out any prior unused reserved addresses if this is a different Wallet
        cur_wallet = cls.get_associated_wallet()
        if cur_wallet and cur_wallet != wallet:
            super().unreserve_addresses(cur_wallet)

        # Store our `Wallet` as the current one for Swan auto-withdrawals
        cls.set_associated_wallet(wallet)

        # Send the new list to Swan (DELETES any unused ones; creates a new SWAN_WALLET_ID if needed)
        swan_wallet_id = cls.client().update_autowithdrawal_addresses(
            cls.get_current_user_service_data().get(cls.SWAN_WALLET_ID),
            specter_wallet_name=wallet.name,
            specter_wallet_alias=wallet.alias,
            addresses=addresses,
        )
        logger.debug(f"Updating the Swan wallet id to {swan_wallet_id}")
        if swan_wallet_id:
            cls.update_current_user_service_data({cls.SWAN_WALLET_ID: swan_wallet_id})

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
        cls.reserve_addresses(
            wallet=wallet, num_addresses=cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS
        )

        swan_wallet_id = cls.get_current_user_service_data().get(cls.SWAN_WALLET_ID)
        # Send the autowithdrawal threshold
        resp = cls.client().set_autowithdrawal(
            swan_wallet_id, btc_threshold=btc_threshold
        )
        autowithdrawal_id = resp["item"]["id"]
        if autowithdrawal_id != cls.get_current_user_service_data().get(
            SwanService.AUTOWITHDRAWAL_ID
        ):
            cls.update_current_user_service_data(
                {
                    SwanService.AUTOWITHDRAWAL_ID: autowithdrawal_id,
                }
            )

        # Store the threshold setting in the User's service data
        cls.update_current_user_service_data(
            {SwanService.AUTOWITHDRAWAL_THRESHOLD: btc_threshold}
        )

    @classmethod
    def sync_swan_data(cls):
        """
        Called when the user completes the OAuth2 link with Swan.

        User could be:
        * A first-time Specter-Swan integration (so no local or Swan API wallet data).
        * Re-linking on a previously linked Specter instance (some/all existing data).
        * Linking a new Specter instance but had previously linked on a different Specter
            instance; the previously linked Specter wallet may or may not be present
            (need to resync data).
        """
        from . import client as swan_client

        def sync_autowithdrawal_settings(service_data):
            """
            Retrieve the autowithdrawal objs from Swan. We only care if we find one
            that matches our SWAN_WALLET_ID and has `isActive: true`.

            Otherwise clear any local autowithdrawal data.
            """
            autowithdrawal_info = cls.client().get_autowithdrawal_info()
            """
                {
                    "entity": "automaticWithdrawal",
                    "list": [
                        {
                            "id": "2026d75b-baf0-45c3-a1c6-9e17d4f7e90f",
                            "minBtcThreshold": "0.01",
                            "isActive": false,
                            "isCanceled": false,
                            "createdAt": "2022-01-07T02:14:56.070Z",
                            "walletId": "e26132e7-2e03-49b7-807b-9067aa3a8507",
                            "walletAddressId": null
                        },
                        ...,
                        { ... }
                    ]
                }
            """
            if autowithdrawal_info and "list" in autowithdrawal_info:
                swan_wallet_id = service_data.get(SwanService.SWAN_WALLET_ID)
                for entry in autowithdrawal_info["list"]:
                    if entry.get("wallet_id") == swan_wallet_id and entry.get(
                        "isActive"
                    ):
                        # Found our swan_wallet_id's active autowithdrawal!
                        logger.debug(
                            "Found swan_wallet_id's active autowithdrawal entry"
                        )
                        SwanService.update_current_user_service_data(
                            {
                                SwanService.AUTOWITHDRAWAL_ID: entry["id"],
                                SwanService.AUTOWITHDRAWAL_THRESHOLD: entry[
                                    "minBtcThreshold"
                                ],
                            }
                        )

                        # Check to make sure we have enough autowithdrawal addresses
                        SwanService.update()

                        return

            # Did not find a matching and/or active autowithdrawal
            logger.debug("No active autowithdrawal with swan_wallet_id found")

            # Clear the autowithdrawal fields from local storage and move on
            service_data.pop(SwanService.AUTOWITHDRAWAL_ID, None)
            service_data.pop(SwanService.AUTOWITHDRAWAL_THRESHOLD, None)
            SwanService.set_current_user_service_data(service_data)
            return

        service_data = cls.get_current_user_service_data()
        if SwanService.SWAN_WALLET_ID in service_data:
            # This user has previously/currently linked to Swan on this instance
            swan_wallet_id = service_data[SwanService.SWAN_WALLET_ID]
            logger.debug(f"swan_wallet_id: {swan_wallet_id}")

            # Confirm that the Swan walletId exists on the Swan side
            details = cls.client().get_wallet_details(swan_wallet_id)
            """
            {
                "entity": "wallet",
                "item": {
                    "id": "*******",
                    "isConfirmed": false,
                    "displayName": "Specter autowithdrawal to SeedSigner demo",
                    "metadata": {
                        "oidc": {
                            "clientId": "specter-dev"
                        },
                        "specter_wallet_alias": "seedsigner_demo"
                    }
                }
            }
            """
            if not details:
                # Specter's SWAN_WALLET_ID is out of sync; doesn't exist on Swan's side.
                # Clear the local SWAN_WALLET_ID and continue below to try to find one.
                logger.debug(f"swan_wallet_id {swan_wallet_id} not found on Swan")
                del service_data[SwanService.SWAN_WALLET_ID]
                cls.set_current_user_service_data(service_data)

            elif (
                "item" in details
                and "metadata" in details["item"]
                and "specter_wallet_alias" in details["item"]["metadata"]
            ):
                wallet_alias = details["item"]["metadata"]["specter_wallet_alias"]
                logger.debug(f"swan_wallet_id exists on Swan side")
                if wallet_alias in [
                    w.alias for w in app.specter.wallet_manager.wallets.values()
                ]:
                    # All is good; we've matched Swan's wallet data with a Specter `Wallet` that we recognize.
                    logger.debug(f"Found wallet_alias {wallet_alias} in Specter")
                    if wallet_alias != service_data.get(
                        SwanService.SPECTER_WALLET_ALIAS
                    ):
                        # Our local `service_data` is out of sync; update with the
                        # current Specter wallet_alias Swan is expecting.
                        logger.debug(
                            f"Updating service_data to use wallet_alias {wallet_alias}"
                        )
                        cls.update_current_user_service_data(
                            {SwanService.SPECTER_WALLET_ALIAS: wallet_alias}
                        )

                    sync_autowithdrawal_settings(service_data)

                    return
                else:
                    # Swan is out of sync with Specter; the SPECTER_WALLET_ALIAS we had
                    # been using doesn't exist on this Specter instance.
                    logger.warn(
                        f"Swan referenced an unknown wallet_alias {wallet_alias}"
                    )
                    if SwanService.SPECTER_WALLET_ALIAS in service_data:
                        # Clear the local reference to that unknown SPECTER_WALLET_ALIAS
                        del service_data[SwanService.SPECTER_WALLET_ALIAS]
                        cls.set_current_user_service_data(service_data)

        # This Specter instance has no idea if there might already be wallet data on the Swan side.
        # Fetch all Swan wallets, if any exist.
        wallet_entries = cls.client().get_wallets().get("list")
        if not wallet_entries:
            # No Swan data at all yet. Nothing to do.
            logger.debug("No wallets on the Swan side yet")
            return

        swan_wallet_id = None
        for wallet_entry in wallet_entries:
            swan_wallet_id = wallet_entry["id"]
            specter_wallet_alias = wallet_entry["metadata"].get("specter_wallet_alias")
            if specter_wallet_alias in [
                w.alias for w in app.specter.wallet_manager.wallets.values()
            ]:
                # All is good; we've matched Swan's wallet data with a Specter `Wallet` that we recognize.
                # Use this Swan walletId going forward.
                cls.update_current_user_service_data(
                    {
                        SwanService.SWAN_WALLET_ID: swan_wallet_id,
                        SwanService.SPECTER_WALLET_ALIAS: specter_wallet_alias,
                    }
                )
                logger.debug(
                    f"Found a Specter wallet that we recognize: {specter_wallet_alias}"
                )

                sync_autowithdrawal_settings(service_data)

                return

        # We didn't find a matching Specter `Wallet`. Clear out any nonsense settings in our local data.
        logger.debug(
            "Did not find any matching Specter wallets in the Swan wallet metadata"
        )
        if SwanService.SPECTER_WALLET_ALIAS in service_data:
            del service_data[SwanService.SPECTER_WALLET_ALIAS]
            SwanService.set_current_user_service_data(service_data)

        # Did we at least get a Swan walletId that we can update later?
        if swan_wallet_id:
            cls.update_current_user_service_data(
                {
                    SwanService.SWAN_WALLET_ID: swan_wallet_id,
                }
            )
            logger.debug(f"Setting swan_wallet_id to {swan_wallet_id}")

    @classmethod
    def remove_swan_integration(cls, user: User):
        # Unreserve unused addresses in all wallets
        for wallet_name, wallet in user.wallet_manager.wallets.items():
            SwanService.unreserve_addresses(wallet=wallet)

        # If an autowithdrawal setup is active, remove pending addrs from Swan
        try:
            service_data = SwanService.get_current_user_service_data()
            if service_data.get(cls.SPECTER_WALLET_ALIAS) and service_data.get(
                cls.SWAN_WALLET_ID
            ):
                # Import here to prevent circular dependency
                from . import client as swan_client

                cls.client().delete_autowithdrawal_addresses(
                    service_data[cls.SWAN_WALLET_ID]
                )
        except Exception as e:
            # Note the exception but proceed with clearing local data
            logger.exception(e)

        # Wipe the on-disk encrypted service data (refresh_token, etc)
        SwanService.set_current_user_service_data({})

        # Remove Swan from User's list of active Services
        user.remove_service(SwanService.id)

    """ ***********************************************************************
                                Update hooks overrides
    *********************************************************************** """

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
            logger.debug(
                "No associated wallet. Swan autowithdrawals are not set up yet."
            )
            return

        # Scan the Wallet for any new Swan autowithdrawals
        reserved_addresses: List[Address] = wallet.get_associated_addresses(
            service_id=cls.id, unused_only=False
        )
        for addr_obj in reserved_addresses:
            if addr_obj.used and addr_obj.label == cls.default_address_label():
                # This addr has received an autowithdrawal since we last checked
                logger.debug(
                    f"Updating address label for {json.dumps(addr_obj, indent=4)}"
                )
                wallet.setlabel(addr_obj.address, str(_("Swan autowithdrawal")))

        num_pending_autowithdrawal_addrs = len(
            [addr_obj for addr_obj in reserved_addresses if not addr_obj["used"]]
        )
        if num_pending_autowithdrawal_addrs < cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS:
            logger.debug("Need to send more addrs to Swan")
            cls.reserve_addresses(
                wallet=wallet, num_addresses=cls.MIN_PENDING_AUTOWITHDRAWAL_ADDRS
            )

    @classmethod
    def on_user_login(cls):
        cls.update()
