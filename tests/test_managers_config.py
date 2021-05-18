import os
import time

from cryptoadvance.specter.managers.config_manager import ConfigManager
from mock import Mock, PropertyMock


def test_ConfigManager(empty_data_folder):
    cm = ConfigManager(data_folder=empty_data_folder)
    assert os.path.isfile(os.path.join(empty_data_folder, "config.json"))

    assert cm.data["auth"]["method"] == "none"
    # Should probably raise an Exception!
    cm.update_auth("muh", 11, 11)
    user_mock = Mock()
    cm.update_explorer("CUSTOM", {"url": "meh"}, user_mock, "regtest")
    cm.update_fee_estimator("bitcoin_core", "blub", user_mock)
