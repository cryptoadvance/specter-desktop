import json
import logging
import shutil

import pytest

from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.logic import (get_cli, Device, DeviceManager, Specter, Wallet, WalletManager,
                     alias)
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
    assert specter_regtest_configured.wallets is not None
    assert specter_regtest_configured.devices is not None
    assert specter_regtest_configured.config['rpc']['host'] != "None"
    logging.debug("out {}".format(specter_regtest_configured.test_rpc() ))
    json_return = json.loads(specter_regtest_configured.test_rpc()["out"] )
    # that might only work if your chain is fresh
    # assert json_return['blocks'] == 100
    assert json_return['chain'] == 'regtest'

def test_DeviceManager(empty_data_folder):
    # A DeviceManager manages devices, specifically the persistence 
    # of them via json-files in an empty data folder
    dm = DeviceManager(data_folder=empty_data_folder)
    # initialisation will load from the folder but i's empty, yet
    assert len(dm) == 0
    # a device has a name, a type and a list of keys
    a_key = {
        "derivation": "m/48h/1h/0h/2h",
        "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "fingerprint": "08686ac6",
        "type": "wsh",
        "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
    }
    # the DeviceManager doesn't care so much about the content of a key
    # so this is a minimal valid "key":
    another_key = {
        'original': 'blub'
    }
    dm.add("some_name","the_type",[a_key,another_key])
    assert dm.get_by_alias('some_name')['name'] == 'some_name'
    assert dm.get_by_alias('some_name')['type'] == 'the_type'
    assert dm.get_by_alias('some_name')['keys'][0]['fingerprint'] == '08686ac6'
    # Now it has a length of 1
    assert len(dm) == 1
    # and is iterable
    assert [the_type['type'] for the_type in dm] == ['the_type']
    # The DeviceManager will return Device-Types (subclass of dict)
    assert type(dm['some_name']) == Device

    # A device is mainly a Domain-Object which assumes an underlying 
    # json-file which can be found in the "fullpath"-key
    # It derives from a dict
    # It needs a DeviceManager to be injected and can't reasonable
    # be created on your own.
    some_device = dm['some_name']
    assert some_device['fullpath'] == empty_data_folder + '/some_name.json'

    # keys can be added and removed. It will instantly update the underlying json
    # TBD: more explanational tests

def test_WalletManager(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder,bitcoin_regtest.get_cli(),"regtest")
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('trezor')
    assert device != None
    key = {
            "derivation": "m/84h/1h/0h",
            "original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko",
            "fingerprint": "1ef4e492",
            "type": "wpkh",
            "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"
    }
    # Lets's create a wallet with the WalletManager
    wm.create_simple('a_test_wallet','wpkh',key,device)
    # The wallet-name gets its filename and therfore its alias
    wallet = wm.get_by_alias('a_test_wallet')
    assert wallet != None
    assert wallet.getbalances()['trusted'] == 0
    assert wallet.getbalances()['untrusted_pending'] == 0
    # this is a sum of both
    assert wallet.getfullbalance() == 0
    address = wallet.getnewaddress()
    # newly minted coins need 100 blocks to get spendable
    wallet.cli.generatetoaddress(1, address)
    # let's mine another 100 blocks to get these coins spendable
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(100, random_address)
    # a balance has properties which are caching the result from last call
    assert wallet.fullbalance == 0
    assert wallet.getfullbalance() == 50
    assert wallet.fullbalance == 50
    assert wallet.getbalance() == 50
    # Lets's spend something and create a PSBT to a random address

    psbt = wallet.createpsbt(random_address,10, True, 10)
    # the most relevant stuff of the above object:
    assert len(psbt['tx']['vin']) == 1 # 1 input
    assert psbt['tx']['vin'][0]['txid'] == "730b41bd1e77b65770bfec73304da5c34cc1bad100394e6f5cc020bb5dbe65fd"
    assert len(psbt['tx']['vout']) == 2 # 2 outputs
    # Now let's send some money to this wallet (creating 10 more potential inputs)
    for i in range(0,4): # 40 coins as a whole
        bitcoin_regtest.testcoin_faucet(address,10)
    assert wallet.getfullbalance() == 90
    assert wallet.getbalances()['untrusted_pending'] == 40
    assert wallet.getbalances()['trusted'] == 50
    # Even though the Bitcoin-API doesn't support spending more than 'trusted'
    try:
        wallet.cli.walletcreatefundedpsbt(
            [],                     # inputs (choose yourself)
            [{random_address: 60}], # output
            0,                      # locktime
            {},                     # options
            True                    # replaceable
        )
        assert False # excpected an exception
    except RpcError as rpce:
        assert rpce.error_msg == "Insufficient funds"
        pass
    # But wallet.createpsbt supports it (by explicitely specifying inputs)! 
    psbt = wallet.createpsbt(random_address, 60, True, 10)
    assert len(psbt['tx']['vin']) == 3
    assert psbt['tx']['vin'][2]['txid'] == '730b41bd1e77b65770bfec73304da5c34cc1bad100394e6f5cc020bb5dbe65fd'

