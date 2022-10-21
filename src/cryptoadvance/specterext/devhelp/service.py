import logging
from flask import current_app as app
from flask import render_template
from cryptoadvance.specter.services.service import Service, devstatus_alpha
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter import util
from .console import Console
import flask
import flask_login
from flask_login import current_user

logger = logging.getLogger(__name__)


class DevhelpService(Service):
    id = "devhelp"
    name = "Development Helper"
    icon = "devhelp/img/orange-wrench.png"
    logo = "devhelp/img/orange-wrench.png"
    desc = "Wrenches at work."
    has_blueprint = True
    blueprint_module = "cryptoadvance.specterext.devhelp.controller"
    devices = ["cryptoadvance.specterext.devhelp.devices.devhelpdevice"]
    devstatus = devstatus_alpha
    console = Console()
    console.updateNamespace(
        {"app": app, "flask": flask, "flask_login": flask_login, "util": util}
    )

    sort_priority = 2

    # ServiceEncryptedStorage field names for Swan
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
            # Referenced an unknown walletfrom cryptoadvance.specter.wallet import Wallet
            # TODO: keep ignoring or remove the unknown wallet from service_data?
            return

    @classmethod
    def set_associated_wallet(cls, wallet: Wallet):
        """Set the Specter `Wallet` that is currently associated with Swan auto-withdrawals"""
        cls.update_current_user_service_data({cls.SPECTER_WALLET_ALIAS: wallet.alias})

    @classmethod
    def inject_in_basejinja_body_top(cls):
        return render_template("devhelp/html_inject_in_basejinja.jinja")
