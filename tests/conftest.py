import atexit
import json
import os
import shutil
import subprocess
import tempfile
import time

import pytest
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

import docker
from bitcoind import BitcoindDockerController, BitcoindPlainController


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

def start_bitcoind(bitcoind_path, cleanup_at_exit=True, rpc_port=18543):
    if bitcoind_path == "docker":
        bitcoind_controller = BitcoindDockerController()
    else:
        bitcoind_controller = BitcoindPlainController()
    print("    --> Starting bitcoind based on {}".format(bitcoind_path))
    bitcoind_controller.start_bitcoind(cleanup_at_exit)
    return bitcoind_controller.rpcconn


@pytest.fixture(scope="module")
def bitcoin_regtest(docker):
    if docker:
        bitcoind_path = 'docker'
    else:
        if os.path.isfile('tests/bitcoin/src/bitcoind'):
            bitcoind_path = 'tests/bitcoin/src/bitcoind ' # always prefer the self-compiled bitcoind if existing
        else:
            bitcoind_path = 'bitcoind ' # Alternatively take the one on the path for now
    btc_conn = start_bitcoind(bitcoind_path)
    return btc_conn

# for testing purposes only
# This will make all the print-statements available which are not shown up via "pytest --docker"
# python3 tests/conftest.py
if __name__ == '__main__':
    start_bitcoind('docker')
