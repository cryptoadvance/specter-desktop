import logging
import os
from importlib import import_module

from flask import current_app as app
from flask.blueprints import Blueprint
from cryptoadvance.specter.wallet import Wallet
from flask_babel import lazy_gettext as _
from typing import List

from .service_apikey_storage import ServiceApiKeyStorageManager
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
    desc = None     # TODO: rename to "description" to be explicit
    has_blueprint = True  # the default
    devstatus = devstatus_alpha

    def __init__(self, active, specter):
        if not hasattr(self, "id"):
            raise Exception(f"Service {self.__class__} needs ID")
        if not hasattr(self, "name"):
            raise Exception(f"Service {self.__class__} needs name")
        self.active = active
        self.specter = specter
        if self.has_blueprint:
            self.__class__.blueprint = Blueprint(
                f"{self.id}_endpoint",
                f"cryptoadvance.specter.services.{self.id}.manifest",  # To Do: move to subfolder
                template_folder="templates",
                static_folder="static",
            )

            def inject_stuff():
                """Can be used in all jinja2 templates"""
                return dict(specter=app.specter, service=self)

            self.__class__.blueprint.context_processor(inject_stuff)
            # Import the controller for this service
            import_module(f"cryptoadvance.specter.services.{self.id}.controller")
            app.register_blueprint(self.__class__.blueprint, url_prefix=f"/svc/{self.id}")

    @classmethod
    def set_current_user_api_data(cls, api_data: dict):
        ServiceApiKeyStorageManager.get_instance().set_current_user_api_data(service_id=cls.id, api_data=api_data)

    @classmethod
    def update_current_user_api_data(cls, api_data: dict):
        ServiceApiKeyStorageManager.get_instance().update_current_user_api_data(service_id=cls.id, api_data=api_data)

    @classmethod
    def get_current_user_api_data(cls) -> dict:
        return ServiceApiKeyStorageManager.get_instance().get_current_user_api_data(service_id=cls.id)

    @classmethod
    def get_blueprint_name(cls):
        return f"{cls.id}_endpoint"
    

    @classmethod
    def default_address_label(cls):
        # Have to str() it; can't pass a LazyString to json serializer
        return str(_(f"Reserved for {cls.name}"))


    @classmethod
    def reserve_address(cls, wallet: Wallet, address: str, label: str = None):
        # Mark an Address in a persistent way as being reserved by a Service
        if not label:
            label = cls.default_address_label()
        wallet.reserve_address_for_service(address=address, service_id=cls.id, label=label)


    @classmethod
    def reserve_addresses(cls, wallet: Wallet, label: str = None, num_addresses: int = 5) -> List[tuple]:
        """
        Reserve n addresses but leave a gap between each one so that this reserved range
        never causes an address gap in the wallet (e.g. if you reserve ten in a row it's
        possible that some wallet software will miss a new tx on the 11th address).

        If `label` is not provided, we use Service.default_address_label().

        Returns a list of (address:str, index:int) tuples.
        """
        # Track Service-related addresses in ServiceAnnotationsStorage
        annotations_storage = ServiceAnnotationsStorage(
            service_id=cls.id, wallet=wallet
        )

        addresses = []
        start_index = wallet.address_index + 1
        for i in range(start_index, start_index + (2 * num_addresses), 2):
            address = wallet.get_address(i)

            # Mark an Address in a persistent way as being reserved by a Service
            cls.reserve_address(wallet=wallet, address=address)

            addresses.append((address, i))
        
            # TODO: What annotations do we want to save? Date reserved? Nothing yet?
            annotations_storage.set_addr_annotations(addr=address, annotations={}, autosave=False)
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
        addrs = wallet.get_reserved_addresses(service_id=cls.id, unused_only=True)
        for addr_obj in addrs:
            wallet.unreserve_address(addr_obj["address"])
            annotations_storage.remove_addr_annotations(addr_obj.address, autosave=False)
        annotations_storage.save()


    def is_active(self):
        return self.active


    def set_active(self, value):
        self.active = value
