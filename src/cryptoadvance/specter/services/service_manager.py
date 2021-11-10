import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules

from flask import current_app as app

logger = logging.getLogger(__name__)


maturity_alpha = "alpha"
maturity_beta = "beta"
maturity_prod = "prod"


class Service:
    """A BaseClass for Services"""

    has_blueprint = True  # the default
    maturity = maturity_alpha

    def __init__(self, active):
        if not hasattr(self, "id"):
            raise Exception(f"Service {self.__class__} needs ID")
        if not hasattr(self, "name"):
            raise Exception(f"Service {self.__class__} needs name")
        self.active = active

    def is_active(self):
        return self.active

    def set_active(self, value):
        self.active = value


class ServiceManager:
    """A ServiceManager which is quite dumb right now but it should decide which services to show"""

    def __init__(self, specter):
        self.specter = specter
        self.maturity_treshold = app.config.get(
            "SERVICE_MATURITY_TRESHOLD", "production"
        )
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
            if compare_map[self.maturity_treshold] <= compare_map[clazz.maturity]:
                self._services[clazz.id] = clazz(
                    clazz.id in self.specter.config.get("services", [])
                )
            else:
                logger.info(
                    "Service {clazz.__name__} not activated due to maturity ( {self.maturity_treshold} > {clazz.maturity} )"
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
            logger.info("Collecting possible Services ...")
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if isclass(attribute):
                    if (
                        issubclass(attribute, Service)
                        and not attribute.__name__ == "Service"
                    ):
                        class_list.append(attribute)
        return class_list
