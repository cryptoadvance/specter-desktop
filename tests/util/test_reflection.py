import logging
import pytest
from pathlib import Path
from typing import List
from cryptoadvance.specter.device import Device
from cryptoadvance.specter.devices.bitbox02 import BitBox02
from cryptoadvance.specter.specter_error import SpecterInternalException
from cryptoadvance.specter.util.migrations.migration_0001 import SpecterMigration_0001
from cryptoadvance.specter.util.reflection import (
    get_class,
    get_subclasses_for_clazz,
    get_subclasses_for_clazz_in_cwd,
    get_classlist_of_type_clazz_from_modulelist,
    _get_module_from_class,
    get_package_dir_for_subclasses_of,
    search_dirs_in_path,
)
from cryptoadvance.specter.util.specter_migrator import SpecterMigration
from cryptoadvance.specter.util.migrations.migration_0000 import SpecterMigration_0000
from cryptoadvance.specter.services.service import Service
from cryptoadvance.specterext.devhelp.service import DevhelpService
from cryptoadvance.specterext.electrum.service import ElectrumService
from cryptoadvance.specterext.spectrum.service import SpectrumService
from cryptoadvance.specterext.swan.service import SwanService


def test_get_module_from_class():
    assert (
        _get_module_from_class(SpecterMigration).__name__
        == "cryptoadvance.specter.util.specter_migrator"
    )
    assert (
        _get_module_from_class(Service).__name__
        == "cryptoadvance.specter.services.service"
    )


def test_get_class():
    assert type(get_class("cryptoadvance.specter.device.Device")) == type(Device)
    assert get_class("cryptoadvance.specter.node.Node").__name__ == "Node"

    # It doesn't make sense to raise SpecterErrors as the error messages aren't meaningful to the user
    with pytest.raises(
        SpecterInternalException,
        match="Could not find cryptoadvance.specter.node.notExisting",
    ):
        get_class("cryptoadvance.specter.node.notExisting")
    with pytest.raises(
        SpecterInternalException,
        match="Could not find cryptoadvance.notExisting.notExisting",
    ):
        get_class("cryptoadvance.notExisting.notExisting")


def test_get_package_dir_for_subclasses_of():
    assert get_package_dir_for_subclasses_of(SpecterMigration).endswith(
        "cryptoadvance/specter/util/migrations"
    )
    assert get_package_dir_for_subclasses_of(Service).endswith(
        "cryptoadvance/specterext"
    )


def test_get_classlist_from_importlist(caplog):
    caplog.set_level(logging.DEBUG)
    modulelist = [
        "cryptoadvance.specterext.swan.service",
    ]
    classlist = get_classlist_of_type_clazz_from_modulelist(Service, modulelist)
    assert len(classlist) == 1  # Happy to remove that at some point
    assert SwanService in classlist
    classlist = get_classlist_of_type_clazz_from_modulelist(
        Device, ["cryptoadvance.specter.devices.bitbox02"]
    )
    assert len(classlist) == 1
    assert BitBox02 in classlist


def test_get_subclasses_for_clazz_in_cwd(caplog):
    caplog.set_level(logging.DEBUG)
    classlist: List[type] = get_subclasses_for_clazz_in_cwd(
        Service, cwd="./tests/xtestdata_testextensions"
    )
    # damn, this is difficult to test
    # assert len(classlist) == 3


def test_get_subclasses_for_class(caplog):
    caplog.set_level(logging.DEBUG)
    classlist = get_subclasses_for_clazz(SpecterMigration)
    assert len(classlist) >= 3
    classlist = get_subclasses_for_clazz(Service)
    assert len(classlist) == 5  # Happy to remove that at some point
    assert SwanService in classlist
    assert ElectrumService in classlist
    assert DevhelpService in classlist
