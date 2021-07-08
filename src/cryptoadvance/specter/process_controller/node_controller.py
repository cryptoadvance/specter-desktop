""" Stuff to control a bitcoind-instance.
"""
import atexit
import json
import logging
import os
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time

import psutil
from cryptoadvance.specter.liquid.rpc import LiquidRPC
from requests.exceptions import ConnectionError
from urllib3.exceptions import MaxRetryError, NewConnectionError

from ..helpers import load_jsons
from ..rpc import BitcoinRPC, RpcError
from ..specter_error import ExtProcTimeoutException, SpecterError
from ..util.shell import get_last_lines_from_file, which

logger = logging.getLogger(__name__)


class Btcd_conn:
    """An object to easily store connection data to bitcoind-comatible nodes (Bitcoin/Elements)"""

    def __init__(
        self,
        node_impl="bitcoin",
        rpcuser="bitcoin",
        rpcpassword="secret",
        rpcport=18543,
        ipaddress=None,
    ):
        self.node_impl = node_impl
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
    def ipaddress(self, ipaddress):
        self._ipaddress = ipaddress

    def get_rpc(self):
        """returns a BitcoinRPC"""
        if self.node_impl == "bitcoin":
            rpc = BitcoinRPC(
                self.rpcuser, self.rpcpassword, host=self.ipaddress, port=self.rpcport
            )
        elif self.node_impl == "elements":
            rpc = LiquidRPC(
                self.rpcuser, self.rpcpassword, host=self.ipaddress, port=self.rpcport
            )
        else:
            raise SpecterError(f"Unknown node_impl: {self.node_impl}")
        rpc.getblockchaininfo()
        return rpc

    def render_url(self, password_mask=False):
        if password_mask == True:
            password = "xxxxxx"
        else:
            password = self.rpcpassword
        return "http://{}:{}@{}:{}/wallet/".format(
            self.rpcuser, password, self.ipaddress, self.rpcport
        )

    def as_data(self):
        """returns a data-representation of this connection"""
        me = {
            "user": self.rpcuser,
            "password": self.rpcpassword,
            "host": self.ipaddress,
            "port": self.rpcport,
            "url": self.render_url(),
        }
        return me

    def render_json(self):
        """returns a json-representation of this connection"""
        return json.dumps(self.as_data())

    def __repr__(self):
        return "<Btcd_conn {}>".format(self.render_url())


class NodeController:
    """A kind of abstract class to simplify running a bitcoind with or without docker"""

    def __init__(
        self,
        node_impl,
        rpcport=18443,
        network="regtest",
        rpcuser="bitcoin",
        rpcpassword="secret",
    ):
        try:
            self.rpcconn = Btcd_conn(
                node_impl=node_impl,
                rpcuser=rpcuser,
                rpcpassword=rpcpassword,
                rpcport=rpcport,
            )
            self.network = network
            self.node_impl = node_impl
            # reasonable default
            self.cleanup_hard = False
        except Exception as e:
            logger.exception(f"Failed to instantiate BitcoindController. Error: {e}")
            raise e

    def start_node(
        self,
        cleanup_at_exit=False,
        cleanup_hard=False,
        datadir=None,
        extra_args=[],
        timeout=60,
    ):
        """starts bitcoind with a specific rpcport=18543 by default.
        That's not the standard in order to make pytest running while
        developing locally against a different regtest-instance
        if bitcoind_path == docker, it'll run bitcoind via docker.
        Specify a longer timeout for slower devices (e.g. Raspberry Pi)
        """
        if not self.check_existing() is None:
            # This should not happen. For bitcoind, have a look in BitcoindController.attach_to_proc_id()
            raise SpecterError(
                f"While starting Node, there is already a Node running at {self.rpcconn.render_url(password_mask=True)}"
            )

        self._start_node(
            cleanup_at_exit,
            cleanup_hard=cleanup_hard,
            datadir=datadir,
            extra_args=extra_args,
        )
        try:
            self.wait_for_node(self.rpcconn, timeout=timeout)
            self.status = "Running"
        except ExtProcTimeoutException as e:
            if self.node_proc.poll() is None:
                self.status = "error"
                raise Exception(f"Could not start node due to: {self.get_debug_log()}")
            self.status = "Starting up"
            logger.error(self.node_proc.stdout)
            raise e
        except Exception as e:
            self.status = "Error"
            raise e
        logger.info(f"Successfully started {self.node_impl}d in {self.datadir}")
        if "" not in self.get_rpc().listwallets():
            logger.info("Creating Default-wallet")
            self.get_rpc().createwallet("", False, False, "", False, True, True)

        if self.network == "regtest":
            logger.debug(f"Mining 100 blocks (network: {self.network})")
            self.mine(block_count=100)

        return self.rpcconn

    def version(self):
        raise Exception("version needs to be overridden by Subclassses")

    def is_testnet(self):
        return self.network not in [
            "mainnet",
            "main",
            "liquidv1",
            "None",
            "none",
            None,
            "",
        ]

    def is_liquid(self):
        return self.network not in [
            "main",
            "mainnet",
            "regtest",
            "test",
            "signet",
            "None",
            "none",
            None,
            "",
        ]

    def get_rpc(self):
        """wrapper for convenience"""
        return self.rpcconn.get_rpc()

    def _start_node(
        self, cleanup_at_exit, cleanup_hard=False, datadir=None, extra_args=[]
    ):
        raise Exception(f"This should not be used in the baseclass! self: {self}")

    def get_debug_log(self):
        raise Exception(f"This should not be used in the baseclass! self: {self}")

    def check_existing(self):
        raise Exception(f"This should not be used in the baseclass! self: {self}")

    def stop_node(self):
        raise Exception(f"This should not be used in the baseclass! self: {self}")

    def mine(self, address=None, block_count=1):
        """Does mining to the attached address with as many as block_count blocks"""
        if address == None:
            if self.node_impl == "bitcoin":
                address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
            else:
                address = "el1qqf6tv4n8qp55qc04v4xts5snd9v5uurkry4vskef6lmecahj6c42jt9lnj0432287rs67z9vzq2zvuer036s5mahptwxgyd8k"
        self.get_rpc().generatetoaddress(block_count, address)

    def testcoin_faucet(self, address, amount=20):
        """an easy way to get some testcoins"""
        rpc = self.get_rpc()
        try:
            default_rpc = rpc.wallet("")
            default_rpc.getbalance()
        except RpcError as rpce:
            # return-codes:
            # https://github.com/bitcoin/bitcoin/blob/v0.15.0.1/src/rpc/protocol.h#L32L87
            if rpce.error_code == -18:  # RPC_WALLET_NOT_FOUND
                logger.debug("Creating default wallet")
                rpc.createwallet("")
                default_rpc = rpc.wallet("")
            else:
                raise rpce
        balance = default_rpc.getbalance()
        if isinstance(balance, dict):
            balance = balance["bitcoin"]  # elements
        logger.debug("balance:" + str(balance))
        default_address = default_rpc.getnewaddress("")
        if self.node_impl == "elements":
            default_address = default_rpc.getaddressinfo(default_address)[
                "unconfidential"
            ]
        while True:
            btc_balance = default_rpc.getbalance()
            rpc.generatetoaddress(102, default_address)
            if btc_balance > amount:
                break
        default_rpc.sendtoaddress(address, amount)

    @staticmethod
    def check_node(rpcconn, raise_exception=False):
        """returns true if bitcoind is running on that address/port"""
        if raise_exception:
            rpcconn.get_rpc()  # that call will also check the connection
            return True
        try:
            rpcconn.get_rpc()  # that call will also check the connection
            return True
        except RpcError as e:
            # E.g. "Loading Index ..." #ToDo: check it here
            return False
        except ConnectionError as e:
            return False
        except MaxRetryError as e:
            return False
        except TypeError as e:
            return False
        except NewConnectionError as e:
            return False
        except Exception as e:
            # We should avoid this:
            # If you see it in the logs, catch that new exception above
            logger.error("Unexpected Exception, THIS SHOULD NOT HAPPEN " + str(type(e)))
            logger.debug(f"could not reach bitcoind - message returned: {e}")
            return False

    @staticmethod
    def wait_for_node(rpcconn, timeout=15):
        """tries to reach the bitcoind via rpc. Timeout after n seconds"""
        i = 0
        while True:
            if NodeController.check_node(rpcconn):
                break
            time.sleep(0.5)
            i = i + 1
            if i % 10 == 0:
                logger.info(f"Node timeout in {timeout - i/2} seconds")
            if i > (2 * timeout):
                try:
                    NodeController.check_node(rpcconn, raise_exception=True)
                except Exception as e:
                    if "Verifying blocks..." in str(e) or "Loading wallet..." in str(e):
                        # Timed out too soon while node is still spinning up
                        logger.info("Giving node more time to restart...")
                        i = 0
                        pass
                    else:
                        raise ExtProcTimeoutException(
                            f"Timeout while trying to reach node {rpcconn.render_url(password_mask=True)} because {e}".format(
                                rpcconn
                            )
                        )

    @staticmethod
    def render_rpc_options(rpcconn):
        options = " -rpcport={} -rpcuser={} -rpcpassword={} ".format(
            rpcconn.rpcport, rpcconn.rpcuser, rpcconn.rpcpassword
        )
        return options

    @classmethod
    def construct_node_cmd(
        cls,
        rpcconn,
        run_docker=True,
        datadir=None,
        node_path="bitcoind",
        network="regtest",
        extra_args=[],
    ):
        """returns a command to run your node (bitcoind/elementsd)"""
        btcd_cmd = '"{}" '.format(node_path)
        if network != "mainnet" and network != "main":
            btcd_cmd += " -{} ".format(network)
        btcd_cmd += " -fallbackfee=0.0002 "
        btcd_cmd += " -port={} -rpcport={} -rpcbind=0.0.0.0 -rpcbind=0.0.0.0".format(
            rpcconn.rpcport - 1, rpcconn.rpcport
        )
        btcd_cmd += " -rpcuser={} -rpcpassword={} ".format(
            rpcconn.rpcuser, rpcconn.rpcpassword
        )
        btcd_cmd += " -rpcallowip=0.0.0.0/0 -rpcallowip=172.17.0.0/16 "
        if not run_docker:
            btcd_cmd += " -noprinttoconsole"
            if datadir == None:
                datadir = tempfile.mkdtemp(prefix="bitcoind_datadir")
            btcd_cmd += ' -datadir="{}" '.format(datadir)
        if extra_args:
            btcd_cmd += " {}".format(" ".join(extra_args))
        logger.debug("constructed bitcoind-command: %s", btcd_cmd)
        return btcd_cmd


class NodePlainController(NodeController):
    """A class controlling the bitcoind-process directly on the machine"""

    def __init__(
        self,
        node_impl,
        node_path="bitcoind",
        rpcport=18443,
        network="regtest",
        rpcuser="bitcoin",
        rpcpassword="secret",
    ):
        try:
            super().__init__(
                node_impl,
                rpcport=rpcport,
                network=network,
                rpcuser=rpcuser,
                rpcpassword=rpcpassword,
            )
            self.node_path = node_path
            self.rpcconn.ipaddress = "localhost"
            self.status = "Down"
        except Exception as e:
            logger.exception(f"Failed to instantiate NodePlainController. Error: {e}")
            raise e

    def _start_node(
        self, cleanup_at_exit=True, cleanup_hard=False, datadir=None, extra_args=[]
    ):
        if datadir == None:
            datadir = tempfile.mkdtemp(
                prefix=f"specter_{self.node_impl}_regtest_plain_datadir_"
            )
        self.datadir = datadir

        node_cmd = self.construct_node_cmd(
            self.rpcconn,
            run_docker=False,
            datadir=datadir,
            node_path=self.node_path,
            network=self.network,
            extra_args=extra_args,
        )
        logger.debug("About to execute: {}".format(node_cmd))
        # exec will prevent creating a child-process and will make node_proc.terminate() work as expected
        self.node_proc = subprocess.Popen(
            ("exec " if platform.system() != "Windows" else "") + node_cmd,
            shell=True,
        )
        time.sleep(0.2)  # sleep 200ms (catch stdout of stupid errors)
        if not self.node_proc.poll() is None:
            # Might itself raise a SpecterError:
            debug_logs = self.get_debug_log()
            raise SpecterError(f"Could not start node due to:" + debug_logs)
        logger.debug(
            f"Running {self.node_impl}d-process with pid {self.node_proc.pid} in datadir {datadir}"
        )

        # This function is redirecting to the class.member as it needs a fixed parameterlist: (signal_number, stack)
        def cleanup_node_callback(signal_number=None, stack=None):
            self.cleanup_node(cleanup_hard, datadir)

        # If the node is shutdown via self.stop_node() (e.g. pytests) we need to know how hard we should do that
        self.cleanup_hard = cleanup_hard

        if cleanup_at_exit:
            logger.info(
                "Register function cleanup_node for atexit, SIGINT, and SIGTERM"
            )
            atexit.register(cleanup_node_callback)
            # This is for CTRL-C --> SIGINT
            signal.signal(signal.SIGINT, cleanup_node_callback)
            # This is for kill $pid --> SIGTERM
            signal.signal(signal.SIGTERM, cleanup_node_callback)

    def get_debug_log(self):

        logfile_location = os.path.join(
            self.datadir,
            self.network if self.network != "testnet" else "testnet3",
            "debug.log",
        )
        try:
            return "".join(get_last_lines_from_file(logfile_location))
        except FileNotFoundError as e:
            raise SpecterError(
                f"Could not find debug.log at {logfile_location}. Is that directory even existing?"
            )
        except Exception as e:
            logger.exception(f"Failed to get debug logs. Error: {e}")
            return "[Failed to get debug logs. Check the logs for details]"

    def cleanup_node(self, cleanup_hard=None, datadir=None):
        """KILLS or TERMINATES the node-process depending on cleanup_hard
        removes the datadir in case of KILL
        """
        returnvalue = True  # assume only the best
        if not hasattr(self, "datadir"):
            self.datadir = None

        if cleanup_hard == None:
            cleanup_hard = self.cleanup_hard
        if not hasattr(self, "node_proc"):
            logger.info("node process was not running")
            if cleanup_hard:
                logger.info(f"Removing node datadir: {datadir}")
                if datadir is None:
                    datadir = self.datadir
                shutil.rmtree(datadir, ignore_errors=True)
            returnvalue = False
        timeout = 50  # in secs
        logger.info(
            f"Cleaning up (cleanup_hard:{cleanup_hard} , datadir:{self.datadir})"
        )
        if cleanup_hard:
            try:
                self.node_proc.kill()  # might be usefull for e.g. testing. We can't wait for so long
                logger.info(
                    f"Killed {self.node_impl}d with pid {self.node_proc.pid}, Removing {self.datadir}"
                )
                shutil.rmtree(self.datadir, ignore_errors=True)
            except Exception as e:
                logger.error(e)
                returnvalue = False
        else:
            try:
                if not hasattr(self, "node_proc"):
                    returnvalue = False
                else:
                    self.node_proc.terminate()  # might take a bit longer than kill but it'll preserve block-height
                    logger.info(
                        f"Terminated {self.node_impl}d with pid {self.node_proc.pid}, waiting for termination (timeout {timeout} secs)..."
                    )
                    # self.node_proc.wait() # doesn't have a timeout
                    procs = psutil.Process().children()
                    for p in procs:
                        p.terminate()
                    _, alive = psutil.wait_procs(procs, timeout=timeout)
                    for p in alive:
                        logger.info(
                            f"{self.node_impl} did not terminated in time, killing!"
                        )
                        p.kill()
            except ProcessLookupError:
                # Bitcoind probably never came up or crashed.
                returnvalue = False
        if platform.system() == "Windows":
            subprocess.run("Taskkill /IM bitcoind.exe /F")
        return returnvalue

    def stop_node(self):
        success = self.cleanup_node()
        self.status = "Down"
        return success

    def check_existing(self):
        """other then in docker, we won't check on the "instance-level". This will return true if a
        node is running on the default port.
        """
        if not self.check_node(self.rpcconn):
            if self.status == "Running":
                self.status = "Down"
            return None
        else:
            self.status = "Running"
            return True


def find_node_executable(node_impl):
    '''Returns the path to a node_impl executable whereas node_impl is either "bitcoin" or "elements"'''
    if os.path.isfile(f"tests/{node_impl}/src/{node_impl}d"):
        # copied from conftest.py
        # always prefer the self-compiled bitcoind if existing
        return f"tests/{node_impl}/src/{node_impl}d"
    elif os.path.isfile(f"./tests/{node_impl}/bin/{node_impl}d"):
        # next take the self-installed binary if existing
        return f"tests/{node_impl}/bin/{node_impl}d"
    else:
        # First list files in the folders above:
        logger.warning(f"Couldn't find reasonable executable for {node_impl}")
        # hmmm, maybe we have a bitcoind on the PATH
        return which(f"{node_impl}d")


def fetch_wallet_addresses_for_mining(node_impl, data_folder):
    """parses all the wallet-jsons in the folder (default ~/.specter/wallets/regtest)
    and returns an array with the addresses
    """
    wallet_folder = (
        f"{data_folder}/wallets/{'regtest' if node_impl == 'bitcoin' else 'elreg'}"
    )
    wallets = load_jsons(wallet_folder)
    address_array = [value["address"] for key, value in wallets.items()]
    # remove duplicates
    address_array = list(dict.fromkeys(address_array))
    return address_array
