import pytest
import os


import atexit
import subprocess
import tempfile
import shutil
import json
import time
import docker
#import unittest

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

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
    ''' starts bitcoind with a specific rpcport=18543 by default.
        That's not the standard in order to make pytest running while
        developing locally against a different regtest-instance
        if bitcoind_path == docker, it'll run bitcoind via docker
    '''
    rpc_user = "bitcoin"
    rpc_password = "wurst"
    exec_array = []
    exec_array.append(bitcoind_path)
    if bitcoind_path == "docker":
        run_docker = True
        bitcoind_path = "bitcoind "
    else:
        run_docker = False
    
    bitcoind_path += " -regtest "
    bitcoind_path += " -port=18544 -rpcport={} -rpcbind=0.0.0.0 -rpcbind=0.0.0.0".format(rpc_port)
    bitcoind_path += " -rpcuser={} -rpcpassword={} ".format(rpc_user,rpc_password)
    if not run_docker:
        bitcoind_path += " -noprinttoconsole"
        datadir = tempfile.mkdtemp()
        # This is not needed
        bitcoind_path += " -datadir={} ".format(datadir) 
        print("    --> About to execute: {}".format(bitcoind_path))
        bitcoind_proc = subprocess.Popen(bitcoind_path, shell=True)
        def cleanup_bitcoind():
            bitcoind_proc.kill()
            shutil.rmtree(datadir)
        if cleanup_at_exit:
            atexit.register(cleanup_bitcoind)
        ip_address = '127.0.0.1'
    else:

        bitcoind_path += " -rpcallowip=0.0.0.0/0 -rpcallowip=172.17.0.0/16 "
        dclient = docker.from_env()
        print("    --> Running (in docker): {}\n".format(bitcoind_path))
        docker_container = dclient.containers.run("registry.gitlab.com/k9ert/specter-desktop/python-bitcoind:latest", bitcoind_path,  ports={'18544/tcp': 18544, '18543/tcp': 18543}, detach=True)
        print("    --> Spun up Docker container:\n\n {}".format(docker_container.attrs))
        def cleanup_docker_bitcoind():
            docker_container.stop()
            docker_container.remove()
            pass
        if cleanup_at_exit:
            atexit.register(cleanup_docker_bitcoind)
        # ToDo figure out wheter the container is already running
        # That's not the way: while dclient.containers.list().length
        i = 0
        while True:
            ip_address = docker_container.attrs['NetworkSettings']['IPAddress']
            if ip_address.startswith("172"):
                break
            docker_container.reload()
            if i % 11 == 0:
                print(".", end='') 
            time.sleep(0.5)
            i = i + 1
            if i > 120:
                print("\n    --> TIMEOUT!")
                print("    --> bitcoind-logs: \n {}".format(docker_container.logs()))
                raise Exception("Timeout while starting bitcoind-docker-container!")
    url = 'http://{}:{}@{}:{}/wallet/'.format(rpc_user, rpc_password, ip_address, rpc_port)
    print("\n    --> trying to connect to: {}".format(url))
    while True:
        try:
            rpc = AuthServiceProxy(url)
            rpc.getblockchaininfo()
            print("\n    --> SUCCESSFULLY connected to bitcoind via {}:{}".format(ip_address, rpc_port))
            break
        except ConnectionRefusedError as cre:
            time.sleep(0.5)
        except TypeError:
            time.sleep(0.5)
        except JSONRPCException as jre:
            time.sleep(0.5)
        except Exception as e:
            if run_docker:
                print("\n    --> catched Exception {}".format(e))
                print("    --> bitcoind logs:{}".format(docker_container.logs()))
                raise e
            else:
                raise e

    print("    --> mine 100 blocks to make sure there are blocks and coins available")
    rpc.generatetoaddress(101, rpc.getnewaddress())
    return (rpc, rpc_user, rpc_password, ip_address, rpc_port)

@pytest.fixture(scope="module")
def bitcoin_regtest(docker):
    btc_conn = {}
    if docker:
        bitcoind_path = 'docker'
    else:
        bitcoind_path = 'bitcoind ' # Let's take the one on the path for now
    btc_conn['rpc'], btc_conn['rpc_username'], btc_conn['rpc_password'], btc_conn['rpc_host'], btc_conn['rpc_port'] = start_bitcoind(bitcoind_path)
    return btc_conn

# for testing purposes only
# This will make all the print-statements available which are not shown up via "pytest --docker"
# python3 tests/conftest.py
if __name__ == '__main__':
    start_bitcoind('docker')