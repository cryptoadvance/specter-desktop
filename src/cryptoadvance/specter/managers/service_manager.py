import json
import logging
import os
from importlib import import_module
from inspect import isclass
from pathlib import Path
from pkgutil import iter_modules
import sys
from typing import Dict, List

from cryptoadvance.specter.config import ProductionConfig
from cryptoadvance.specter.managers.singleton import ConfigurableSingletonException
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.user import User
from cryptoadvance.specter.util.reflection import get_template_static_folder
from flask import current_app as app
from flask import url_for
from flask.blueprints import Blueprint

from ..services.service import Service
from ..services import callbacks, ExtensionException
from ..services.service_encrypted_storage import (
    ServiceEncryptedStorageManager,
    ServiceUnencryptedStorageManager,
)
from ..util.reflection import (
    _get_module_from_class,
    get_classlist_of_type_clazz_from_modulelist,
    get_package_dir_for_subclasses_of,
    get_subclasses_for_clazz,
    get_subclasses_for_clazz_in_cwd,
)
from ..util.reflection_fs import search_dirs_in_path

logger = logging.getLogger(__name__)


class ServiceManager:
    """Loads support for all Services it auto-discovers."""

    def __init__(self, specter, devstatus_threshold):
        self.specter = specter
        specter.ext = {}
        self.devstatus_threshold = devstatus_threshold

        # Each Service class is stored here, keyed on its Service.id str
        self._services: Dict[str, Service] = {}
        logger.info("----> starting service discovery Static")
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
            logger.info("----> starting service discovery dynamic")
            class_list.extend(get_subclasses_for_clazz_in_cwd(Service))
        else:
            logger.info("----> skipping service discovery dynamic")
        logger.info("----> starting service loading")
        class_list = set(class_list)  # remove duplicates (shouldn't happen but  ...)
        for clazz in class_list:
            compare_map = {"alpha": 1, "beta": 2, "prod": 3}
            if compare_map[self.devstatus_threshold] <= compare_map[clazz.devstatus]:
                # First configure the service
                self.configure_service_for_module(clazz)
                # Now activate it
                self._services[clazz.id] = clazz(
                    active=clazz.id in self.specter.config.get("services", []),
                    specter=self.specter,
                )
                self.specter.ext[clazz.id] = self._services[clazz.id]
                # maybe register the blueprint
                self.register_blueprint_for_ext(clazz, self._services[clazz.id])
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

        specter.service_unencrypted_storage_manager = ServiceUnencryptedStorageManager(
            specter.user_manager, specter.data_folder
        )

        logger.info("----> finished service processing")
        self.execute_ext_callbacks("afterServiceManagerInit")

    @classmethod
    def register_blueprint_for_ext(cls, clazz, ext):
        if not clazz.has_blueprint:
            return
        if hasattr(clazz, "blueprint_module"):
            import_name = clazz.blueprint_module
            controller_module = clazz.blueprint_module
        else:
            # The import_name helps to locate the root_path for the blueprint
            import_name = f"cryptoadvance.specter.services.{clazz.id}.service"
            controller_module = f"cryptoadvance.specter.services.{clazz.id}.controller"

        clazz.blueprint = Blueprint(
            f"{clazz.id}_endpoint",
            import_name,
            template_folder=get_template_static_folder("templates"),
            static_folder=get_template_static_folder("static"),
        )

        def inject_stuff():
            """Can be used in all jinja2 templates"""
            return dict(specter=app.specter, service=ext)

        clazz.blueprint.context_processor(inject_stuff)

        # Import the controller for this service
        logger.info(f"  Loading Controller {controller_module}")
        controller_module = import_module(controller_module)

        # finally register the blueprint
        if clazz.isolated_client:
            ext_prefix = app.config["ISOLATED_CLIENT_EXT_URL_PREFIX"]
        else:
            ext_prefix = app.config["EXT_URL_PREFIX"]

        try:
            if (
                app.testing
                and len([vf for vf in app.view_functions if vf.startswith(clazz.id)])
                <= 1
            ):  # the swan-static one
                # Yet again that nasty workaround which has been described in the archblog.
                # The easy variant can be found in server.py
                # The good news is, that we'll only do that for testing
                import importlib

                logger.info("Reloading Extension controller")
                importlib.reload(controller_module)
                app.register_blueprint(
                    clazz.blueprint, url_prefix=f"{ext_prefix}/{clazz.id}"
                )
            else:
                app.register_blueprint(
                    clazz.blueprint, url_prefix=f"{ext_prefix}/{clazz.id}"
                )
            logger.info(f"  Mounted {clazz.id} to {ext_prefix}/{clazz.id}")
        except AssertionError as e:
            if str(e).startswith("A name collision"):
                raise SpecterError(
                    f"""
                There is a name collision for the {clazz.blueprint.name}. \n
                This is probably because you're running in DevelopementConfig and configured
                the extension at the same time in the EXTENSION_LIST which currently loks like this:
                {app.config['EXTENSION_LIST']})
                """
                )

    @classmethod
    def configure_service_for_module(cls, clazz):
        """searches for ConfigClasses in the module-Directory and merges its config in the global config"""
        try:
            module = import_module(f"cryptoadvance.specter.services.{clazz.id}.config")
        except ModuleNotFoundError:
            # maybe the other style:
            org = clazz.__module__.split(".")[0]
            try:
                module = import_module(f"{org}.specterext.{clazz.id}.config")
            except ModuleNotFoundError:
                logger.warning(
                    f"Service {clazz.id} does not have a service Configuration! Skipping!"
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

    def execute_ext_callbacks(self, callback_id, *args, **kwargs):
        """will execute the callback function for each extension which has defined that method
        the callback_id needs to be passed and specify why the callback has been called.
        It needs to be one of the constants defined in cryptoadvance.specter.services.callbacks
        """
        if callback_id not in dir(callbacks):
            raise Exception(f"Non existing callback_id: {callback_id}")
        # No debug statement here possible as this is called for every request and would flood the logs
        # logger.debug(f"Executing callback {callback_id}")
        for ext in self.services.values():
            if hasattr(ext, f"callback_{callback_id}"):
                getattr(ext, f"callback_{callback_id}")(*args, **kwargs)
            elif hasattr(ext, "callback"):
                ext.callback(callback_id, *args, **kwargs)

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
        for _, ext in self.services.items():
            logger.debug(
                f"Setting service '{ext.id}' active to {ext.id in service_names_active}"
            )
            ext.active = ext.id in service_names_active

    def get_service(self, plugin_id: str) -> Service:
        """get an extension-instance by ID. Raises an ExtensionException if it doesn't find it."""
        if plugin_id not in self._services:
            raise ExtensionException(f"No such plugin: '{plugin_id}'")
        return self._services[plugin_id]

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
        """returns a list of package-directories which each represents a specific service.
        This is used EXCLUSIVELY by the pyinstaller-hook packaging specter to add templates/static
        When this gets called, CWD is ./pyinstaller
        """

        arr = [
            Path(Path(_get_module_from_class(clazz).__file__).parent, x)
            for clazz in get_subclasses_for_clazz(Service)
        ]
        logger.debug(f"Initial arr:")
        for element in arr:
            logger.debug(element)
        # /home/kim/src/specter-desktop/.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/bitcoinreserve/templates
        # /home/kim/src/specter-desktop/.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates

        arr = [path for path in arr if path.is_dir()]
        # Those pathes are absolute. Let's make them relative:
        arr = [Path(*path.parts[-6:]) for path in arr]

        virtuelenv_path = os.path.relpath(os.environ["VIRTUAL_ENV"], ".")

        if os.name == "nt":
            virtualenv_search_path = Path(virtuelenv_path, "Lib")
        else:
            # let's calcultate so that we get something like:
            # virtualenv_search_path = Path("..", ".buildenv", "lib", "python3.8")
            site_package = [path for path in sys.path if "site-packages" in path][0]
            site_package = Path(virtuelenv_path, *(Path(site_package).parts[-3:-1]))
            virtualenv_search_path = site_package

        # ... and as the classes are in the .buildenv (see build-unix.sh) let's add ..
        arr = [Path(virtualenv_search_path, path) for path in arr]

        # Non internal-repo extensions sitting in org/specterext/... need to be added, too
        src_org_specterext_exts = search_dirs_in_path(
            virtualenv_search_path, return_without_extid=False
        )
        src_org_specterext_exts = [Path(path, x) for path in src_org_specterext_exts]

        arr.extend(src_org_specterext_exts)

        return arr

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
