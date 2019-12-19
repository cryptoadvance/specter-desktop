import json
import logging
import shutil

import pytest

from specter import Specter, alias, DeviceManager, Device, WalletManager, Wallet

def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"

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
    from specter import DeviceManager
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

def test_WalletManager(empty_data_folder):
    wm = WalletManager(empty_data_folder,None,"regtest")
    #wm.create_simple("first_wallet",)


