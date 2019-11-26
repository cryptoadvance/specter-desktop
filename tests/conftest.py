import pytest
import os


import atexit
import subprocess
import tempfile
import shutil
import json
import time
#import unittest

from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

def start_bitcoind(bitcoind_path, cleanup_at_exit=True, rpc_port=18543):
    ''' starts bitcoind with a specific rpcport=18543 by default.
        That's not the standard in order to make pytest running while
        developing locally against a different regtest-instance
    '''
    datadir = tempfile.mkdtemp()
    bitcoind_proc = subprocess.Popen([
        bitcoind_path, '-regtest', 
        '-datadir=' + datadir, 
        '-port=18544',
        '-rpcport=' + str(rpc_port), 
        '-noprinttoconsole'
    ])
    def cleanup_bitcoind():
        bitcoind_proc.kill()
        shutil.rmtree(datadir)
    if cleanup_at_exit:
        atexit.register(cleanup_bitcoind) 
    # Wait for cookie file to be created
    # ToDo: Why not acively setting rpc_username/password?!
    while not os.path.exists(datadir + '/regtest/.cookie'):
        time.sleep(0.5)
    # Read .cookie file to get user and pass
    with open(datadir + '/regtest/.cookie') as f:
        rpc_username, rpc_password = f.readline().lstrip().rstrip().split(':')
    rpc = AuthServiceProxy('http://{}:{}@127.0.0.1:{}/wallet/'.format(rpc_username, rpc_password, rpc_port))

    # Wait for bitcoind to be ready
    ready = False
    while not ready:
        try:
            rpc.getblockchaininfo()
            ready = True
        except JSONRPCException:
            time.sleep(0.5)
            pass

    # Make sure there are blocks and coins available
    rpc.generatetoaddress(101, rpc.getnewaddress())
    return (rpc, rpc_username, rpc_password, rpc_port)



@pytest.fixture(scope="module")
def bitcoin_regtest():
    btc_conn = {}
    #ToDo: compile our own version of bitcoind
    #bitcoind_path = os.path.join(test_dir, 'bitcoin/src/bitcoind')
    #bitcoind_path = '/usr/local/bin/bitcoind'
    bitcoind_path = 'bitcoind' # Let's take the one on the path for now
    btc_conn['rpc'], btc_conn['rpc_username'], btc_conn['rpc_password'], btc_conn['rpc_port'] = start_bitcoind(bitcoind_path)
    return btc_conn