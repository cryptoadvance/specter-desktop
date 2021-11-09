import pytest
from cryptoadvance.specter.services.service_manager import ServiceManager
from cryptoadvance.specter.services.service_settings_manager import (
    ServiceSettingsManager,
)
from mock import patch, Mock


def test_ServiceSettingsManager(specter_regtest_configured):
    # A DeviceManager manages devices, specifically the persistence
    # of them via json-files in an empty data folder
    um = ServiceSettingsManager(specter_regtest_configured.data_folder, "vaultoro")

    with pytest.raises(Exception):
        assert um.get_key("admin", "wurstbrot")
    um.set_key("admin", "wurstbrot", "lecker")
    assert um.get_key("admin", "wurstbrot") == "lecker"
    um.set_key("admin", "other_key", {"yet_a_key": "yet_a_value"})
    assert um.get_key("admin", "other_key") == {"yet_a_key": "yet_a_value"}
    assert um.get_key("admin", "wurstbrot") == "lecker"


def test_ServiceManager(empty_data_folder):
    specter_mock = Mock()
    specter_mock.config = Mock()
    specter_mock.config.get.return_value = ["dummyservice"]
    assert specter_mock.config.get("services", []) == ["dummyservice"]
    specter_mock.data_folder.return_value = empty_data_folder

    sm = ServiceManager(specter_mock)
    scls = sm.get_service_classes()
    assert len(scls) == 2
    assert scls[0].id == "dummyservice"
    assert scls[1].id == "vaultoro"
    # assert False
