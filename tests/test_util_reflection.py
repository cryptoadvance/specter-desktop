import logging
from pathlib import Path
from typing import List
from cryptoadvance.specter.util.reflection import (
    get_subclasses_for_clazz,
    get_subclasses_for_clazz_in_cwd,
    get_classlist_of_type_clazz_from_modulelist,
    _get_module_from_class,
    get_package_dir_for_subclasses_of,
    search_dirs_in_path,
)
from cryptoadvance.specter.util.specter_migrator import SpecterMigration
from cryptoadvance.specter.util.migrations.migration_0000 import SpecterMigration_0000
from cryptoadvance.specter.managers.service_manager import Service
from cryptoadvance.specter.services.swan.service import SwanService
from cryptoadvance.specter.services.bitcoinreserve.service import BitcoinReserveService


def test_get_module_from_class():
    assert (
        _get_module_from_class(SpecterMigration).__name__
        == "cryptoadvance.specter.util.specter_migrator"
    )
    assert (
        _get_module_from_class(Service).__name__
        == "cryptoadvance.specter.services.service"
    )


def test_get_package_dir_for_subclasses_of():
    assert get_package_dir_for_subclasses_of(SpecterMigration).endswith(
        "cryptoadvance/specter/util/migrations"
    )
    assert get_package_dir_for_subclasses_of(Service).endswith(
        "cryptoadvance/specter/services"
    )


def test_get_classlist_from_importlist(caplog):
    caplog.set_level(logging.DEBUG)
    modulelist = [
        "cryptoadvance.specter.services.swan.service",
        "cryptoadvance.specter.services.bitcoinreserve.service",
    ]
    classlist = get_classlist_of_type_clazz_from_modulelist(Service, modulelist)
    assert len(classlist) == 2  # Happy to remove that at some point
    assert SwanService in classlist
    assert BitcoinReserveService in classlist


def test_get_subclasses_for_clazz_in_cwd(caplog):
    caplog.set_level(logging.DEBUG)
    classlist: List[type] = get_subclasses_for_clazz_in_cwd(
        Service, cwd="./tests/xtestdata_testextensions"
    )
    # damn, this is difficult to test
    # assert len(classlist) == 3


def test_get_subclasses_for_class(caplog):
    caplog.set_level(logging.INFO)
    classlist = get_subclasses_for_clazz(SpecterMigration)
    assert SpecterMigration_0000 in classlist
    classlist = get_subclasses_for_clazz(Service)
    assert len(classlist) == 2  # Happy to remove that at some point
    assert SwanService in classlist
    assert BitcoinReserveService in classlist
