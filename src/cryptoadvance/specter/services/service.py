import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from flask import current_app as app, url_for
from flask.blueprints import Blueprint
from flask_babel import lazy_gettext as _

from .service_apikey_storage import ServiceApiKeyStorageManager
from .service_annotations_storage import ServiceAnnotationsStorage

logger = logging.getLogger(__name__)


devstatus_alpha = "alpha"
devstatus_beta = "beta"
devstatus_prod = "prod"


class Service:
    """A BaseClass for Services"""

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
            self.init_controller()

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
    def reserve_addresses(cls, wallet, label: str = None, num_addresses: int = 5):
        """
        Reserve n addresses but leave a gap between each one so that this reserved range
        never causes an address gap in the wallet (e.g. if you reserve ten in a row it's
        possible that some wallet software will miss a new tx on the 11th address).

        If `label` is not provided, we'll use "Reserved for {Service.name}"
        """
        print(f"Service cls.id: {cls.id}")
        # Track Service-related addresses in ServiceAnnotationsStorage
        annotations_storage = ServiceAnnotationsStorage(
            service_id=cls.id, wallet=wallet
        )

        if not label:
            label = str(_(f"Reserved for {cls.name}"))
        start_index = wallet.address_index + 1
        for i in range(start_index, start_index + (2 * num_addresses), 2):
            address = wallet.get_address(i)

            # TODO: Mark an Address in a persistent way as being reserved by a Service
            wallet.setlabel(address=address, label=label)
        
            # TODO: What annotations do we want to save? Date reserved?
            annotations_storage.set_addr_annotations(addr=address, annotations={}, autosave=False)
        
        annotations_storage.save()

    def init_controller(self):
        """This is importing the controller for this service"""
        module = import_module(f"cryptoadvance.specter.services.{self.id}.controller")
        app.register_blueprint(self.__class__.blueprint, url_prefix=f"/svc/{self.id}")

    def is_active(self):
        return self.active

    def set_active(self, value):
        self.active = value
