import logging
import sys
import pytest
from pathlib import PosixPath, Path
import os
from unittest.mock import MagicMock
from flask import Flask
from cryptoadvance.specter.managers.service_manager import ExtensionManager
from cryptoadvance.specter.services.callbacks import after_serverpy_init_app

from cryptoadvance.specterext.swan.service import SwanService
from cryptoadvance.specterext.swan.service import SwanClient
from cryptoadvance.specterext.devhelp.service import DevhelpService


def test_ExtensionManager2(mock_specter, mock_flaskapp, caplog):
    ctx = mock_flaskapp.app_context()
    ctx.push()
    sm = ExtensionManager(mock_specter, "alpha")
    # We have passed the TestConfig which is (hopefully) not existing in the Swan Extension
    # So the ExtensionManager will move up the dependency tree of TestConfig until it finds
    # a Config and will copy the keys into the flask-config
    assert mock_flaskapp.config["SWAN_API_URL"] == "https://api.dev.swanbitcoin.com"
    assert sm.services["swan"] != None

    sm.execute_ext_callbacks(after_serverpy_init_app, scheduler=None)


def test_is_class_from_loaded_extension(mock_specter, mock_flaskapp):
    with mock_flaskapp.app_context():
        sm = ExtensionManager(mock_specter, "alpha")
        assert type(sm.services_sorted[0]) == SwanService
        assert sm.is_class_from_loaded_extension(SwanClient)
        assert sm.is_class_from_loaded_extension(SwanService)
        assert not sm.is_class_from_loaded_extension(DevhelpService)


@pytest.mark.skip(reason="The .buildenv directoy does not exist on the CI-Infra")
def test_ExtensionManager_get_service_x_dirs(caplog):
    caplog.set_level(logging.DEBUG)
    try:
        os.chdir("./pyinstaller")
        # THis is usefull in the pytinstaller/specterd.spec
        dirs = ExtensionManager.get_service_x_dirs("templates")
        # As the tests are executed in a development-environment (pip3 install -e .), the results we get back here
        # are not the same than the one we would get back when really are building. Because in that case,
        # the .buildenv would the environment and no symlinks would link to src/cryptoadavance...
        expected_folder = (
            f"../.buildenv/lib/python{sys.version_info[0]}.{sys.version_info[1]}/src"
        )
        # however, in the real build, you get something like:
        # ../.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates
        assert f"{expected_folder}/cryptoadvance/specterext/swan/templates" in [
            str(dir) for dir in dirs
        ]
        for path in dirs:
            assert str(path).endswith("templates")

        dirs = ExtensionManager.get_service_x_dirs("static")
        assert f"{expected_folder}/cryptoadvance/specterext/swan/static" in [
            str(dir) for dir in dirs
        ]
        print(dirs)
        assert len(dirs) >= 2000
        assert False
    finally:
        os.chdir("../")


def test_ServiceManager_get_service_packages(caplog):
    caplog.set_level(logging.DEBUG)

    packages = ExtensionManager.get_service_packages()
    assert "cryptoadvance.specterext.electrum.service" in packages
    assert "cryptoadvance.specterext.electrum.devices.electrum" in packages
    assert "cryptoadvance.specterext.swan.service" in packages
    assert "cryptoadvance.specterext.electrum.service" in packages
    assert "cryptoadvance.specterext.electrum.devices.electrum" in packages
    assert "cryptoadvance.specterext.devhelp.service" in packages
    assert "cryptoadvance.specterext.liquidissuer.service" in packages

    assert "cryptoadvance.specter.util.migrations.migration_0000" in packages
    assert "cryptoadvance.specter.util.migrations.migration_0001" in packages
    assert "cryptoadvance.specter.util.migrations.migration_0002" in packages

    # This needs to be adjusted with each new extension
    # We don't need to assert every single package but we also ensure with that, that we don't
    # loose anything on the way of changing something in the service_manager
    assert len(packages) == 31


def test_ServiceManager_make_path_relative(caplog):
    caplog.set_level(logging.DEBUG)
    arr = [
        Path(
            "/home/kim/src/specter-desktop/.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates"
        ),
        Path("wurstbrot/something/.env/site-packages/the_rest"),
    ]
    arr = [ExtensionManager._make_path_relative(path) for path in arr]
    assert arr[0] == PosixPath(
        "site-packages/cryptoadvance/specter/services/swan/templates"
    )
    assert arr[1] == PosixPath("site-packages/the_rest")


@pytest.fixture
def mock_specter():
    specter_mock = MagicMock()
    specter_mock.config = {"services": {}}
    return specter_mock


@pytest.fixture
def mock_flaskapp(mock_specter):

    flaskapp_mock = Flask(__name__)
    flaskapp_mock.config["EXTENSION_LIST"] = [
        "cryptoadvance.specterext.swan.service",
    ]
    flaskapp_mock.config["ISOLATED_CLIENT_EXT_URL_PREFIX"] = "/spc/ext"
    flaskapp_mock.config["EXT_URL_PREFIX"] = "/ext"
    # The ExtensionManager is a flask-aware component. It will load all the services
    # however, in order to configure them, he needs to know about the configuration
    # of the specterApp.
    flaskapp_mock.config[
        "SPECTER_CONFIGURATION_CLASS_FULLNAME"
    ] = "cryptoadvance.specter.config.TestConfig"
    return flaskapp_mock
