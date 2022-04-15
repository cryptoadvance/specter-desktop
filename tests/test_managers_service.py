import logging
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
    assert mock_flaskapp.config["SWAN_API_URL"] == "https://dev-api.swanbitcoin.com"
    assert sm.services["bitcoinreserve"] != None
    assert sm.services["swan"] != None

    sm.execute_ext_callbacks(after_serverpy_init_app, scheduler=None)


def test_ServiceManager_get_service_x_dirs():
    try:
        os.chdir("./pyinstaller")
        # THis is usefull in the pytinstaller/specterd.spec
        dirs = ServiceManager.get_service_x_dirs("templates")
        assert "../src/cryptoadvance/specter/services/swan/templates" in [
            str(dir) for dir in dirs
        ]
        for path in dirs:
            assert str(path).endswith("templates")

        dirs = ServiceManager.get_service_x_dirs("static")
        assert "../src/cryptoadvance/specter/services/swan/static" in [
            str(dir) for dir in dirs
        ]
        assert "../src/cryptoadvance/specter/services/bitcoinreserve/static" in [
            str(dir) for dir in dirs
        ]
        print(dirs)
        assert len(dirs) >= 2
    finally:
        os.chdir("../")


def test_ServiceManager_get_service_packages():
    packages = ServiceManager.get_service_packages()
    assert "cryptoadvance.specter.services.swan.service" in packages
    assert "cryptoadvance.specter.services.bitcoinreserve.service" in packages


@pytest.fixture
def mock_specter():
    specter_mock = MagicMock()
    specter_mock.config = {"services": {}}
    return specter_mock


@pytest.fixture
def mock_flaskapp(mock_specter):

    flaskapp_mock = Flask(__name__)
    flaskapp_mock.config["EXTENSION_LIST"] = [
        "cryptoadvance.specter.services.swan.service",
        "cryptoadvance.specter.services.bitcoinreserve.service",
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
