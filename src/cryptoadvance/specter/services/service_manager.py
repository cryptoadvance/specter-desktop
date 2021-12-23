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

from cryptoadvance.specter.managers.singleton import ConfigurableSingletonException

from .service import Service
from .service_encrypted_storage import ServiceEncryptedStorageManager

logger = logging.getLogger(__name__)


class ServiceManager:
    """Loads support for all Services it auto-discovers."""

    def __init__(self, specter, devstatus_threshold):
        self.specter = specter
        self.devstatus_threshold = devstatus_threshold
        self._services = {}

        # Discover all subclasses of Service by listing the path where all the services are located:
        package_dir = str(Path(Path(__file__).resolve().parent).resolve())
        logger.info("----> starting service discovery <----")
        for item in os.listdir(package_dir):
            # We're looking for the subdirs for each Service; skip anything else.
            #   ".DS_Store" is a macOS artifact.
            if item.endswith(".py") or item in [
                "templates",
                "static",
                "__pycache__",
                ".DS_Store",
            ]:
                continue
            try:
                module = import_module(f"cryptoadvance.specter.services.{item}.service")
            except ModuleNotFoundError:
                logger.warning(
                    f"Service Directory cryptoadvance.specter.services.{item} does not have a service implementation file! Skipping!"
                )
                continue
            service_id = item
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)

                if isclass(attribute):
                    clazz = attribute
                    if issubclass(clazz, Service) and not clazz.__name__ == "Service":
                        # Found a Service subclass!
                        # Activate based on devstatus
                        compare_map = {"alpha": 1, "beta": 2, "prod": 3}
                        if (
                            compare_map[self.devstatus_threshold]
                            <= compare_map[clazz.devstatus]
                        ):
                            # First configure the service
                            self.configure_service_for_module(service_id)
                            # Now activate it
                            self._services[clazz.id] = clazz(
                                active=clazz.id
                                in self.specter.config.get("services", []),
                                specter=self.specter,
                            )
                            logger.info(
                                f"Service {clazz.__name__} activated ({clazz.devstatus})"
                            )
                        else:
                            logger.info(
                                f"Service {clazz.__name__} not activated due to devstatus ( {self.devstatus_threshold} > {clazz.devstatus} )"
                            )

        # Configure and instantiate the one and only ServiceApiKeyStorageManager
        try:
            ServiceEncryptedStorageManager.configure_instance(specter=specter)
        except ConfigurableSingletonException as e:
            # Test suite triggers multiple calls; ignore for now.
            pass
        logger.info("----> finished service discovery <----")

    @classmethod
    def configure_service_for_module(cls, service_id):
        """searches for ConfigClasses in the module-Directory and merges its config in the global config"""
        module = import_module(f"cryptoadvance.specter.services.{service_id}.config")
        config_clazz_name = app.config.get("SPECTER_CONFIGURATION_CLASS_FULLNAME")
        config_clazz_slug = config_clazz_name.split(".")[-1]
        found_config = False
        potential_config_classes = []
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isclass(attribute):
                clazz = attribute
                potential_config_classes.append(clazz)
                if clazz.__name__.endswith(
                    config_clazz_slug
                ):  # e.g. BaseConfig or DevelopmentConfig
                    found_config = True
                    cls.import_config(clazz)

        if not found_config:
            logger.warning(
                f"Could not find a configuration for Service {module} ... trying parent-classes of main-config"
            )
            config_module = import_module(".".join(config_clazz_name.split(".")[0:-1]))
            config_clazz = getattr(config_module, config_clazz_slug)
            config_candidate_class = config_clazz.__bases__[0]
            while config_candidate_class != object:
                for clazz in potential_config_classes:
                    if clazz.__name__.endswith(config_candidate_class.__name__):
                        cls.import_config(clazz)
                config_candidate_class = config_candidate_class.__bases__[0]
            logger.warning(f"Could not find a configuration for Service {module}")

    @classmethod
    def import_config(cls, clazz):
        logger.info(f"Loading Service-specific configuration from {clazz}")
        for key in dir(clazz):
            if key.isupper():
                if app.config.get(key):
                    raise Exception(
                        f"Config {clazz} tries to override existing key {key}"
                    )
                app.config[key] = getattr(clazz, key)
                logger.debug(f"setting {key} = {app.config[key]}")

    @property
    def services(self):
        return self._services

    @property
    def services_sorted(self):
        service_names = sorted(
            self._services, key=lambda s: self._services[s].sort_priority
        )
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
