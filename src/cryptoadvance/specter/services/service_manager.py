import json
import logging
import os

from flask import current_app as app, url_for
from flask.blueprints import Blueprint
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules
from typing import List

from .service import Service
from .service_encrypted_storage import ServiceEncryptedStorageManager

logger = logging.getLogger(__name__)



class ServiceManager:
    """ Loads support for all Services it auto-discovers. """

    def __init__(self, specter, devstatus_threshold):
        self.specter = specter
        self.devstatus_threshold = devstatus_threshold
        self._initialize_services()

        # Configure and instantiate the one and only ServiceApiKeyStorageManager
        ServiceEncryptedStorageManager.configure_instance(specter=specter)

        print(f"ServiceManager.__init()__: {devstatus_threshold}")

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
                    f"cryptoadvance.specter.services.{item}.service"
                )
            except ModuleNotFoundError:
                logger.error(
                    f"Service Directory cryptoadvance.specter.services.{item} does not have a service implementation file! Skipping!"
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

    @property
    def services(self):
        return self._services
    
    def _initialize_services(self):
        self._services = {}
        for clazz in self.get_service_classes():
            print(clazz)
            print(f"self.devstatus_threshold: {self.devstatus_threshold}")
            compare_map = {"alpha": 1, "beta": 2, "prod": 3}
            if compare_map[self.devstatus_threshold] <= compare_map[clazz.devstatus]:
                self._services[clazz.id] = clazz(
                    clazz.id in self.specter.config.get("services", []), self.specter
                )
                logger.info(f"Service {clazz.__name__} activated ({clazz.devstatus})")
            else:
                logger.info(
                    f"Service {clazz.__name__} not activated due to devstatus ( {self.devstatus_threshold} > {clazz.devstatus} )"
                )
    
    @property
    def services_sorted(self):
        service_names = sorted(self._services, key=lambda s: self._services[s].sort_priority)
        return [self._services[s] for s in service_names]

    def set_active_services(self, service_names_active):
        logger.debug(f"Setting these services active: {service_names_active}")
        self.specter.update_services(service_names_active)
        for _, service in self.services.items():
            logger.debug(
                f"Setting service '{service.id}' active to {service.id in service_names_active}"
            )
            service.active = service.id in service_names_active

    def get_service(self, service_id: str) -> Service:
        if service_id not in self._services:
            # TODO: better error handling?
            raise Exception(f"No such Service: '{service_id}'")
        return self._services[service_id]
