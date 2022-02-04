import logging
from importlib import import_module
from inspect import isclass
import os
from pathlib import Path
import pkgutil
from pkgutil import iter_modules
import sys
from .common import camelcase2snake_case
from ..specter_error import SpecterError

logger = logging.getLogger(__name__)


def _get_module_from_class(clazz):
    return import_module(clazz.__module__)


def get_template_static_folder(foldername):
    """convenience-method to return static/template methods taking pyinstaller into account
    foldername can be anything but probably most reasonable template or static
    """
    if getattr(sys, "frozen", False):
        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        x_folder = os.path.join(sys._MEIPASS, foldername)
    else:
        x_folder = foldername
    return x_folder


def get_package_dir_for_subclasses_of(clazz):
    """There are two occasions where this makes sense: migrations and service-classes. Depending on the clazz
    this function is returning package_directories where subclasses from clazz are supposed to be located
    * subclasses of SpecterMigration are located in a subpackage called migrations
    * subclasses of Servuce are located in subpackages of package cryptoadvance.specter.services
    I have to admit that this is not a pure util class as it's containing business-logic.
    It's no longer used for Service.
    """
    if clazz.__name__ == "SpecterMigration":
        return str(
            Path(
                Path(_get_module_from_class(clazz).__file__).resolve().parent,
                "migrations",
            ).resolve()
        )
    elif clazz.__name__ == "Service":
        return str(
            Path(
                import_module("cryptoadvance.specter.services").__file__
            ).parent.resolve()
        )
    # This is mainly for testing purposes for now
    elif clazz.__name__ == "Device":
        return str(
            Path(
                import_module("cryptoadvance.specter.devices").__file__
            ).parent.resolve()
        )
    raise SpecterError("Unknown Class: {clazz}")


def get_classlist_of_type_clazz_from_modulelist(clazz, modulelist):
    """A helper method converting a List of modules as described in config.py
    into a List of classes. In order to make that more util-like, you
    have to pass the the class you're searching for in the modules
    """
    class_list = []
    for fq_module_name in modulelist:
        module = import_module(fq_module_name)
        logger.debug(f"Imported {fq_module_name}")
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isclass(attribute):
                if (
                    issubclass(attribute, clazz)
                    and not attribute.__name__ == clazz.__name__
                ):
                    class_list.append(attribute)
                    logger.info(f"  Found class {attribute.__name__}")
    return class_list


def get_subclasses_for_clazz_in_cwd(clazz):
    """Returns all subclasses of class clazz located in the CWD if the cwd
    is not a specter-desktop dev-env-kind-of-dir
    """
    package_dirs = []
    if Path("./src/cryptoadvance").is_dir() or getattr(sys, "frozen", False):
        # No discovery in specter-desktop-dev-env (doesn't make sense)
        # or appimage-mode (technically difficult on Linux and security-risk for
        # appimage-users even on --config DevelopmentConfig)
        return []
    else:
        package_dirs.append(".")
        logger.info("Running in non-specter-src-folder. Added CWD to Service-Discovery")
        return get_subclasses_for_clazz(clazz, package_dirs)


def get_subclasses_for_clazz(clazz, package_dirs=None):
    """Returns all subclasses of class clazz located in the CWD
    potentially add additional_packagedirs which is usefull for
    calculating pyinstaller hiddenimports
    """
    if package_dirs == None:
        package_dirs = [get_package_dir_for_subclasses_of(clazz)]
    class_list = []
    logger.info(f"Collecting subclasses of {clazz.__name__} in {package_dirs}...")
    for (_, module_name, _) in iter_modules(
        package_dirs
    ):  # import the module and iterate through its attributes
        logger.debug(f"Iterating on {module_name} ")
        if clazz.__name__ == "Service":
            try:

                module = import_module(
                    f"cryptoadvance.specter.services.{module_name}.service"
                )
                logger.debug(
                    f"Imported cryptoadvance.specter.services.{module_name}.service"
                )
            except ModuleNotFoundError:
                logger.debug(
                    f"No Service Impl found in cryptoadvance.specter.services.{module_name}."
                )
                try:
                    module = import_module(f"{module_name}.service")
                    logger.debug(f"Imported {module_name}.service")
                except ModuleNotFoundError as e:
                    logger.debug(
                        f"No Service Impl found in {module_name}.service. Skipping!"
                    )
                    continue
        elif clazz.__name__ == "SpecterMigration":
            module = import_module(
                f"cryptoadvance.specter.util.migrations.{module_name}"
            )
        else:
            try:
                module = import_module(
                    f"{module_name}.{camelcase2snake_case(clazz.__name__)}"
                )
                logger.debug(
                    f"Imported {module_name}.{camelcase2snake_case(clazz.__name__)}"
                )
            except ModuleNotFoundError as e:
                logger.debug(
                    f"No Service Impl found in {module_name}.service. Skipping!"
                )
                continue
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if isclass(attribute):
                if (
                    issubclass(attribute, clazz)
                    and not attribute.__name__ == clazz.__name__
                ):
                    class_list.append(attribute)
                    logger.info(f"  Found class {attribute.__name__}")
    return class_list
