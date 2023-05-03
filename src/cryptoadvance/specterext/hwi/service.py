import logging

from flask import current_app as app
from flask import redirect, url_for
from flask_apscheduler import APScheduler

from cryptoadvance.specter.services.service import (
    Extension,
    Service,
    devstatus_alpha,
    devstatus_beta,
    devstatus_prod,
)

# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specterext.hwi.hwi_rpc_binary import HWIBinaryBridge

from .binary_downloader import BinaryDownloader
from .hwi_server import hwi_server

logger = logging.getLogger(__name__)


class HwiService(Extension):
    id = "hwi"
    name = "Hwi Service"
    icon = "hwi/img/ghost.png"
    logo = "hwi/img/logo.jpeg"
    desc = "Where a hwi grows bigger."
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.hwi.controller"

    devstatus = devstatus_beta
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    # ServiceEncryptedStorage field names for this service
    # Those will end up as keys in a json-file
    SPECTER_WALLET_ALIAS = "wallet"

    def callback_specter_added_to_flask_app(self):
        if app.config["HWI_RPC_IMPL"] == "lib":
            # As we're planning to remove the pypi-dependency to hwi, we'll import that like this
            # to avoid dependency issues which cannot be resolved:
            from cryptoadvance.specterext.hwi.hwi_rpc_hwilib import HWILibBridge

            logger.info("Using HWI Library")
            app.specter.hwi = HWILibBridge()
        elif app.config["HWI_RPC_IMPL"] == "bin":
            logger.info("Using HWI Binary")
            downloader = BinaryDownloader.from_github_repo(
                app.specter,
                hash=app.config["HWI_BIN_HASH"],
                version=app.config["HWI_BIN_VERSION"],
            )
            app.specter.hwi = HWIBinaryBridge(downloader.get_executable)

        app.register_blueprint(hwi_server, url_prefix="/hwi")
        app.csrf.exempt(hwi_server)
        if (
            app.config.get("OPERATIONAL_MODE", "specter") == "hwibridge"
        ):  # default is specter -> do not activate

            @app.route("/", methods=["GET"])
            def index():
                return redirect(url_for("hwi_server.hwi_bridge_settings"))

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

    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """Set the Specter `Wallet` that is currently associated with this Service"""
        cls.update_current_user_service_data({cls.SPECTER_WALLET_ALIAS: wallet.alias})
