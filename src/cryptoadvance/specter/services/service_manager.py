import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from flask import current_app as app, url_for
from flask.blueprints import Blueprint

from cryptoadvance.specter.services.service_apikey_storage import SecretStorage

logger = logging.getLogger(__name__)


devstatus_alpha = "alpha"
devstatus_beta = "beta"
devstatus_prod = "prod"


class ServiceBase:
    """A BaseClass for Services"""

    has_blueprint = True  # the default
    devstatus = devstatus_alpha
    _ = None

    def __init__(self, active, specter):
        if not hasattr(self, "id"):
            raise Exception(f"Service {self.__class__} needs ID")
        if not hasattr(self, "name"):
            raise Exception(f"Service {self.__class__} needs name")
        self.active = active
        self.specter = specter
        if self.has_blueprint:
            self.__class__._ = self
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
        self._sec_storage = SecretStorage(specter.data_folder, specter.user_manager)

    @property
    def bp_name(self):
        return f"{self.id}_endpoint"

    def init_controller(self):
        """This is importing the controller for this service"""
        module = import_module(f"cryptoadvance.specter.services.{self.id}.controller")
        app.register_blueprint(self.__class__.blueprint, url_prefix=f"/svc/{self.id}")

    def is_active(self):
        return self.active

    def set_active(self, value):
        self.active = value


class Service(ServiceBase):
    def set_sec_data(self, api_data: dict):
        self._sec_storage.set_sec_data(self.id, api_data)

    def get_sec_data(self) -> dict:
        return self._sec_storage.get_sec_data(self.id)


class ServiceManager:
    """A ServiceManager which is quite dumb right now but it should decide which services to show"""

    def __init__(self, specter, devstatus_treshold):
        self.specter = specter
        self.devstatus_treshold = devstatus_treshold
        self.services

    def set_active_services(self, service_names_active):
        logger.debug(f"Setting these services active: {service_names_active}")
        self.specter.update_services(service_names_active)
        for _, service in self.services.items():
            logger.debug(
                f"Setting serve {service.id} active to {service.id in service_names_active}"
            )
            service.active = service.id in service_names_active

    @property
    def services(self):
        if hasattr(self, "_services"):
            return self._services
        self._services = {}
        for clazz in self.get_service_classes():
            compare_map = {"alpha": 1, "beta": 2, "prod": 3}
            if compare_map[self.devstatus_treshold] <= compare_map[clazz.devstatus]:
                self._services[clazz.id] = clazz(
                    clazz.id in self.specter.config.get("services", []), self.specter
                )
                logger.info(f"Service {clazz.__name__} activated")
            else:
                logger.info(
                    f"Service {clazz.__name__} not activated due to devstatus ( {self.devstatus_treshold} > {clazz.devstatus} )"
                )
        return self._services

    @classmethod
    def get_service_classes(cls):
        """Returns all subclasses of class SpecterMigration"""
        class_list = []
        # The path where all the migrations are located:
        package_dir = str(Path(Path(__file__).resolve().parent).resolve())
        print(package_dir)
        for item in os.listdir(package_dir):
            if (
                item.endswith(".py")
                or item.endswith("templates")
                or item.endswith("static")
                or item.endswith("__pycache__")
            ):
                continue
            try:
                module = import_module(
                    f"cryptoadvance.specter.services.{item}.manifest"
                )
            except ModuleNotFoundError:
                logger.error(
                    f"Service Directory cryptoadvance.specter.services.{item} does not have a manifest file! Skipping!"
                )
                continue
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isclass(attribute):
                    if (
                        issubclass(attribute, Service)
                        and not attribute.__name__ == "Service"
                    ):
                        class_list.append(attribute)
        return class_list
