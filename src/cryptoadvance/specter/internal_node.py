import json
import logging
import os

from .helpers import is_testnet
from .specter_error import SpecterError, ExtProcTimeoutException
from .rpc import (
    BitcoinRPC,
    RpcError,
    autodetect_rpc_confs,
    detect_rpc_confs,
    get_default_datadir,
)
from .process_controller.bitcoind_controller import BitcoindPlainController
from .persistence import write_node
from .node import Node

logger = logging.getLogger(__name__)


class InternalNode(Node):
    """A Node but other than Node, this one is managed by Specter.
    So it has start and stop methods and one called is_bitcoind_running
    """

    def __init__(
        self,
        name,
        alias,
        autodetect,
        datadir,
        user,
        password,
        port,
        host,
        protocol,
        fullpath,
        manager,
        bitcoind_path,
        bitcoind_network,
        version,
    ):
        super().__init__(
            name,
            alias,
            autodetect,
            datadir,
            user,
            password,
            port,
            host,
            protocol,
            False,
            fullpath,
            manager,
        )

        self.bitcoind_path = bitcoind_path
        self.bitcoind_network = bitcoind_network
        self._bitcoind = None
        self.bitcoin_pid = False
        self.version = version
        if self.bitcoind_network != "main":
            if self.bitcoind_network == "testnet" and not self.datadir.endswith(
                "/testnet3"
            ):
                self.datadir = os.path.join(self.datadir, "testnet3")
            elif self.bitcoind_network == "regtest" and not self.datadir.endswith(
                "/regtest"
            ):
                self.datadir = os.path.join(self.datadir, "regtest")
            elif self.bitcoind_network == "signet" and not self.datadir.endswith(
                "/signet"
            ):
                self.datadir = os.path.join(self.datadir, "signet")
            logger.info(f"persisting {self} in __init__")
            write_node(self, self.fullpath)

    @classmethod
    def from_json(cls, node_dict, manager, default_alias="", default_fullpath=""):
        name = node_dict.get("name", "")
        alias = node_dict.get("alias", default_alias)
        autodetect = node_dict.get("autodetect", True)
        datadir = node_dict.get("datadir", get_default_datadir())
        user = node_dict.get("user", "")
        password = node_dict.get("password", "")
        port = node_dict.get("port", None)
        host = node_dict.get("host", "localhost")
        protocol = node_dict.get("protocol", "http")
        external_node = node_dict.get("external_node", True)
        fullpath = node_dict.get("fullpath", default_fullpath)
        bitcoind_path = node_dict.get("bitcoind_path", "")
        bitcoind_network = node_dict.get("bitcoind_network", "main")
        version = node_dict.get("version", "")

        return cls(
            name,
            alias,
            autodetect,
            datadir,
            user,
            password,
            port,
            host,
            protocol,
            fullpath,
            manager,
            bitcoind_path,
            bitcoind_network,
            version,
        )

    @property
    def json(self):
        node_json = super().json
        node_json["bitcoind_path"] = self.bitcoind_path
        node_json["bitcoind_network"] = self.bitcoind_network
        node_json["version"] = self.version
        return node_json

    def start(self, timeout=15):
        try:
            self.bitcoind.start_bitcoind(
                datadir=os.path.expanduser(self.datadir),
                timeout=timeout,  # At the initial startup, we don't wait on bitcoind
            )
        except ExtProcTimeoutException as e:
            logger.error(e)
            e.check_logfile(os.path.join(self.datadir, "debug.log"))
            logger.error(e.get_logger_friendly())
        except SpecterError as e:
            logger.error(e)
            # Likely files of bitcoind were not found. Maybe deleted by the user?
        finally:
            try:
                self.bitcoin_pid = self.bitcoind.node_proc.pid
            except Exception as e:
                logger.error(e)
        return self.update_rpc()

    def stop(self):
        if self._bitcoind:
            self._bitcoind.stop_bitcoind()
        self.bitcoin_pid = False

    @property
    def bitcoind(self):
        if os.path.isfile(self.bitcoind_path):
            if not self._bitcoind:
                self._bitcoind = BitcoindPlainController(
                    bitcoind_path=self.bitcoind_path,
                    rpcport=self.port,
                    network=self.bitcoind_network,
                    rpcuser=self.user,
                    rpcpassword=self.password,
                )
            return self._bitcoind
        raise SpecterError(
            "Bitcoin Core files missing. Make sure Bitcoin Core is installed within Specter"
        )

    def is_bitcoind_running(self):
        return self._bitcoind and self._bitcoind.check_existing()
