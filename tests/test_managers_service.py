from unittest.mock import MagicMock
from cryptoadvance.specter.services.service_manager import ServiceManager


def test_ServiceManager(app_no_node):
    specter_mock = MagicMock()
    specter_mock.config = {"services": {}}
    sm = ServiceManager(specter_mock, "alpha")
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
