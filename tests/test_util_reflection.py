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
    is_specter_desktop_project,
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


def test_get_classlist_skips_missing_module(caplog):
    """Missing modules should be skipped with a warning when skip_missing=True.
    Regression test for #2496."""
    caplog.set_level(logging.WARNING)
    modulelist = [
        "cryptoadvance.specterext.swan.service",
        "cryptoadvance.specterext.nonexistent_extension.service",
        "cryptoadvance.specterext.devhelp.service",
    ]
    classlist = get_classlist_of_type_clazz_from_modulelist(
        Service, modulelist, skip_missing=True
    )
    # Should load swan and devhelp, skip the missing one
    assert SwanService in classlist
    assert DevhelpService in classlist
    assert len(classlist) == 2
    # Should have logged a warning about the missing module
    assert "Skipping module" in caplog.text
    assert "nonexistent_extension" in caplog.text


def test_get_classlist_skips_missing_module_empty_list(caplog):
    """If ALL modules are missing, should return empty list, not crash."""
    caplog.set_level(logging.WARNING)
    modulelist = [
        "cryptoadvance.specterext.totally_fake.service",
    ]
    classlist = get_classlist_of_type_clazz_from_modulelist(
        Service, modulelist, skip_missing=True
    )
    assert classlist == []
    assert "Skipping module" in caplog.text


def test_get_classlist_raises_on_missing_module_by_default():
    """Without skip_missing, missing modules should still raise (strict mode)."""
    modulelist = [
        "cryptoadvance.specterext.nonexistent_extension.service",
    ]
    with pytest.raises(ModuleNotFoundError):
        get_classlist_of_type_clazz_from_modulelist(Service, modulelist)


repo_root = Path(__file__).parent.parent
xtestdata = repo_root / "tests" / "xtestdata_testextensions"


def test_is_specter_desktop_project():
    """The specter-desktop project detects itself via the name in its own
    pyproject.toml. If that name changes (PEP 503 allows "." "-" and "_" to be
    used interchangeably), the dev-server dies on startup, see #2526."""
    assert is_specter_desktop_project(repo_root)
    assert not is_specter_desktop_project(xtestdata / "ext_root_fully_qualified_1")
    assert not is_specter_desktop_project(xtestdata)


def test_is_specter_desktop_project_pep503_names(tmp_path):
    for name in [
        "cryptoadvance.specter",
        "cryptoadvance_specter",
        "Cryptoadvance-Specter",
    ]:
        (tmp_path / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "1.2.3"\n'
        )
        assert is_specter_desktop_project(tmp_path), f"{name} should be detected"

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "boatacccorp.tretboot"\n'
    )
    assert not is_specter_desktop_project(tmp_path)


def test_get_subclasses_for_clazz_in_cwd_in_specter_desktop_project(monkeypatch):
    """No dynamic extension-discovery in the specter-desktop project itself.
    Regression test: this used to raise "This should not happen!" when the
    project got renamed to cryptoadvance_specter, breaking
    `python3 -m cryptoadvance.specter server --config DevelopmentConfig`"""
    # the production code takes a shortcut for tests, so pretend we're not testing
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert get_subclasses_for_clazz_in_cwd(Service, cwd=repo_root) == []


def test_get_subclasses_for_clazz_in_cwd(caplog):
    caplog.set_level(logging.DEBUG)
    classlist: List[type] = get_subclasses_for_clazz_in_cwd(Service, cwd=xtestdata)
    # That folder is a container of extension-projects, not an extension-project
    # itself, so there is nothing importable in there
    assert classlist == []
    assert "Detected Extension-style: adhoc" in caplog.text


def test_get_subclasses_for_class(caplog):
    caplog.set_level(logging.DEBUG)
    classlist = get_subclasses_for_clazz(SpecterMigration)
    assert len(classlist) >= 3
    classlist = get_subclasses_for_clazz(Service)
    assert len(classlist) == 5  # Happy to remove that at some point
    assert SwanService in classlist
    assert ElectrumService in classlist
    assert DevhelpService in classlist
