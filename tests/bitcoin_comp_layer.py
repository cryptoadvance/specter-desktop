""" This module tries to leverage the Bitcoin test_framework for Specter testing
    It needs the contents of bitcoin/test/functional/test_framework in this directory

"""

import base64
import logging
import subprocess
import sys
from collections import namedtuple
from decimal import Decimal, getcontext
from time import time

from cryptoadvance.specter.rpc import BitcoinRPC

sys.path
sys.path.append("./tests/bitcoin/test/functional")

from test_framework.authproxy import AuthServiceProxy, JSONRPCException
from test_framework.descriptors import descsum_create
from test_framework.test_framework import (
    BitcoinTestFramework,
    BitcoinTestMetaClass,
    TestStatus,
)
from test_framework.util import (
    assert_equal,
    assert_fee_amount,
    assert_greater_than,
    assert_raises_rpc_error,
    count_bytes,
    get_auth_cookie,
    rpc_port,
)

logger = logging.getLogger(__name__)


class SpecterBitcoinTestMetaClass(BitcoinTestMetaClass):
    """Override __new__ to remove the TypeError caused by overriding main() in SpecterBitcoinTestFramework.
    I can understand the intention but that doesn't help use here
    """

    def __new__(cls, clsname, bases, dct):
        return type.__new__(cls, clsname, bases, dct)


HTTP_TIMEOUT = 30
USER_AGENT = "AuthServiceProxy/0.1"


class SpecterAuthServiceProxy(AuthServiceProxy):
    """A class which behaves like a BitcoinRpc but is derived from AuthServiceProxy"""

    def __init__(self, auth_service_proxy):
        self.__service_url = auth_service_proxy.__service_url
        self._service_name = auth_service_proxy._service_name
        self.ensure_ascii = (
            auth_service_proxy.ensure_ascii
        )  # can be toggled on the fly by tests
        self.__url = auth_service_proxy.__url
        self.__auth_header = auth_service_proxy.__auth_header
        self.timeout = auth_service_proxy.timeout
        self.__conn = auth_service_proxy.__conn

    def test_connection(self):
        """returns a boolean depending on whether getblockchaininfo() succeeds"""
        try:
            self.getblockchaininfo()
            return True
        except:
            return False


class SpecterBitcoinTestFramework(
    BitcoinTestFramework, metaclass=SpecterBitcoinTestMetaClass
):
    """A bridge class to leverage the Bitcoin test_framework within Specter Tests. It provides:
    * bitcoin_rpc(), a convenience method to get a BitcoinRpc from a node
    * overrides the main-method to suppress sys.exit() (and needs a custom Metaclass for this)
    * adds the "option" of the corresponding test itself
    """

    def bitcoin_rpc(self, node_number=0):
        """The testFramework uses AuthProxy and you can get an instance via .rpc
        Specter uses for the rpc-communication something similiar, a self created BitcoinRpc-class
        This method delivers a working BitcoinRpc for the nodes[node_number]
        """
        user, password = get_auth_cookie(self.nodes[node_number].datadir, "regtest")
        # print(f"bitcoin-cli -rpcconnect=127.0.0.1  -rpcport={rpc_port(0)} -rpcuser=__cookie__ -rpcpassword={password} getblockchaininfo")
        rpc = BitcoinRPC(
            host="127.0.0.1",
            user="__cookie__",
            password=password.strip(),
            port=rpc_port(node_number),
        )
        return rpc

    def add_options(self, parser):
        """Add an option to enable that this test is initialized within a pytest which might have the
        the file as an argument and other potential arguments which are not suppose to be used within
        the tests at all.
        """

        parser.add_argument(f"tests/{self.__module__}.py")
        parser.add_argument("-full", "--full-trace", required=False)
        parser.add_argument("-junit", "--junitxml", required=False)

    def run_test(self):
        """We need to specify that here because the BitcoinTestMetaClass is checking that"""
        raise Exception("You have to override this method")

    def set_test_params(self):
        """We need to specify that here because the BitcoinTestMetaClass is checking that"""
        raise Exception("You have to override this method")

    def main(self):
        """Main function. This should not be overridden by the subclass test scripts.

        Oh, yes, we have to in order to get rid of the sys.exit() commented below and make some other
        changes for making that more compatible with pytest
        """

        assert hasattr(
            self, "num_nodes"
        ), "Test must set self.num_nodes in set_test_params()"
        startTime = time()
        try:
            self.setup()
            self.run_test()
            print("FINISHED****************************************")
            self.success = TestStatus.PASSED
        except JSONRPCException:
            logger.exception("JSONRPC error")
            self.success = TestStatus.FAILED
        except AssertionError:
            logger.exception("Assertion failed")
            self.success = TestStatus.FAILED
        except KeyError:
            logger.exception("Key error")
            self.success = TestStatus.FAILED
        except subprocess.CalledProcessError as e:
            logger.exception("Called Process failed with '{}'".format(e.output))
            self.success = TestStatus.FAILED
        except Exception:
            logger.exception("Unexpected exception caught during testing")
            self.success = TestStatus.FAILED
        except KeyboardInterrupt:
            logger.warning("Exiting after keyboard interrupt")
            self.success = TestStatus.FAILED
        finally:
            exit_code = self.shutdown()
            # sys.exit(exit_code)
            if self.success == TestStatus.FAILED:
                raise Exception("Test Failed")
            if exit_code != 0:
                raise Exception(
                    f"bitcoind did not shutdown cleanly but with exit_code {exit_code}"
                )
        return time() - startTime
