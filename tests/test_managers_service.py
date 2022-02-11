import logging
from unittest.mock import MagicMock
from flask import Flask
from cryptoadvance.specter.managers.service_manager import ServiceManager


def test_ServiceManager(caplog):
    caplog.set_level(logging.DEBUG)
    specter_mock = MagicMock()
    specter_mock.config = {"services": {}}
    flaskapp_mock = Flask(__name__)
    flaskapp_mock.config["EXTENSION_LIST"] = [
        "cryptoadvance.specter.services.swan.service",
        "cryptoadvance.specter.services.bitcoinreserve.service",
    ]
    flaskapp_mock.config["ISOLATED_CLIENT_EXT_URL_PREFIX"] = "/spc/ext"
    flaskapp_mock.config["EXT_URL_PREFIX"] = "/ext"

    ctx = flaskapp_mock.app_context()
    ctx.push()
    # The ServiceManager is a flask-aware component. It will load all the services
    # however, in order to configure them, he needs to know about the configuration
    # of the specterApp.
    flaskapp_mock.config[
        "SPECTER_CONFIGURATION_CLASS_FULLNAME"
    ] = "cryptoadvance.specter.config.TestConfig"
    sm = ServiceManager(specter_mock, "alpha")
    # We have passed the TestConfig which is (hopefully) not existing in the Swan Extension
    # So the ServiceManager will move up the dependency tree of TestConfig until it finds
    # a Config and will copy the keys into the flask-config
    assert flaskapp_mock.config["SWAN_API_URL"] == "https://dev-api.swanbitcoin.com"
    assert sm.services["bitcoinreserve"] != None
    assert sm.services["swan"] != None

    # THis is usefull in the pytinstaller/specterd.spec
    dirs = ServiceManager.get_service_x_dirs("templates")
    assert "../src/cryptoadvance/specter/services/swan/templates" in [
        str(dir) for dir in dirs
    ]
    assert len(dirs) >= 1  # Should not need constant update

    dirs = ServiceManager.get_service_x_dirs("static")
    assert "../src/cryptoadvance/specter/services/swan/static" in [
        str(dir) for dir in dirs
    ]
    assert "../src/cryptoadvance/specter/services/bitcoinreserve/static" in [
        str(dir) for dir in dirs
    ]
    assert len(dirs) >= 2

    packages = ServiceManager.get_service_packages()
    assert "cryptoadvance.specter.services.swan.service" in packages
    assert "cryptoadvance.specter.services.bitcoinreserve.service" in packages
