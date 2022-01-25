import logging
from pathlib import Path
from cryptoadvance.specter.util.reflection import (
    get_subclasses_for_class,
    _get_module_from_class,
    get_package_dir_for_subclasses_of,
)
from cryptoadvance.specter.util.specter_migrator import SpecterMigration
from cryptoadvance.specter.util.migrations.migration_0000 import SpecterMigration_0000
from cryptoadvance.specter.services.service_manager import Service
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


def test_get_subclasses_in_packagedir(caplog):
    caplog.set_level(logging.INFO)
    classlist = get_subclasses_for_class(SpecterMigration)
    assert SpecterMigration_0000 in classlist
    classlist = get_subclasses_for_class(Service)
    assert SwanService in classlist
    assert BitcoinReserveService in classlist
