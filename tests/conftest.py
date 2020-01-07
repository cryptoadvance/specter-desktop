import atexit
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time

import pytest
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

import docker
from bitcoind import BitcoindDockerController, BitcoindPlainController

from specter import Specter


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
    return bitcoind_controller.rpcconn


@pytest.fixture
def empty_data_folder():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_2789334'
    shutil.rmtree(data_folder, ignore_errors=True)
    os.mkdir(data_folder)
    yield data_folder
    shutil.rmtree(data_folder, ignore_errors=True)

@pytest.fixture
def filled_data_folder(empty_data_folder):
    os.makedirs(empty_data_folder+"/wallets/regtest")
    with open(empty_data_folder+"/wallets/regtest/simple.json", "w") as text_file:
        text_file.write('''
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
    return empty_data_folder # no longer empty, though

@pytest.fixture
def specter_regtest_configured(bitcoin_regtest):
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_3456778'
    shutil.rmtree(data_folder, ignore_errors=True)
    config = {
        "rpc": {
            "autodetect": False,
            "user": bitcoin_regtest.rpcuser,
            "password": bitcoin_regtest.rpcpassword,
            "port": bitcoin_regtest.rpcport,
            "host": bitcoin_regtest.ipaddress,
            "protocol": "http"
        },
    }
    yield Specter(data_folder=data_folder, config=config)
    shutil.rmtree(data_folder, ignore_errors=True)
