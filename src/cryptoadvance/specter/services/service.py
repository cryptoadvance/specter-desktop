import logging
import os
import sys
from importlib import import_module

from flask import current_app as app
from flask.blueprints import Blueprint
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.util.reflection import get_template_static_folder
from flask_babel import lazy_gettext as _
from typing import List

from .service_encrypted_storage import ServiceEncryptedStorageManager
from .service_annotations_storage import ServiceAnnotationsStorage

from cryptoadvance.specter.addresslist import Address


logger = logging.getLogger(__name__)


devstatus_alpha = "alpha"
devstatus_beta = "beta"
devstatus_prod = "prod"


class Service:
    """A base class for Services"""

    # These should be overrided in implementation classes
    id = None
    name = None
    icon = None
    logo = None
    desc = None  # TODO: rename to "description" to be explicit
    has_blueprint = True  # the default
    devstatus = devstatus_alpha

    def __init__(self, active, specter):
        if not hasattr(self, "id"):
            raise Exception(f"Service {self.__class__} needs ID")
        if not hasattr(self, "name"):
            raise Exception(f"Service {self.__class__} needs name")
        self.active = active
        self.specter = specter
        if hasattr(self.__class__, "blueprint_module"):
            import_name = self.blueprint_module
        else:
            import_name = f"cryptoadvance.specter.services.{self.id}.service"
        if self.has_blueprint:
            self.__class__.blueprint = Blueprint(
                f"{self.id}_endpoint",
                import_name,
                template_folder=get_template_static_folder("templates"),
                static_folder=get_template_static_folder("static"),
            )

            def inject_stuff():
                """Can be used in all jinja2 templates"""
                return dict(specter=app.specter, service=self)

            self.__class__.blueprint.context_processor(inject_stuff)
            # Import the controller for this service
            if hasattr(self.__class__, "blueprint_module"):
                controller_module = self.blueprint_module
            else:
                controller_module = (
                    f"cryptoadvance.specter.services.{self.id}.controller"
                )
            logger.info(f"  Loading Controller {controller_module}")
            import_module(controller_module)
            app.register_blueprint(
                self.__class__.blueprint, url_prefix=f"/svc/{self.id}"
            )

    @classmethod
    def set_current_user_service_data(cls, service_data: dict):
        ServiceEncryptedStorageManager.get_instance().set_current_user_service_data(
            service_id=cls.id, service_data=service_data
        )

    @classmethod
    def update_current_user_service_data(cls, service_data: dict):
        ServiceEncryptedStorageManager.get_instance().update_current_user_service_data(
            service_id=cls.id, service_data=service_data
        )

    @classmethod
    def get_current_user_service_data(cls) -> dict:
        return (
            ServiceEncryptedStorageManager.get_instance().get_current_user_service_data(
                service_id=cls.id
            )
        )

    @classmethod
    def get_blueprint_name(cls):
        return f"{cls.id}_endpoint"

    @classmethod
    def default_address_label(cls):
        # Have to str() it; can't pass a LazyString to json serializer
        return str(_("Reserved for {}").format(cls.name))

    @classmethod
    def reserve_address(cls, wallet: Wallet, address: str, label: str = None):
        # Mark an Address in a persistent way as being reserved by a Service
        if not label:
            label = cls.default_address_label()
        wallet.associate_address_with_service(
            address=address, service_id=cls.id, label=label
        )

    @classmethod
    def reserve_addresses(
        cls,
        wallet: Wallet,
        label: str = None,
        num_addresses: int = 10,
        annotations: dict = None,
    ) -> List[str]:
        """
        Reserve n unused addresses but leave a gap between each one so that this reserved
        range never causes an address gap in the wallet (e.g. if you reserve ten in a
        row it's possible that some wallet software will miss a new tx on the 11th
        address).

        If `label` is not provided, we use Service.default_address_label().

        Optional `annotations` data can be attached to each Address being reserved.
        """
        # Track Service-related addresses in ServiceAnnotationsStorage
        if annotations:
            annotations_storage = ServiceAnnotationsStorage(
                service_id=cls.id, wallet=wallet
            )

        addresses = []
        start_index = wallet.address_index + 1
        for i in range(start_index, start_index + (2 * num_addresses), 2):
            address = wallet.get_address(i)

            # Mark an Address in a persistent way as being reserved by a Service
            cls.reserve_address(wallet=wallet, address=address)

            addresses.append(address)

            if annotations:
                annotations_storage.set_addr_annotations(
                    addr=address, annotations=annotations, autosave=False
                )
        if annotations:
            annotations_storage.save()

        return addresses

    @classmethod
    def unreserve_addresses(cls, wallet: Wallet):
        """
        Clear out Services-related data from any unused Addresses, but leave already-used
        Addresses as-is.
        """
        annotations_storage = ServiceAnnotationsStorage(
            service_id=cls.id, wallet=wallet
        )
        addrs = wallet.get_associated_addresses(service_id=cls.id, unused_only=True)
        for addr_obj in addrs:
            wallet.deassociate_address(addr_obj["address"])
            annotations_storage.remove_addr_annotations(
                addr_obj.address, autosave=False
            )
        annotations_storage.save()

    # def is_active(self):
    #     return self.active

    # def set_active(self, value):
    #     self.active = value

    @classmethod
    def update(self):
        """
        Called by backend periodic process to keep Service in sync with any remote
        data (e.g. fetching the latest data from an external API).
        """
        logger.info(f"update() not implemented / not necessary for Service {self.id}")

    """ ***********************************************************************
                                    Update hooks
    *********************************************************************** """

    @classmethod
    def on_user_login(cls):
        pass
