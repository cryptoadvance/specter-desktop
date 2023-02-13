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
from cryptoadvance.specter.device import Device
from cryptoadvance.specter.managers.service_manager.callback_executor import (
    CallbackExecutor,
)
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.user import User
from cryptoadvance.specter.util.reflection import get_template_static_folder
from flask import current_app as app
from flask import url_for
from flask.blueprints import Blueprint

from cryptoadvance.specter.util.specter_migrator import SpecterMigration

from ...services.service import Service, ServiceOptionality
from ...services import callbacks, ExtensionException
from ...util.reflection import (
    _get_module_from_class,
    get_classlist_of_type_clazz_from_modulelist,
    get_package_dir_for_subclasses_of,
    get_subclasses_for_clazz,
    get_subclasses_for_clazz_in_cwd,
)
from ...util.reflection_fs import search_dirs_in_path

logger = logging.getLogger(__name__)


class ExtensionManager:
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
        # * EXTENSION_LIST (array of Fully Qualified module strings like ["cryptoadvance.specterext.swan.service"])
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
                logger.info(f"Loading Service {clazz.__name__} from {clazz.__module__}")
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
                self.register_devices_from_ext(self._services[clazz.id])
                logger.info(f"Service {clazz.__name__} activated ({clazz.devstatus})")
            else:
                logger.info(
                    f"Service {clazz.__name__} not activated due to devstatus ( {self.devstatus_threshold} > {clazz.devstatus} )"
                )
        logger.info("----> finished service processing")
        self.callback_executor = CallbackExecutor(self.services)
        self.execute_ext_callbacks(callbacks.afterExtensionManagerInit)

    @classmethod
    def register_blueprint_for_ext(cls, clazz, ext):
        if not clazz.has_blueprint:
            return
        if hasattr(clazz, "blueprint_modules"):
            controller_modules = clazz.blueprint_modules
            setattr(clazz, "blueprints", {})
        elif hasattr(clazz, "blueprint_module"):
            controller_modules = {"default": clazz.blueprint_module}
        else:
            import_name = f"cryptoadvance.specter.services.{clazz.id}.service"
            controller_modules = controller_modules = {
                "default": f"cryptoadvance.specter.services.{clazz.id}.controller"
            }

        only_one_blueprint = len(controller_modules.items()) == 1

        def inject_stuff():
            """Can be used in all jinja2 templates"""
            return dict(specter=app.specter, service=ext)

        if "default" not in controller_modules.keys():
            raise SpecterError(
                "You need at least one Blueprint, with the key 'default'. It will be used to link to your UI"
            )

        for bp_key, bp_value in controller_modules.items():
            if bp_key == "":
                raise SpecterError("Empty keys are not allowed in the blueprints map")
            middple_part = "" if bp_key == "default" else f"{bp_key}_"
            bp_name = f"{clazz.id}_{middple_part}endpoint"
            logger.debug(
                f"  Creating blueprint with name {bp_name} (middle_part:{middple_part}:"
            )
            bp = Blueprint(
                f"{clazz.id}_{middple_part}endpoint",
                bp_value,
                template_folder=get_template_static_folder("templates"),
                static_folder=get_template_static_folder("static"),
            )
            if only_one_blueprint:
                setattr(clazz, "blueprint", bp)
            else:
                clazz.blueprints[bp_key] = bp
            bp.context_processor(inject_stuff)

            # Import the controller for this service
            logger.info(f"  Loading Controller {bp_value}")

            try:
                controller_module = import_module(bp_value)
            except ModuleNotFoundError as e:
                raise Exception(
                    f"""
                    There was an issue finding a controller module:
                    {e}
                    That module was specified in the Service class of service {clazz.id}
                    check that specification in {clazz.__module__}
                """
                )

            # finally register the blueprint
            if clazz.isolated_client:
                ext_prefix = app.config["ISOLATED_CLIENT_EXT_URL_PREFIX"]
            else:
                ext_prefix = app.config["EXT_URL_PREFIX"]

            try:
                bp_postfix = "" if only_one_blueprint else f"/{bp_key}"
                if (
                    app.testing
                    and len(
                        [vf for vf in app.view_functions if vf.startswith(clazz.id)]
                    )
                    <= 1
                ):  # the swan-static one
                    # Yet again that nasty workaround which has been described in the archblog.
                    # The easy variant can be found in server.py
                    # The good news is, that we'll only do that for testing
                    import importlib

                    logger.info("Reloading Extension controller")
                    importlib.reload(controller_module)
                    app.register_blueprint(
                        bp, url_prefix=f"{ext_prefix}/{clazz.id}{bp_postfix}"
                    )
                else:
                    app.register_blueprint(
                        bp, url_prefix=f"{ext_prefix}/{clazz.id}{bp_postfix}"
                    )
                logger.info(f"  Mounted {bp} to {ext_prefix}/{clazz.id}{bp_postfix}")
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
    def register_devices_from_ext(cls, ext):
        """extract the devices from the extension and appends all found one to
        cryptoadvance.specter.devices
        """
        classes = cls.extract_thing_classes_from_extension("devices", Device, ext)
        if not classes:
            return
        from cryptoadvance.specter.devices import __all__ as all_devices

        for device_class in classes:
            all_devices.append(device_class)
            logger.debug(f"  Loaded Device {device_class}")

    @classmethod
    def register_callbacks_from_ext(cls, ext):
        """extract all callbacks from the extension and import them so that they are
        discoverable as subclass of Callback.
        """
        # importing it is the main job here. If it's imported, it'll also be discovered
        # as a subclass of Callback.
        classes = cls.extract_thing_classes_from_extension(
            "callbacks", callbacks.Callback, ext
        )
        for callback_class in classes:
            logger.debug(f"  Loaded Callback {callback_class}")

    @classmethod
    def extract_thing_classes_from_extension(
        cls, things: str, thing_class: type, ext
    ) -> List[type]:
        """If an extension has a definition like that:
        class SomeExtension(Extension)
            things = ["someNym.specterext.some_extensions.things"]
        then this method will return a list of all the thing_class classes
        which can be found in that module:
        extract_thing_classes_from_extension("things",Thing, someExtension)
        """
        if hasattr(ext.__class__, things):
            thing_modules: List[str] = getattr(ext.__class__, things)
        else:
            return []
        classes = []
        for module in thing_modules:
            try:
                classes.extend(
                    get_classlist_of_type_clazz_from_modulelist(Device, [module])
                )
            except ModuleNotFoundError:
                raise SpecterError(
                    f"""
                    The extension {ext.id} declared devices and a module called {module}
                    But that module is not existing.
                """
                )
        if len(classes) == 0:
            raise SpecterError(
                f"""
                    The extension {ext.id} declared devices and a module called {module}
                    But that module doesn't contain any devices.
            """
            )
        from cryptoadvance.specter.devices import __all__ as all_devices

        for device_class in classes:
            all_devices.append(device_class)
            logger.debug(f"  Loaded Device {device_class}")

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
                    f"  Service {clazz.id} does not have a service Configuration! Skipping!"
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
                if (
                    clazz.__name__.split(".")[-1] == main_config_clazz_slug
                ):  # e.g. BaseConfig or DevelopmentConfig
                    cls.import_config(clazz)
                    return

        config_module = import_module(".".join(main_config_clazz_name.split(".")[0:-1]))

        config_clazz = getattr(config_module, main_config_clazz_slug)
        config_candidate_class = config_clazz.__bases__[0]
        while config_candidate_class != object:
            for clazz in potential_config_classes:
                if clazz.__name__.split(".")[-1] == config_candidate_class.__name__:
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
                logger.debug(f"    setting {key} = {app.config[key]}")

    def execute_ext_callbacks(self, callback_id, *args, **kwargs):
        """will execute the callback function for each extension which has defined that method
        the callback_id needs to be passed and specify why the callback has been called.
        It needs to be one of the constants defined in cryptoadvance.specter.services.callbacks
        """
        return self.callback_executor.execute_ext_callbacks(
            callback_id, *args, **kwargs
        )

    @property
    def services(self) -> Dict[str, Service]:
        return self._services or {}

    @property
    def services_sorted(self):
        service_names = sorted(
            self._services, key=lambda s: self._services[s].sort_priority
        )
        return [self._services[s] for s in service_names]

    def is_class_from_loaded_extension(self, claz):
        """Returns Ture if that class is from a module which belongs to an extension
        which is loaded, False otherwise
        """
        print("")
        ext_module = ".".join(claz.__module__.split(".")[0:3])
        for ext in self.services_sorted:
            if ext.__class__.__module__.startswith(ext_module):
                return True
        return False

    def user_has_encrypted_storage(self, user: User) -> bool:
        """Looks for any data for any service in the User's ServiceEncryptedStorage.
        This check works even if the user doesn't have their plaintext_user_secret
        available."""
        encrypted_data = (
            self.specter.service_encrypted_storage_manager.get_raw_encrypted_data(user)
        )
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

    def delete_service_from_user(self, user: User, service_id: str, autosave=True):
        "Removes the service for the user and deletes the stored data in the ServiceEncryptedStorage"
        # remove the service from the sidebar
        user.remove_service(service_id, autosave=autosave)
        # delete the data if it was encrypted
        if (
            self.user_has_encrypted_storage(user=user)
            and self.get_service(service_id).encrypt_data
        ):
            self.specter.service_encrypted_storage_manager.remove_service_data(
                user, service_id, autosave=autosave
            )
        # here we do not need to delete the data if it was unencrypted

    def delete_services_with_encrypted_storage(self, user: User):
        services_with_encrypted_storage = [
            service_id
            for service_id in self.services
            if self.get_service(service_id).encrypt_data
        ]
        for service_id in services_with_encrypted_storage:
            self.delete_service_from_user(user, service_id, autosave=True)

        user.delete_user_secret(autosave=True)
        # Encrypted Service data is now orphaned since there is no
        # password. So wipe it from the disk.
        self.specter.service_encrypted_storage_manager.delete_all_service_data(user)
        logger.debug(
            f"Deleted encrypted services {services_with_encrypted_storage} and user secret"
        )

    def delete_services_with_unencrypted_storage(self, user: User):
        services_with_unencrypted_storage = [
            service_id
            for service_id in self.services
            if not self.get_service(service_id).encrypt_data
        ]
        for service_id in services_with_unencrypted_storage:
            self.delete_service_from_user(user, service_id, autosave=True)

        self.specter.service_unencrypted_storage_manager.delete_all_service_data(user)
        logger.debug(f"Deleted unencrypted services")

    def add_required_services_to_users(self, users, force_opt_out=False):
        "Adds the mandatory and opt_out (only if no services activated for user) services to users"
        for service in self.services.values():
            for user in users:
                if service.optionality == ServiceOptionality.mandatory or (
                    service.optionality == ServiceOptionality.opt_out
                    and ((service.id not in user.services) or force_opt_out)
                ):
                    user.add_service(service.id)

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
        logger.info(f"Initial arr:")
        for element in arr:
            logger.debug(element)
        # /home/kim/src/specter-desktop/.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates

        # filter only directories
        arr = [path for path in arr if path.is_dir()]
        # Those pathes are absolute. Let's make them relative:
        arr = [cls._make_path_relative(path) for path in arr]

        # result:
        # site-package/cryptoadvance/specterext/devhelp/templates
        logger.info(f"After making the pathes relative, example: {arr[0]}")

        virtuelenv_path = os.path.relpath(os.environ["VIRTUAL_ENV"], ".")

        logger.info(f"virtuelenv_path: {virtuelenv_path}")

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
        logger.info(f"src_org_specterext_exts[0]: {src_org_specterext_exts[0]}")

        src_org_specterext_exts = [Path(path, x) for path in src_org_specterext_exts]

        arr.extend(src_org_specterext_exts)

        logger.debug(f"Returning example: {arr[0]}")
        return arr

    @classmethod
    def get_service_packages(cls):
        """returns a list of strings containing the service-classes (+ controller +config-classes +devices +migrations)
        This is used for hiddenimports in pyinstaller
        """
        arr = get_subclasses_for_clazz(Service)
        arr.extend(get_subclasses_for_clazz(SpecterMigration))
        logger.info(f"initial arr: {arr}")
        arr.extend(
            get_classlist_of_type_clazz_from_modulelist(
                Service, ProductionConfig.EXTENSION_LIST
            )
        )
        logger.info(f"After extending: {arr}")

        # Before we transform the arr into an array of strings, we iterate through all services to discover
        # the devices which might be specified in there
        devices_arr = []
        for clazz in arr:
            if hasattr(clazz, "devices"):
                logger.debug(f"class {clazz.__name__} has devices: {clazz.devices}")
                for device in clazz.devices:
                    try:
                        import_module(device)
                        devices_arr.append(device)
                    except ModuleNotFoundError as e:
                        pass

        # Same for callbacks
        callbacks_arr = []
        for clazz in arr:
            if hasattr(clazz, "callbacks"):
                logger.debug(f"class {clazz.__name__} has callbacks: {clazz.callbacks}")
                for device in clazz.callbacks:
                    try:
                        import_module(device)
                        callbacks_arr.append(device)
                    except ModuleNotFoundError as e:
                        pass

        # Transform into array of strings
        arr = [clazz.__module__ for clazz in arr]

        arr.extend(devices_arr)
        arr.extend(callbacks_arr)
        logger.debug(f"After transforming + devices + callbacks: {arr}")

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
        arr = list(dict.fromkeys(arr))
        return arr

    @classmethod
    def _make_path_relative(cls, path: Path) -> Path:
        """make out of something like '# /home/kim/src/specter-desktop/.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates
        somethink like:                                                                                   cryptoadvance/specter/services/swan/templates
        The first part might be completely random. The marker is something like .*env
        """
        index = 0
        sep_index = 0
        for part in path.parts:
            if part.endswith("site-packages"):
                sep_index = index
            index += 1
        if sep_index == 0:
            raise SpecterInternalException(
                f"Path {path} does not contain an environment directory!"
            )

        return Path(*path.parts[sep_index:index])
