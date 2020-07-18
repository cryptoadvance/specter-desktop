''' Stuff to control a bitcoind-instance. Either directly by access to a bitcoind-executable or
    via docker.
'''
import atexit
import logging
import os
import shutil
import subprocess
import tempfile
import time

import docker

from .helpers import which
from .server import DATA_FOLDER
from .rpc import RpcError
from .rpc import BitcoinCLI
from .helpers import load_jsons

logger = logging.getLogger(__name__)

class Btcd_conn:
    ''' An object to easily store connection data '''
    def __init__(self, rpcuser="bitcoin", rpcpassword="secret", rpcport=18543, ipaddress=None):
        self.rpcport = rpcport
        self.rpcuser = rpcuser
        self.rpcpassword = rpcpassword
        self._ipaddress = ipaddress

    @property
    def ipaddress(self):
        if self._ipaddress == None:
            raise Exception("ipadress is none")
        else:
            return self._ipaddress


    @ipaddress.setter
    def ipaddress(self,ipaddress):
        self._ipaddress = ipaddress

    def get_cli(self):
        ''' returns a BitcoinCLI '''
        # def __init__(self, user, passwd, host="127.0.0.1", port=8332, protocol="http", path="", timeout=30, **kwargs):
        cli = BitcoinCLI(self.rpcuser, self.rpcpassword, host=self.ipaddress, port=self.rpcport)
        cli.getblockchaininfo()
        return cli

    def render_url(self):
        return 'http://{}:{}@{}:{}/wallet/'.format(self.rpcuser, self.rpcpassword, self.ipaddress, self.rpcport)
    
    def __repr__(self):
        return '<Btcd_conn {}>'.format(self.render_url())

class BitcoindController:
    ''' A kind of abstract class to simplify running a bitcoind with or without docker '''
    def __init__(self, rpcport=18443):
        self.rpcconn = Btcd_conn(rpcport=rpcport)

    def start_bitcoind(self, cleanup_at_exit=False):
        ''' starts bitcoind with a specific rpcport=18543 by default.
            That's not the standard in order to make pytest running while
            developing locally against a different regtest-instance
            if bitcoind_path == docker, it'll run bitcoind via docker
        '''
        if self.check_existing() != None:
            return self.check_existing()

        logger.debug("Starting bitcoind")
        self._start_bitcoind(cleanup_at_exit)

        self.wait_for_bitcoind(self.rpcconn)
        self.mine(block_count=100)
        return self.rpcconn


    def version(self):
        ''' Returns the version of bitcoind, e.g. "v0.19.1" '''
        version = self.get_cli().getnetworkinfo()['subversion']
        version = version.replace('/','').replace('Satoshi:','v')
        return version

    def get_cli(self):
        ''' wrapper for convenience '''
        return self.rpcconn.get_cli()

    def _start_bitcoind(self, cleanup_at_exit):
        raise Exception("This should not be used in the baseclass!")

    def check_existing(self):
        raise Exception("This should not be used in the baseclass!")

    def stop_bitcoind(self):
        raise Exception("This should not be used in the baseclass!")

    def mine(self, address="mruae2834buqxk77oaVpephnA5ZAxNNJ1r", block_count=1):
        ''' Does mining to the attached address with as many as block_count blocks '''
        self.rpcconn.get_cli().generatetoaddress(block_count, address)
    
    def testcoin_faucet(self, address, amount=20, mine_tx=False):
        ''' an easy way to get some testcoins '''
        cli = self.get_cli()
        try:
            test3rdparty_cli = cli.wallet("test3rdparty")
            test3rdparty_cli.getbalance()
        except RpcError as rpce:
            # return-codes:
            # https://github.com/bitcoin/bitcoin/blob/v0.15.0.1/src/rpc/protocol.h#L32L87
            if rpce.error_code == -18: # RPC_WALLET_NOT_FOUND
                logger.debug("Creating test3rdparty wallet")
                cli.createwallet("test3rdparty")
                test3rdparty_cli = cli.wallet("test3rdparty")
            else:
                raise rpce
        balance = test3rdparty_cli.getbalance()
        if balance < amount:
            test3rdparty_address = test3rdparty_cli.getnewaddress("test3rdparty")
            cli.generatetoaddress(102, test3rdparty_address)
        test3rdparty_cli.sendtoaddress(address,amount)
        if mine_tx:
            cli.generatetoaddress(1, test3rdparty_address)
        
    @staticmethod
    def check_bitcoind(rpcconn):
        ''' returns true if bitcoind is running on that address/port '''
        try:
            rpcconn.get_cli() # that call will also check the connection
            return True
        except ConnectionRefusedError:
            return False
        except TypeError:
            return False
        except Exception:
            return False

    @staticmethod
    def wait_for_bitcoind(rpcconn):
        ''' tries to reach the bitcoind via rpc. Will timeout after 10 seconds '''
        i = 0
        while True:
            if BitcoindController.check_bitcoind(rpcconn):
                break
            time.sleep(0.5)
            i = i + 1
            if i > 20:
                raise Exception("Timeout while trying to reach bitcoind at rpcport {} !".format(rpcconn))
        
    @staticmethod
    def render_rpc_options(rpcconn):
        options = " -rpcport={} -rpcuser={} -rpcpassword={} ".format(rpcconn.rpcport, rpcconn.rpcuser,rpcconn.rpcpassword)
        return options

    
    @classmethod
    def construct_bitcoind_cmd(cls, rpcconn, run_docker=True,datadir=None, bitcoind_path='bitcoind'):
        ''' returns a bitcoind-command to run bitcoind '''
        btcd_cmd = "{} ".format(bitcoind_path)
        btcd_cmd += " -regtest "
        btcd_cmd += " -fallbackfee=0.0002 "
        btcd_cmd += " -port={} -rpcport={} -rpcbind=0.0.0.0 -rpcbind=0.0.0.0".format(rpcconn.rpcport-1,rpcconn.rpcport)
        btcd_cmd += " -rpcuser={} -rpcpassword={} ".format(rpcconn.rpcuser,rpcconn.rpcpassword)
        btcd_cmd += " -rpcallowip=0.0.0.0/0 -rpcallowip=172.17.0.0/16 "
        if not run_docker:
            btcd_cmd += " -noprinttoconsole"
            if datadir == None:
                datadir = tempfile.mkdtemp(prefix="bitcoind_datadir")
            btcd_cmd += " -datadir={} ".format(datadir)
        logger.debug("constructed bitcoind-command: %s",btcd_cmd)
        return btcd_cmd

class BitcoindPlainController(BitcoindController):
    ''' A class controlling the bicoind-process directly on the machine '''
    def __init__(self, bitcoind_path='bitcoind', rpcport=18443):
        super().__init__(rpcport=rpcport)
        self.bitcoind_path = bitcoind_path
        self.rpcconn.ipaddress = 'localhost'

    def _start_bitcoind(self, cleanup_at_exit=False):
        datadir = tempfile.mkdtemp(prefix="bitcoind_plain_datadir")
        bitcoind_cmd = self.construct_bitcoind_cmd(self.rpcconn, run_docker=False, datadir=datadir, bitcoind_path=self.bitcoind_path)
        logger.debug("About to execute: {}".format(bitcoind_cmd))
        # exec will prevent creating a child-process and will make bitcoind_proc.terminate() work as expected
        self.bitcoind_proc = subprocess.Popen("exec " + bitcoind_cmd, shell=True)  
        logger.debug("Running bitcoind-process with pid {}".format(self.bitcoind_proc.pid))
        def cleanup_bitcoind():
            self.bitcoind_proc.kill() # much faster then terminate() and speed is key here over being nice
            logger.debug("Killed bitcoind-process with pid {}".format(self.bitcoind_proc.pid))
            shutil.rmtree(datadir)
            logger.debug("removed temp-dir")
        if cleanup_at_exit:
            atexit.register(cleanup_bitcoind)
    
    def stop_bitcoind(self):
        # not necessary as the cleanup_bitcoind() will do it automatically!
        # ToDo: Implement it nevertheless
        pass
    
    def check_existing(self):
        ''' other then in docker, we won't check on the "instance-level". This will return true if if a 
            bitcoind is running on the default port. 
        '''
        if not self.check_bitcoind(self.rpcconn):
            return None
        else:
            return True

class BitcoindDockerController(BitcoindController):
    ''' A class specifically controlling a docker-based bitcoind-container '''
    def __init__(self,rpcport=18443, docker_tag="latest"):
        self.btcd_container = None
        super().__init__(rpcport=rpcport)
        self.docker_exec = which('docker')
        self.docker_tag=docker_tag
        if self.docker_exec == None:
            raise("Docker not existing!")
        if self.detect_bitcoind_container(rpcport) != None:
            rpcconn, self.btcd_container = self.detect_bitcoind_container(rpcport)
            self.rpcconn = rpcconn

    def _start_bitcoind(self, cleanup_at_exit):
        bitcoind_path = self.construct_bitcoind_cmd(self.rpcconn )
        dclient = docker.from_env()
        logger.debug("Running (in docker): {}".format(bitcoind_path))
        ports={
            '{}/tcp'.format(self.rpcconn.rpcport-1): self.rpcconn.rpcport-1, 
            '{}/tcp'.format(self.rpcconn.rpcport): self.rpcconn.rpcport
        }
        logger.debug("portmapping: {}".format(ports))
        image = dclient.images.get("registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{}".format(self.docker_tag))
        self.btcd_container = dclient.containers.run("registry.gitlab.com/cryptoadvance/specter-desktop/python-bitcoind:{}".format(self.docker_tag), bitcoind_path,  ports=ports, detach=True)
        def cleanup_docker_bitcoind():
            self.btcd_container.stop()
            self.btcd_container.remove()
        if cleanup_at_exit:
            atexit.register(cleanup_docker_bitcoind)
        logger.debug("Waiting for container {} to come up".format(self.btcd_container.id))
        self.wait_for_container()
        rpcconn, _ = self.detect_bitcoind_container(self.rpcconn.rpcport)
        if rpcconn == None:
            raise Exception("Couldn't find container or it died already. Check the logs!")
        else:
            self.rpcconn = rpcconn
        return 
        

    def stop_bitcoind(self):
        if self.btcd_container != None:
            self.btcd_container.reload()
            if self.btcd_container.status == 'running':
                _, container = self.detect_bitcoind_container(self.rpcconn.rpcport)
                if container == self.btcd_container:
                    self.btcd_container.stop()
                    logger.info("Stopped btcd_container {}".format(self.btcd_container))
                    return 
        raise Exception('Ambigious Container running')

    def check_existing(self):
        ''' Checks whether self.btcd_container is up2date and not ambigious '''
        if self.btcd_container != None:
            self.btcd_container.reload()
            if self.btcd_container.status == 'running':
                rpcconn, container = self.detect_bitcoind_container(self.rpcconn.rpcport)
                if container == self.btcd_container:
                    return rpcconn
                raise Exception('Ambigious Container running')
        return None

    @staticmethod
    def search_bitcoind_container(all=False):
        ''' returns a list of containers which are running bitcoind '''
        d_client = docker.from_env()
        return [c for c in d_client.containers.list(all) if (c.attrs['Config'].get('Cmd')or[""])[0]=='bitcoind']

    @staticmethod
    def detect_bitcoind_container(with_rpcport):
        ''' checks all the containers for a bitcoind one, parses the arguments and initializes 
            the object accordingly 
            returns rpcconn, btcd_container
        '''
        d_client = docker.from_env()
        potential_btcd_containers = BitcoindDockerController.search_bitcoind_container()
        if len(potential_btcd_containers) == 0:
            logger.debug("could not detect container. Candidates: {}".format(d_client.containers.list()))
            all_candidates = BitcoindDockerController.search_bitcoind_container(all=True)
            logger.debug("could not detect container. All Candidates: {}".format(all_candidates))
            if len(all_candidates) > 0:
                logger.debug("100 chars of logs of first candidate")
                logger.debug(all_candidates[0].logs()[0:100])
            return None
        for btcd_container in potential_btcd_containers:
            rpcport = int([arg for arg in btcd_container.attrs['Config']['Cmd'] if 'rpcport' in arg][0].split('=')[1])
            if rpcport != with_rpcport:
                logger.debug("checking port {} against searched port {}".format(type(rpcport), type(with_rpcport)))
                continue
            rpcpassword = [arg for arg in btcd_container.attrs['Config']['Cmd'] if 'rpcpassword' in arg][0].split('=')[1]
            rpcuser = [arg for arg in btcd_container.attrs['Config']['Cmd'] if 'rpcuser' in arg][0].split('=')[1]
            if "CI" in os.environ: # this is a predefined variable in gitlab
                # This works on Linux (direct docker) and gitlab-CI but not on MAC
                ipaddress = btcd_container.attrs['NetworkSettings']['IPAddress']
            else:
                # This works on most machines but not on gitlab-CI
                ipaddress ="127.0.0.1"
            rpcconn = Btcd_conn(rpcuser=rpcuser, rpcpassword=rpcpassword, rpcport=rpcport, ipaddress=ipaddress)
            logger.info("detected container {}".format(btcd_container.id))
            return rpcconn, btcd_container
        logger.debug("No matching container found")
        return None

    
    def wait_for_container(self):
        ''' waits for the docker-container to come up. Times out after 10 seconds '''
        i = 0
        while True:
            ip_address = self.btcd_container.attrs['NetworkSettings']['IPAddress']
            if ip_address.startswith("172"):
                self.rpcconn.ipaddress = ip_address
                break
            self.btcd_container.reload()
            time.sleep(0.5)
            i = i + 1
            if i > 20:
                raise Exception("Timeout while starting bitcoind-docker-container!")


def fetch_wallet_addresses_for_mining(data_folder=None):
    ''' parses all the wallet-jsons in the folder (default ~/.specter/wallets/regtest)
        and returns an array with the addresses 
    '''
    if data_folder == None:
        data_folder = os.path.expanduser(DATA_FOLDER)
    wallets = load_jsons(data_folder+"/wallets/regtest")
    address_array = [ value['address'] for key, value in wallets.items()]
    # remove duplicates
    address_array = list( dict.fromkeys(address_array) )
    return address_array
