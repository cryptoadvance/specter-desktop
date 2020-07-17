import json, logging, pytest
from cryptoadvance.specter.specter import get_cli, Specter
from cryptoadvance.specter.helpers import alias
from cryptoadvance.specter.rpc import BitcoinCLI


def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"

@pytest.mark.skip(reason="no idea why this does not pass on gitlab exclusively")
def test_get_cli(specter_regtest_configured):
    specter_regtest_configured.check()
    rpc_config_data = {
        "autodetect": False,
        "user": "bitcoin",
        "password": "secret",
        "port": specter_regtest_configured.config['rpc']['port'],
        "host": "localhost",
        "protocol": "http"
    }
    print("rpc_config_data: {}".format(rpc_config_data))
    cli = get_cli(rpc_config_data)
    assert cli.getblockchaininfo() 
    assert isinstance(cli, BitcoinCLI)
    # ToDo test autodetection-features

def test_specter(specter_regtest_configured,caplog): 
    caplog.set_level(logging.DEBUG)
    specter_regtest_configured.check()
    assert specter_regtest_configured.wallet_manager is not None
    assert specter_regtest_configured.device_manager is not None
    assert specter_regtest_configured.config['rpc']['host'] != "None"
    logging.debug("out {}".format(specter_regtest_configured.test_rpc() ))
    json_return = json.loads(specter_regtest_configured.test_rpc()["out"] )
    # that might only work if your chain is fresh
    # assert json_return['blocks'] == 100
    assert json_return['chain'] == 'regtest'
