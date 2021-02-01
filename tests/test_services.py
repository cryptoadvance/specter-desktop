import os
from cryptoadvance.specter.services.service_settings_manager import (
    ServiceSettingsManager,
)
import pytest


def test_ServiceSettingsManager(specter_regtest_configured):
    # A DeviceManager manages devices, specifically the persistence
    # of them via json-files in an empty data folder
    um = ServiceSettingsManager(specter_regtest_configured, "vaultoro")

    with pytest.raises(Exception):
        assert um.get_key("admin", "wurstbrot")
    um.set_key("admin", "wurstbrot", "lecker")
    assert um.get_key("admin", "wurstbrot") == "lecker"
    um.set_key("admin", "other_key", {"yet_a_key": "yet_a_value"})
    assert um.get_key("admin", "other_key") == {"yet_a_key": "yet_a_value"}
    assert um.get_key("admin", "wurstbrot") == "lecker"
