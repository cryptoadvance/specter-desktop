import logging
import sys
import pytest
import os
from unittest.mock import MagicMock
from flask import Flask
from cryptoadvance.specter.managers.service_manager import ServiceManager
from cryptoadvance.specter.services.callbacks import after_serverpy_init_app


def test_ServiceManager2(mock_specter, mock_flaskapp, caplog):
    ctx = mock_flaskapp.app_context()
    ctx.push()
    sm = ServiceManager(mock_specter, "alpha")
    # We have passed the TestConfig which is (hopefully) not existing in the Swan Extension
    # So the ServiceManager will move up the dependency tree of TestConfig until it finds
    # a Config and will copy the keys into the flask-config
    assert mock_flaskapp.config["SWAN_API_URL"] == "https://api.dev.swanbitcoin.com"
    assert sm.services["swan"] != None

    sm.execute_ext_callbacks(after_serverpy_init_app, scheduler=None)


@pytest.mark.skip(reason="The .buildenv directoy does not exist on the CI-Infra")
def test_ServiceManager_get_service_x_dirs(caplog):
    caplog.set_level(logging.DEBUG)
    try:
        os.chdir("./pyinstaller")
        # THis is usefull in the pytinstaller/specterd.spec
        dirs = ServiceManager.get_service_x_dirs("templates")
        # As the tests are executed in a development-environment (pip3 install -e .), the results we get back here
        # are not the same than the one we would get back when really are building. Because in that case,
        # the .buildenv would the environment and no symlinks would link to src/cryptoadavance...
        expected_folder = (
            f"../.buildenv/lib/python{sys.version_info[0]}.{sys.version_info[1]}/src"
        )
        # however, in the real build, you get something like:
        # ../.buildenv/lib/python3.8/site-packages/cryptoadvance/specter/services/swan/templates
        assert f"{expected_folder}/cryptoadvance/specter/services/swan/templates" in [
            str(dir) for dir in dirs
        ]
        for path in dirs:
            assert str(path).endswith("templates")

        dirs = ServiceManager.get_service_x_dirs("static")
        assert f"{expected_folder}/cryptoadvance/specter/services/swan/static" in [
            str(dir) for dir in dirs
        ]
        assert (
            f"{expected_folder}/cryptoadvance/specter/services/bitcoinreserve/static"
            in [str(dir) for dir in dirs]
        )
        print(dirs)
        assert len(dirs) >= 2
    finally:
        os.chdir("../")


def test_ServiceManager_get_service_packages(caplog):
    caplog.set_level(logging.DEBUG)
    packages = ServiceManager.get_service_packages()
    assert "cryptoadvance.specterext.electrum.service" in packages
    assert "cryptoadvance.specterext.electrum.devices.electrum" in packages
    assert "cryptoadvance.specterext.swan.service" in packages


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
    # The ServiceManager is a flask-aware component. It will load all the services
    # however, in order to configure them, he needs to know about the configuration
    # of the specterApp.
    flaskapp_mock.config[
        "SPECTER_CONFIGURATION_CLASS_FULLNAME"
    ] = "cryptoadvance.specter.config.TestConfig"
    return flaskapp_mock
