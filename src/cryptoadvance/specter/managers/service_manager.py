import json
import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules
from typing import Dict, List

from cryptoadvance.specter.config import ProductionConfig
from cryptoadvance.specter.managers.singleton import ConfigurableSingletonException
from cryptoadvance.specter.user import User
from flask import current_app as app
from flask import url_for
from flask.blueprints import Blueprint

from ..services.service import Service
from ..services.service_encrypted_storage import ServiceEncryptedStorageManager
from ..util.reflection import (
    _get_module_from_class,
    get_classlist_of_type_clazz_from_modulelist,
    get_package_dir_for_subclasses_of,
    get_subclasses_for_clazz,
    get_subclasses_for_clazz_in_cwd,
)

logger = logging.getLogger(__name__)


class ServiceManager:
    """Loads support for all Services it auto-discovers."""

    def __init__(self, specter, devstatus_threshold):
        self.specter = specter
        self.devstatus_threshold = devstatus_threshold

        # Each Service class is stored here, keyed on its Service.id str
        self._services: Dict[str, Service] = {}
        logger.info("----> starting service discovery <----")
        # How do we discover services? Two configs are relevant:
        # * SERVICES_LOAD_FROM_CWD (boolean, CWD is current working directory)
        # * EXTENSION_LIST (array of Fully Qualified module strings like ["cryptoadvance.specter.services.swan.service"])
        # Ensuring security (especially for the CWD) is NOT done here but
        # in the corresponding (Production)Config
        logger.debug(f"EXTENSION_LIST = {app.config.get('EXTENSION_LIST')}")
        class_list = get_classlist_of_type_clazz_from_modulelist(
            Service, app.config.get("EXTENSION_LIST", [])
        )
        if app.config.get("SERVICES_LOAD_FROM_CWD", False):
            class_list.extend(get_subclasses_for_clazz_in_cwd(Service))
        class_list = set(class_list)  # remove duplicates (shouldn't happen but  ...)
        for clazz in class_list:
            compare_map = {"alpha": 1, "beta": 2, "prod": 3}
            if compare_map[self.devstatus_threshold] <= compare_map[clazz.devstatus]:
                # First configure the service
                self.configure_service_for_module(clazz.id)
                # Now activate it
                self._services[clazz.id] = clazz(
                    active=clazz.id in self.specter.config.get("services", []),
                    specter=self.specter,
                )
                logger.info(f"Service {clazz.__name__} activated ({clazz.devstatus})")
            else:
                logger.info(
                    f"Service {clazz.__name__} not activated due to devstatus ( {self.devstatus_threshold} > {clazz.devstatus} )"
                )

        # Configure and instantiate the one and only ServiceEncryptedStorageManager
        try:
            ServiceEncryptedStorageManager.configure_instance(
                specter.data_folder, specter.user_manager
            )
        except ConfigurableSingletonException as e:
            # Test suite triggers multiple calls; ignore for now.
            pass
        logger.info("----> finished service discovery <----")

    @classmethod
    def configure_service_for_module(cls, service_id):
        """searches for ConfigClasses in the module-Directory and merges its config in the global config"""
        try:
            module = import_module(
                f"cryptoadvance.specter.services.{service_id}.config"
            )
        except ModuleNotFoundError:
            logger.warning(
                f"Service {service_id} does not have a service Configuration! Skipping!"
            )
            return
        main_config_clazz_name = app.config.get("SPECTER_CONFIGURATION_CLASS_FULLNAME")
        main_config_clazz_slug = main_config_clazz_name.split(".")[-1]
        potential_config_classes = []
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isclass(attribute):
                clazz = attribute
                potential_config_classes.append(clazz)
                if clazz.__name__.endswith(
                    main_config_clazz_slug
                ):  # e.g. BaseConfig or DevelopmentConfig
                    cls.import_config(clazz)
                    return

        config_module = import_module(".".join(main_config_clazz_name.split(".")[0:-1]))

        config_clazz = getattr(config_module, main_config_clazz_slug)
        config_candidate_class = config_clazz.__bases__[0]
        while config_candidate_class != object:
            for clazz in potential_config_classes:
                if clazz.__name__.endswith(config_candidate_class.__name__):
                    cls.import_config(clazz)
                    return
            config_candidate_class = config_candidate_class.__bases__[0]
        logger.warning(
            f"Could not find a configuration for Service {module}. Skipping configuration."
        )

    @classmethod
    def import_config(cls, clazz):
        logger.info(f"  Loading Service-specific configuration from {clazz}")
        for key in dir(clazz):
            if key.isupper():
                if app.config.get(key):
                    raise Exception(
                        f"Config {clazz} tries to override existing key {key}"
                    )
                app.config[key] = getattr(clazz, key)
                logger.debug(f"setting {key} = {app.config[key]}")

    @property
    def services(self) -> Dict[str, Service]:
        return self._services or {}

    @property
    def services_sorted(self):
        service_names = sorted(
            self._services, key=lambda s: self._services[s].sort_priority
        )
        return [self._services[s] for s in service_names]

    def user_has_encrypted_storage(self, user: User) -> bool:
        """Looks for any data for any service in the User's ServiceEncryptedStorage.
        This check works even if the user doesn't have their plaintext_user_secret
        available."""
        encrypted_data = (
            ServiceEncryptedStorageManager.get_instance().get_raw_encrypted_data(user)
        )
        print(f"encrypted_data: {encrypted_data} for {user}")
        return encrypted_data != {}

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

    def remove_all_services_from_user(self, user: User):
        """
        Clears User.services and `user_secret`; wipes the User's
        ServiceEncryptedStorage.
        """
        # Don't show any Services on the sidebar for the admin user
        user.services.clear()

        # Reset as if we never had any encrypted storage
        user.delete_user_secret(autosave=False)
        user.save_info()

        if self.user_has_encrypted_storage(user=user):
            # Encrypted Service data is now orphaned since there is no
            # password. So wipe it from the disk.
            ServiceEncryptedStorageManager.get_instance().delete_all_service_data(user)

    @classmethod
    def get_service_x_dirs(cls, x):
        """returns a list of package-directories which represents a specific service.
        This is used by the pyinstaller packaging specter
        """
        arr = [
            Path(Path(_get_module_from_class(clazz).__file__).parent, x)
            for clazz in get_subclasses_for_clazz(Service)
        ]
        arr = [path for path in arr if path.is_dir()]
        return [Path("..", *path.parts[-6:]) for path in arr]

    @classmethod
    def get_service_packages(cls):
        """returns a list of strings containing the service-classes (+ controller/config-classes)
        This is used for hiddenimports in pyinstaller
        """
        arr = get_subclasses_for_clazz(Service)
        arr.extend(
            get_classlist_of_type_clazz_from_modulelist(
                Service, ProductionConfig.EXTENSION_LIST
            )
        )
        arr = [clazz.__module__ for clazz in arr]
        # Controller-Packagages from the services are not imported via the service but via the baseclass
        # Therefore hiddenimport don't find them. We have to do it here.
        cont_arr = [
            ".".join(package.split(".")[:-1]) + ".controller" for package in arr
        ]
        for controller_package in cont_arr:
            try:
                import_module(controller_package)
                arr.append(controller_package)
            except ImportError:
                pass
            except AttributeError:
                # something like:
                # AttributeError: type object 'BitcoinReserveService' has no attribute 'blueprint'
                # shows that the package is existing
                arr.append(controller_package)
            except RuntimeError:
                # something like
                # RuntimeError: Working outside of application context.
                # shows that the package is existing
                arr.append(controller_package)
        config_arr = [".".join(package.split(".")[:-1]) + ".config" for package in arr]
        for config_package in config_arr:
            try:
                import_module(config_package)
                arr.append(config_package)
            except ModuleNotFoundError as e:
                pass
        return arr
