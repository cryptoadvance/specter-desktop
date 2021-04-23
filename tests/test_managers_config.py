import os
import time

from cryptoadvance.specter.managers.config_manager import ConfigManager
from mock import Mock, PropertyMock


def test_ConfigManager(empty_data_folder):
    cm = ConfigManager(data_folder=empty_data_folder)
    assert os.path.isfile(os.path.join(empty_data_folder, "config.json"))

    assert cm.rpc_conf["host"] == "localhost"
    assert cm.bitcoin_datadir.endswith(".bitcoin")
    cm.set_bitcoind_pid(123)
    cm.update_use_external_node(True)
    # Should probably raise an Exception!
    cm.update_auth("muh", 11, 11)
    user_mock = Mock()
    cm.update_explorer("CUSTOM", {"url": "meh"}, user_mock, "regtest")
    cm.update_fee_estimator("bitcoin_core", "blub", user_mock)
