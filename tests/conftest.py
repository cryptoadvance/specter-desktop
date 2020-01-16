import atexit
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time

import pytest
import docker
from bitcoind import BitcoindDockerController, BitcoindPlainController

from logic import Specter, DeviceManager


def pytest_addoption(parser):
    ''' Internally called to add options to pytest 
        see pytest_generate_tests(metafunc) on how to check that
    '''
    parser.addoption("--docker", action="store_true", help="run bitcoind in docker")

def pytest_generate_tests(metafunc):
    #ToDo: use custom compiled version of bitcoind
    # E.g. test again bitcoind version [currentRelease] + master-branch
    if "docker" in metafunc.fixturenames:
        if metafunc.config.getoption("docker"):
            # That's a list because we could do both (see above) but currently that doesn't make sense in that context
            metafunc.parametrize("docker", [True],scope="module")
        else:
            metafunc.parametrize("docker", [False], scope="module")

@pytest.fixture(scope="module")
def bitcoin_regtest(docker):
    #logging.getLogger().setLevel(logging.DEBUG)
    if docker:
        bitcoind_controller = BitcoindDockerController(rpcport=18543)
    else:
        if os.path.isfile('tests/bitcoin/src/bitcoind'):
            bitcoind_controller = BitcoindPlainController(bitcoind_path='tests/bitcoin/src/bitcoind') # always prefer the self-compiled bitcoind if existing
        else:
            bitcoind_controller = BitcoindPlainController() # Alternatively take the one on the path for now

    bitcoind_controller.start_bitcoind(cleanup_at_exit=True)
    return bitcoind_controller


@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_2789334'
    shutil.rmtree(data_folder, ignore_errors=True)
    os.mkdir(data_folder)
    yield data_folder
    shutil.rmtree(data_folder, ignore_errors=True)

@pytest.fixture
def devices_filled_data_folder(empty_data_folder):
    os.makedirs(empty_data_folder+"/devices")
    with open(empty_data_folder+"/devices/trezor.json", "w") as text_file:
        text_file.write('''
{
    "name": "Trezor",
    "type": "trezor",
    "keys": [
        {
            "derivation": "m/49h/0h/0h",
            "original": "ypub6XFn7hfb676MLm6ZsAviuQKXeRDNgT9Bs32KpRDPnkKgKDjKcrhYCXJ88aBfy8co2k9eujugJX5nwq7RPG4sj6yncDEPWN9dQGmFWPy4kFB",
            "fingerprint": "1ef4e492",
            "type": "sh-wpkh",
            "xpub": "xpub6CRWp2zfwRYsVTuT2p96hKE2UT4vjq9gwvW732KWQjwoG7v6NCXyaTdz7NE5yDxsd72rAGK7qrjF4YVrfZervsJBjsXxvTL98Yhc7poBk7K"
        },
        {
            "derivation": "m/84h/0h/0h",
            "original": "zpub6rGoJTXEhKw7hUFkjMqNctTzojkzRPa3VFuUWAirqpuj13mRweRmnYpGD1aQVFpxNfp17zVU9r7F6oR3c4zL3DjXHdewVvA7kjugHSqz5au",
            "fingerprint": "1ef4e492",
            "type": "wpkh",
            "xpub": "xpub6CcGh8BQPxr9zssX4eG8CiGzToU6Y9b3f2s2wNw65p9xtr8ySL6eYRVzAbfEVSX7ZPaPd3JMEXQ9LEBvAgAJSkNKYxG6L6X9DHnPWNQud4H"
        },
        {
            "derivation": "m/48h/0h/0h/1h",
            "original": "Ypub6jtWQ1r2D7EwqNoxERU28MWZH4WdL3pWdN8guFJRBTmGwstJGzMXJe1VaNZEuAAVsZwpKPhs5GzNPEZR77mmX1mjwzEiouxmQYsrxFBNVNN",
            "fingerprint": "1ef4e492",
            "type": "sh-wsh",
            "xpub": "xpub6EA9y7SfVU96ZWTTTQDR6C5FPJKvB59RPyxoCb8zRgYzGbWAFvogbTVRkTeBLpHgETm2hL7BjQFKNnL66CCoaHyUFBRtpbgHF6YLyi7fr6m"
        },
        {
            "derivation": "m/48h/0h/0h/2h",
            "original": "Zpub74imhgWwMnnRkSPkiNavCQtSBu1fGo8RP96h9eT2GHCgN5eFU9mZVPhGphvGnG26A1cwJxtkmbHR6nLeTw4okpCDjZCEj2HRLJoVHAEsch9",
            "fingerprint": "1ef4e492",
            "type": "wsh",
            "xpub": "xpub6EA9y7SfVU96dGr96zYgxAMd8AgWBCTqEeQafbPi8VcWdhStCS4AA9X4yb3dE1VM7GKLwRhWy4BpD3VkjK5q1riMAQgz9oBSu8QKv5S7KzD"
        },
        {
            "derivation": "m/49h/1h/0h",
            "original": "upub5EKoQv21nQNkhdt4yuLyRnWitA3EGhW1ru1Y8VTG8gdys2JZhqiYkhn4LHp2heHnH41kz95bXPvrYVRuFUrdUMik6YdjFV4uL4EubnesttQ",
            "fingerprint": "1ef4e492",
            "type": "sh-wpkh",
            "xpub": "tpubDDCDr9rSwixeXKeGwAgwFy8bjBaE5wya9sAVqEC4ccXWmcQxY34KmLRJdwmaDsCnHsu5r9P9SUpYtXmCoRwukWDqmAUJgkBbjC2FXUzicn6"
        },
        {
            "derivation": "m/84h/1h/0h",
            "original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko",
            "fingerprint": "1ef4e492",
            "type": "wpkh",
            "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"
        },
        {
            "derivation": "m/48h/1h/0h/1h",
            "original": "Upub5Tk9tZtdzVaTGWtygRTKDDmaN5vfB59pn2L5MQyH6BkVpg2Y5J95rtpQndjmXNs3LNFiy8zxpHCTtvxxeePjgipF7moTHQZhe3E5uPzDXh8",
            "fingerprint": "1ef4e492",
            "type": "sh-wsh",
            "xpub": "tpubDFiVCZzdarbyfdVoh2LJDL3eVKRPmxwnkiqN8tSYCLod75a2966anQbjHajqVAZ97j54xZJPr9hf7ogVuNL4pPCfwvXdKGDQ9SjZF7vXQu1"
        },
        {
            "derivation": "m/48h/1h/0h/2h",
            "original": "Vpub5naRCEZZ9B7wCKLWuqoNdg6ddWEx8ruztUygXFZDJtW5LRMqUP5HV2TsNw1nc74Ba3QPDSH7qzauZ8LdfNmnmofpfmztCGPgP7vaaYSmpgN",
            "fingerprint": "1ef4e492",
            "type": "wsh",
            "xpub": "tpubDFiVCZzdarbyk8kE65tjRhHCambEo8iTx4xkXL8b33BKZj66HWsDnUb3rg4GZz6Mwm6vTNyzRCjYtiScCQJ77ENedb2deDDtcoNQXiUouJQ"
        }
    ]
}
''')
    return empty_data_folder # no longer empty, though
    

@pytest.fixture
def wallets_filled_data_folder(devices_filled_data_folder):
    os.makedirs(os.path.join(devices_filled_data_folder,"wallets","regtest"))
    with open(os.path.join(devices_filled_data_folder,"wallets","regtest","simple.json"), "w") as json_file:
        json_file.write('''
{
    "alias": "simple",
    "fullpath": "/home/kim/.specter/wallets/regtest/simple.json",
    "name": "Simple",
    "address_index": 0,
    "keypool": 5,
    "address": "bcrt1qcatuhg0gll3h7py4cmn53rjjn9xlsqfwj3zcej",
    "change_index": 0,
    "change_address": "bcrt1qt28v03278lmmxllys89acddp2p5y4zds94944n",
    "change_keypool": 5,
    "type": "simple",
    "description": "Single (Segwit)",
    "key": {
        "derivation": "m/84h/1h/0h",
        "original": "vpub5Y35MNUT8sUR2SnRCU9A9S6z1JDACMTuNnM8WHXvuS7hCwuVuoRAWJGpi66Yo8evGPiecN26oLqx19xf57mqVQjiYb9hbb4QzbNmFfsS9ko",
        "fingerprint": "1ef4e492",
        "type": "wpkh",
        "xpub": "tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc"
    },
    "recv_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/0/*)#xp8lv5nr",
    "change_descriptor": "wpkh([1ef4e492/84h/1h/0h]tpubDC5EUwdy9WWpzqMWKNhVmXdMgMbi4ywxkdysRdNr1MdM4SCfVLbNtsFvzY6WKSuzsaVAitj6FmP6TugPuNT6yKZDLsHrSwMd816TnqX7kuc/1/*)#h4z73prm",
    "device": "Trezor",
    "device_type": "trezor",
    "address_type": "bech32"
}

''')
    return devices_filled_data_folder # and with wallets obviously

@pytest.fixture
def device_manager(devices_filled_data_folder):
    return DeviceManager(os.path.join(devices_filled_data_folder,"devices"))

@pytest.fixture
def specter_regtest_configured(bitcoin_regtest):
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_3456778'
    shutil.rmtree(data_folder, ignore_errors=True)
    config = {
        "rpc": {
            "autodetect": False,
            "user": bitcoin_regtest.rpcconn.rpcuser,
            "password": bitcoin_regtest.rpcconn.rpcpassword,
            "port": bitcoin_regtest.rpcconn.rpcport,
            "host": bitcoin_regtest.rpcconn.ipaddress,
            "protocol": "http"
        },
    }
    yield Specter(data_folder=data_folder, config=config)
    shutil.rmtree(data_folder, ignore_errors=True)
