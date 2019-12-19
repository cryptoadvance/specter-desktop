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
            "user": bitcoin_regtest.rpcuser,
            "password": bitcoin_regtest.rpcpassword,
            "port": bitcoin_regtest.rpcport,
            "host": bitcoin_regtest.ipaddress,
            "protocol": "http"
        },
    }
    yield Specter(data_folder=data_folder, config=config)
    shutil.rmtree(data_folder, ignore_errors=True)
