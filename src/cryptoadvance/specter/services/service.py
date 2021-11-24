import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from flask import current_app as app, url_for
from flask.blueprints import Blueprint

from .service_apikey_storage import ServiceApiKeyStorageManager

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
    def get_current_user_api_data(cls) -> dict:
        return ServiceApiKeyStorageManager.get_instance().get_current_user_api_data(service_id=cls.id)

    @classmethod
    def get_blueprint_name(cls):
        return f"{cls.id}_endpoint"

    def init_controller(self):
        """This is importing the controller for this service"""
        module = import_module(f"cryptoadvance.specter.services.{self.id}.controller")
        app.register_blueprint(self.__class__.blueprint, url_prefix=f"/svc/{self.id}")

    def is_active(self):
        return self.active

    def set_active(self, value):
        self.active = value

