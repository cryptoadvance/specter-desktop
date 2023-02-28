import logging
from importlib import import_module
import inspect
import os
from pathlib import Path
import pkgutil
from pkgutil import iter_modules
import sys
from typing import List
from .common import camelcase2snake_case
from ..specter_error import SpecterError, SpecterInternalException
from .shell import grep

from .reflection_fs import detect_extension_style_in_cwd, search_dirs_in_path

logger = logging.getLogger(__name__)


def _get_module_from_class(clazz):
    return import_module(clazz.__module__)


def get_class(fqcn: str):
    """Returns a class by a fully qualified class name like e.g. cryptoadvance.specter.node.Node"""
    module_name = ".".join(fqcn.split(".")[:-1])

    class_name = fqcn.split(".")[-1]
    try:
        module = import_module(module_name)
        my_class = getattr(module, class_name)
    except (AttributeError, ModuleNotFoundError) as e:
        raise SpecterInternalException(f"Could not find {fqcn}: {e}")
    return my_class


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
        # here, we'd like to know the Path of the namespace module cryptoadvance.specterext
        # but that fails because you cannot import namespace-modules.
        # So we take a module that we know exists and take its parent.
        return str(
            Path(
                import_module("cryptoadvance.specterext.devhelp").__file__
            ).parent.parent.resolve()
        )
    # This is mainly for testing purposes for now
    elif clazz.__name__ == "Device":
        return str(
            Path(
                import_module("cryptoadvance.specter.devices").__file__
            ).parent.resolve()
        )
    raise SpecterError("Unknown Class: {clazz}")


# --------------- static discovery ------------------------------


def get_classlist_of_type_clazz_from_modulelist(clazz, modulelist):
    """A helper method converting a List of modules as described in config.py
    into a List of classes. In order to make that more util-like, you
    have to pass the the class you're searching for in the modules
    """
    class_list = []
    for fq_module_name in modulelist:
        try:
            module = import_module(fq_module_name)
        except ModuleNotFoundError as e:
            # ToDo: make it somehow clear where specific extensions are coming from: external or within same repo
            raise SpecterError(
                f"""
                Module {fq_module_name}  could not be found. This could have these reasons:
                * You might have forgot to: 
                    pip3 install yourPackage
                * You're trying to start the ProductionConfig in a Development Environment. 
                    If you checked out the specter-Sourcecode, you should start specter like this:
                    python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug"""
            )
        logger.debug(f"Imported {fq_module_name}")
        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if inspect.isclass(attribute):
                if (
                    issubclass(attribute, clazz)
                    # This works for 1 level inheritance within one module
                    and not attribute.__name__ == clazz.__name__
                ):
                    # Unfortunately the superclass gets imported if you inherit from it and counts as an attribute as well
                    if str(attribute.__module__).startswith(fq_module_name):
                        logger.debug(f"Adding {attribute} to {class_list}")
                        class_list.append(attribute)
                        logger.info(f"  Found class {attribute.__name__}")
    return class_list


def get_subclasses_for_clazz_in_cwd(clazz, cwd=".") -> List[type]:
    """Returns all subclasses of class clazz located in the CWD if the cwd
    is not a specter-desktop dev-env-kind-of-dir or contains any .py-file
    """
    package_dirs = []
    # security first! No dynamic loading in app-images
    if getattr(sys, "frozen", False):
        return []

    # if not testing but in a folder which looks like specter-desktop/src --> No dynamic extensions
    if "PYTEST_CURRENT_TEST" not in os.environ:
        # Hmm, a bit hackish but if the pyproject.toml specifies cryptoadvance.specter as a name and
        # we don't need to depend on toml-parsing libs, that should be ok.
        try:
            found, line = grep("./pyproject.toml", 'name = "cryptoadvance.specter"')
            if found:
                return []
            if line:
                line = line.replace(" ", "").replace("'", "").replace('"', "")
            if line == "name=cryptoadvance.specter":
                return []
        except FileNotFoundError:
            pass

    # Depending on the style we either add "." or "./src" to the searchpath

    extension_style = detect_extension_style_in_cwd()
    # raise Exception(extension_style)
    if extension_style == "adhoc":
        package_dirs.append(Path("."))
    elif extension_style == "publish-ready":
        package_dirs.extend(search_dirs_in_path(Path("./src")))
    elif extension_style == "specter-desktop":
        if "PYTEST_CURRENT_TEST" in os.environ:
            # I admit, ugly hack
            logger.info("We're in testing mode. Adding CWD to searchpath")
            package_dirs.append(Path("./src"))
        else:
            raise Exception(
                f"""
                We checked before that we're not in the specter-desktop home 
                directory but now the extension-style is 'specter-desktop' ?!
                This should not happen!
            """
            )
    logger.info(f"Detected Extension-style: {extension_style}")
    logger.info(f"We'll search in those package_dirs {package_dirs}")
    return get_subclasses_for_clazz(clazz, package_dirs)


def get_subclasses_for_clazz(
    clazz, package_dirs: List[str] = None, package: str = None
):
    """Returns all subclasses of class clazz searching in specific directories
    potentially add additional_packagedirs which is usefull for
    calculating pyinstaller hiddenimports
    """
    if package_dirs == None:
        package_dirs = [get_package_dir_for_subclasses_of(clazz)]
    class_list = []
    logger.info(
        f"Collecting subclasses of {clazz.__name__} in {' '.join([ str(dir) for dir in package_dirs]) }..."
    )
    for (importer, module_name, is_pkg) in iter_modules(
        [str(dir) for dir in package_dirs]
    ):  # import the module and iterate through its attributes
        # skip known redherrings
        if module_name in ["callbacks"]:
            continue
        logger.info(
            f"Iterating on importer={importer} , module_name={module_name} is_pkg={is_pkg}"
        )
        if clazz.__name__ == "Service":
            # Ignore the stuff lying around in cryptoadvance/specter/services
            if importer.path.endswith(
                os.path.sep.join(["cryptoadvance", "specter", "services"])
            ):
                continue
            try:
                module = import_module(f"{module_name}.service")
                logger.debug(f"  Imported {module_name}.service")
            except ModuleNotFoundError as e:
                try:
                    # Another style is orgname.specterext.extensionid, for that we have to guess the orgname:
                    orgname = str(importer.path).split(os.path.sep)[-2]
                    logger.debug(f"guessing orgname: {orgname}")
                    module = import_module(
                        f"{orgname}.specterext.{module_name}.service"
                    )
                    logger.debug(
                        f"  Imported {orgname}.specterext.{module_name}.service"
                    )
                except ModuleNotFoundError as e:
                    if module_name in str(e.name) or orgname in str(e.name):
                        raise Exception(
                            f"""
                    While iterating over {importer} for module {module_name}, 
                    a Service implementation could not be found in this places:
                    * cryptoadvance.specter.services.{module_name}.service
                    * {module_name}.service
                    * {orgname}.specterext.{module_name}.service
                    Maybe you did forget to do this:
                    $ pip3 install -e .

                    OR The Module has been found, but had issues finding Modules itself

                    {e}
                    """
                        )
                    else:
                        raise e
        elif clazz.__name__ == "SpecterMigration":
            module = import_module(
                f"cryptoadvance.specter.util.migrations.{module_name}"
            )
        else:
            # Hopefully all the classes we're searching for are imported otherwise not much get
            # found
            return get_subclasses(clazz)

        for attribute_name in dir(module):
            attribute = getattr(module, attribute_name)
            if inspect.isclass(attribute):
                if (
                    issubclass(attribute, clazz)
                    and not attribute.__name__ == clazz.__name__
                ):
                    class_list.append(attribute)
                    logger.info(f"  Found class {attribute.__name__}")
    return class_list


def get_subclasses(cls):
    """Naive implementation of searching for subclasses. This will only return classes which has been
    imported. If you also want to find classes which are not imported, you need to provide package-directories
    or well known places as for specific classes as implemented in get_subclasses_for_clazz
    Returns all subclasses of a specific call including sususub...classes
    """
    subclasses = []
    for subclass in cls.__subclasses__():
        # if not subclass.__module__.startswith("test_"):
        subclasses.append(subclass)
        subclasses.extend(get_subclasses(subclass))
    return subclasses
