import shutil
import pytest
import json
from specter import Specter, alias



@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_2789334'
    shutil.rmtree(data_folder, ignore_errors=True) 
    yield data_folder
    shutil.rmtree(data_folder, ignore_errors=True)

@pytest.fixture
def specter_regtest_configured(bitcoin_regtest):
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_3456778'
    shutil.rmtree(data_folder, ignore_errors=True)
    config = {
        "rpc": {
            "autodetect": False,
            "user": bitcoin_regtest["rpc_username"],
            "password": bitcoin_regtest["rpc_password"],
            "port": bitcoin_regtest["rpc_port"],
            "host": "localhost",
            "protocol": "http"
        },
    }
    yield Specter(data_folder=data_folder, config=config)
    shutil.rmtree(data_folder, ignore_errors=True)


def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"

def test_specter(specter_regtest_configured):
    specter_regtest_configured.check()
    assert specter_regtest_configured.wallets is not None
    assert specter_regtest_configured.devices is not None
    json_return = json.loads(specter_regtest_configured.test_rpc()["out"] )
    assert json_return['blocks'] == 101
    assert json_return['chain'] == 'regtest'

def test_device(empty_data_folder):
    from specter import DeviceManager
    my_dm = DeviceManager(data_folder=empty_data_folder)