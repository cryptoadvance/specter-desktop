import json
import logging
import os

from embit.liquid.networks import get_network
from .helpers import is_testnet, is_liquid
from .liquid.rpc import LiquidRPC
from .persistence import write_node
from .rpc import (
    BitcoinRPC,
    RpcError,
    autodetect_rpc_confs,
    detect_rpc_confs,
    get_default_datadir,
)

logger = logging.getLogger(__name__)


class Node:
    """A NodeManager represents the connection to a Bitcoin and/o Liquid Node (Full-) node.
    It can be created via Constructor or from_json, and mainly it can give you A
    RPC-object to use the API.
    One or many Nodes are managed via the NodeManager
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
        external_node,
        fullpath,
        manager,
    ):
        """Constructor for your Node.

        :param name: arbitrary name
        :param alias: Bad habit, doesn't seem to have business functionality
        :param autodetect: Boolean, will use the datadir to derive config is yes
        :param datadir: A directory where a bitcoin.conf can be found, relevant for autodetect
        :param user: rpc-user
        :param password: rpc-password
        :param port: usually something like 8332 for mainnet, 18332 for testnet, 18443 for Regtest, 38332 for signet
        :param host: domainname or ip-address. Don't add the protocol here
        :param protocol: Usually https or http
        :param external_node: should be True for Node and False for InternalNode
        :param fullpath: it's assumed that you want to store it on disk AND decide about the fullpath upfront
        :param manager: A NodeManager instance which will get notified if the Node's name changes, the proxy_url will get copied from the manager as well
        """
        self.name = name
        self.alias = alias
        self.autodetect = autodetect
        self.datadir = datadir
        self.user = user
        self.password = password
        self.port = port
        self.host = host
        self.protocol = protocol
        self.external_node = external_node
        self.fullpath = fullpath
        self.manager = manager
        self.proxy_url = manager.proxy_url
        self.only_tor = manager.only_tor
        self.rpc = self.get_rpc()

        self.check_info()

    @classmethod
    def from_json(cls, node_dict, manager, default_alias="", default_fullpath=""):
        """Create a Node from json"""
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
            external_node,
            fullpath,
            manager,
        )

    @property
    def json(self):
        """Get a json-representation of this Node"""
        return {
            "name": self.name,
            "alias": self.alias,
            "autodetect": self.autodetect,
            "datadir": self.datadir,
            "user": self.user,
            "password": self.password,
            "port": self.port,
            "host": self.host,
            "protocol": self.protocol,
            "external_node": self.external_node,
            "fullpath": self.fullpath,
        }

    def get_rpc(self):
        """
        Checks if config have changed, compares with old rpc
        and returns new one if necessary
        """
        if hasattr(self, "rpc"):
            rpc = self.rpc
        else:
            rpc = None
        if self.autodetect:
            if self.port:
                rpc_conf_arr = autodetect_rpc_confs(
                    datadir=os.path.expanduser(self.datadir), port=self.port
                )
            else:
                rpc_conf_arr = autodetect_rpc_confs(
                    datadir=os.path.expanduser(self.datadir)
                )
            if len(rpc_conf_arr) > 0:
                rpc = BitcoinRPC(
                    **rpc_conf_arr[0], proxy_url=self.proxy_url, only_tor=self.only_tor
                )
        else:
            # if autodetect is disabled and port is not defined
            # we use default port 8332
            if not self.port:
                self.port = 8332
            rpc = BitcoinRPC(
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port,
                protocol=self.protocol,
                proxy_url=self.proxy_url,
                only_tor=self.only_tor,
            )

        if rpc == None:
            return None
        # check if it's liquid
        try:
            res = rpc.getblockchaininfo()
            if is_liquid(res.get("chain")):
                # convert to LiquidRPC class
                rpc = LiquidRPC.from_bitcoin_rpc(rpc)
        except Exception as e:
            return rpc
        return rpc

    def update_rpc(
        self,
        autodetect=None,
        datadir=None,
        user=None,
        password=None,
        port=None,
        host=None,
        protocol=None,
    ):
        update_rpc = self.rpc is None or not self.rpc.test_connection()
        if autodetect is not None and self.autodetect != autodetect:
            self.autodetect = autodetect
            update_rpc = True
        if datadir is not None and self.datadir != datadir:
            self.datadir = datadir
            update_rpc = True
        if user is not None and self.user != user:
            self.user = user
            update_rpc = True
        if password is not None and self.password != password:
            self.password = password
            update_rpc = True
        if port is not None and self.port != port:
            self.port = port
            update_rpc = True
        if host is not None and self.host != host:
            self.host = host
            update_rpc = True
        if protocol is not None and self.protocol != protocol:
            self.protocol = protocol
            update_rpc = True
        if update_rpc:
            self.rpc = self.get_rpc()
            write_node(self, self.fullpath)
        self.check_info()
        return False if not self.rpc else self.rpc.test_connection()

    def rename(self, new_name):
        logger.info("Renaming {}".format(self.alias))
        self.name = new_name
        write_node(self, self.fullpath)
        self.manager.update()

    def check_info(self):
        self._is_configured = self.rpc is not None
        self._is_running = False
        if self._is_configured:
            try:
                res = [
                    r["result"]
                    for r in self.rpc.multi(
                        [
                            ("getblockchaininfo", None),
                            ("getnetworkinfo", None),
                            ("getmempoolinfo", None),
                            ("uptime", None),
                            ("getblockhash", 0),
                            ("scantxoutset", "status", []),
                        ]
                    )
                ]
                self._info = res[0]
                self._network_info = res[1]
                self._info["mempool_info"] = res[2]
                self._info["uptime"] = res[3]
                try:
                    self.rpc.getblockfilter(res[4])
                    self._info["blockfilterindex"] = True
                except:
                    self._info["blockfilterindex"] = False
                self._info["utxorescan"] = (
                    res[5]["progress"]
                    if res[5] is not None and "progress" in res[5]
                    else None
                )
                if self._info["utxorescan"] is None:
                    self.utxorescanwallet = None
                self._network_parameters = get_network(self.chain)
                self._is_running = True
            except Exception as e:
                self._info = {"chain": None}
                self._network_info = {"subversion": "", "version": 999999}
                self._network_parameters = get_network("main")
                logger.error("Exception %s while check_info()" % e)
        else:
            self._info = {"chain": None}
            self._network_info = {"subversion": "", "version": 999999}

        if not self._is_running:
            self._info["chain"] = None

    def test_rpc(self):
        """tests the rpc-connection and returns a dict which helps
        to derive what might be wrong with the config
        ToDo: list an example here.
        """
        rpc = self.get_rpc()
        if rpc is None:
            return {"out": "", "err": "Connection to node failed", "code": -1}
        r = {}
        r["tests"] = {"connectable": False}
        r["err"] = ""
        r["code"] = 0
        try:
            r["tests"]["recent_version"] = (
                int(rpc.getnetworkinfo()["version"]) >= 170000
            )
            if not r["tests"]["recent_version"]:
                r["err"] = "Core Node might be too old"

            r["tests"]["connectable"] = True
            r["tests"]["credentials"] = True
            try:
                rpc.listwallets()
                r["tests"]["wallets"] = True
            except RpcError as rpce:
                logger.error(rpce)
                r["tests"]["wallets"] = False
                r["err"] = "Wallets disabled"

            r["out"] = json.dumps(rpc.getblockchaininfo(), indent=4)
        except ConnectionError as e:
            logger.error("Caught an ConnectionError while test_rpc: %s", e)

            r["tests"]["connectable"] = False
            r["err"] = "Failed to connect!"
            r["code"] = -1
        except RpcError as rpce:
            logger.error("Caught an RpcError while test_rpc: %s", rpce)
            logger.error(rpce.status_code)
            r["tests"]["connectable"] = True
            r["code"] = rpc.r.status_code
            if rpce.status_code == 401:
                r["tests"]["credentials"] = False
                r["err"] = "RPC authentication failed!"
            else:
                r["err"] = str(rpce.status_code)
        except Exception as e:
            logger.error(
                "Caught an exception of type {} while test_rpc: {}".format(
                    type(e), str(e)
                )
            )
            r["out"] = ""
            if rpc.r is not None and "error" in rpc.r:
                r["err"] = rpc.r["error"]
                r["code"] = rpc.r.status_code
            else:
                r["err"] = "Failed to connect"
                r["code"] = -1
        return r

    def abortrescanutxo(self):
        """use this to abort a rescan as it stores some state while rescanning"""
        self.rpc.scantxoutset("abort", [])
        # Bitcoin Core doesn't catch up right away
        # so app.specter.check() doesn't work
        self._info["utxorescan"] = None
        self.utxorescanwallet = None

    def check_blockheight(self):
        return self.info["blocks"] != self.rpc.getblockcount()

    @property
    def is_running(self):
        return self._is_running

    @property
    def is_configured(self):
        return self._is_configured

    @property
    def info(self):
        return self._info

    @property
    def network_info(self):
        return self._network_info

    @property
    def network_parameters(self):
        try:
            return self._network_parameters
        except Exception:
            return get_network("main")

    @property
    def bitcoin_core_version(self):
        # return self.network_info["subversion"].replace("/", "").replace("Satoshi:", "")
        # This hopefully works for elements as well:
        return self.network_info["subversion"].strip("/").split(":")[-1]

    @property
    def bitcoin_core_version_raw(self):
        return self.network_info["version"]

    @property
    def chain(self):
        return self.info["chain"]

    @property
    def is_testnet(self):
        return is_testnet(self.chain)
