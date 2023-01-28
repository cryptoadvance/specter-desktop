import logging
import typing
from typing import List

import flask
import flask_login
import strawberry
from flask import current_app as app
from flask import render_template
from flask_login import current_user

from cryptoadvance.specter import util
from cryptoadvance.specter.services.service import Service, devstatus_alpha
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import Wallet

from . import schema as devhelp_schema
from .callbacks import my_callback
from .console import Console
from .schema import get_bookmarks

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
    # Specifying the my_callback here:
    callbacks = ["cryptoadvance.specterext.devhelp.callbacks"]
    devstatus = devstatus_alpha
    console = Console()
    console.updateNamespace(
        {"app": app, "flask": flask, "flask_login": flask_login, "util": util}
    )

    sort_priority = 2

    # ServiceEncryptedStorage field names for Swan
    SPECTER_WALLET_ALIAS = "wallet"

    def inform_world(self, msg="Hello World"):
        """Just a test method which you might want to call via the devhelper-console"""
        # Calling the self-specified callback!
        app.specter.service_manager.execute_ext_callbacks(my_callback, msg)

    def callback_my_callback(self, msg):
        """Implementing the self declared callback-method
        This is usually implemented in other extensions which depend on this one
        """
        print(msg)

    def callback_create_graphql_schema(self, field_list):
        # Add your fields to the Schema like this::
        field_list.append(strawberry.field(name="bookmarks", resolver=get_bookmarks))
        return field_list

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
