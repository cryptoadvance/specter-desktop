import json
import logging
import os
from os import path
import shutil
from typing import Type

from embit.liquid.networks import get_network
from flask import render_template
from flask_babel import lazy_gettext as _
from requests.exceptions import ConnectionError

from cryptoadvance.specter.devices.bitcoin_core import BitcoinCore, BitcoinCoreWatchOnly
from cryptoadvance.specter.devices.elements_core import ElementsCore

from .helpers import deep_update, is_liquid, is_testnet, validate_network_for_chain
from .liquid.rpc import LiquidRPC
from .persistence import PersistentObject, write_node
from .rpc import (
    BitcoinRPC,
    RpcError,
    autodetect_rpc_confs,
    get_default_datadir,
)
from .specter_error import SpecterError, BrokenCoreConnectionException
from .device import Device

logger = logging.getLogger(__name__)


class NonExistingNode(PersistentObject):
    """A kind of Null-object as it represents a non-existing Node. It's deriving from PersistentObject but is not meant to be
    persisted. Instead, it's be created on the fly from the NodeManager if it doesn't have a reasonable node available.
    It also works as some kind of minimal implementation so that specter doesn't fail gracefully.
    """

    @property
    def info(self):
        return {}

    @property
    def network_info(self):
        return {}

    @property
    def uptime(self):
        return -1

    @property
    def chain(self):
        return None

    @property
    def bitcoin_core_version_raw(self):
        return 9999999

    def update_rpc(self):
        pass

    @property
    def is_running(self):
        return False

    @property
    def rpc(self):
        return None

    @property
    def network_parameters(self):
        """Needed for the derivation path in xpubs when adding a device."""
        return get_network("main")

    def check_blockheight(self):
        """check_blockheight is a method which is probably deprecated.
        It should return True if there are new blocks available since check_info has been called
        (which updates the cached _info[] dict)
        """
        raise NotImplemented(
            "A Node Implementation need to implement the check_blockheight method"
        )

    def is_device_supported(self, device_class_or_device_instance):
        """Lets the node deactivate specific devices. The parameter could be a device or a device_type
            You have to check yourself if overriding this method.
        e.g.
        if device_instance_or_device_class.__class__ == type:
            device_class = device_instance_or_device_class
        else:
            device_class = device_instance_or_device_class.__class__
        # example:
        # if BitcoinCore == device_class:
        #    return False
        return True
        """
        return True

    def node_info_template(self):
        """This should return the path to a Info template as string"""
        return "node/components/bitcoin_core_info.jinja"

    def node_logo_template(self):
        """This should return the path to a Logo template as string
        The template should contain the logo independent from the
        status of the node. It's used in the node-selector
        """
        return "includes/sidebar/components/node_logo.jinja"

    def node_connection_template(self):
        """This should return the path to a connection template as string"""
        return "includes/sidebar/components/node_connection.jinja"

    def delete_wallet_file(self, wallet) -> bool:
        """Deleting the wallet file located on the node. This only works if the node is on the same machine as Specter.
        Returns True if the wallet file could be deleted, otherwise returns False.

        In the case of an Abtract Node, we consider that method as an edge-case anyway and we just return False here.
        That is the normal usage if you don't have access to the internals of your Bitcoin Core.
        Overwrite as necessary.
        """
        return False


class AbstractNode(NonExistingNode):
    """This is a Node class worth deriving from. It tries to define as many attributes as possible which are needed but probably in a very
    inefficient way, e.g. without any caching. Feel free to improve that in subclasses and you might get inspired by existing sublasses
    """

    # Many properties are convenience properties of informations, you get from the various info-rpc-callse, namely:
    # * getblockchaininfo
    # * getnetworkinfo
    # * getmempoolinfo
    # * uptime
    # * getblockhash
    # * scantxoutset

    # So first, here are the one which return directly the content of one of those calls as dict:
    @property
    def info(self):
        """Should be a combination of various info calls from Bitcoin Core. Could have:
        * all the info from https://developer.bitcoin.org/reference/rpc/getblockchaininfo.html
        * plus 'mempool_info' from https://developer.bitcoin.org/reference/rpc/getmempoolinfo.html
        * plus uptime
        * plus other stuff
        We only implement a bare minimum here. See the Node-Impl for more

        This method is exception-safe and returns an empty dict if the connection is broken
        """
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
            info = res[0]
            info["mempool_info"] = res[2]
            info["uptime"] = res[3]
            return info
        except BrokenCoreConnectionException:
            return {}

    @property
    def network_info(self):
        """https://developer.bitcoin.org/reference/rpc/getnetworkinfo.html
        returns an almost empty dict if Broken Connection
        """
        try:
            return self.rpc.getnetworkinfo()
        except BrokenCoreConnectionException:
            return {"subversion": "", "version": 999999}

    @property
    def uptime(self):
        """https://developer.bitcoin.org/reference/rpc/uptime.html"""
        return self.rpc.uptime()

    # Now some even more convenient properties which provide often used handpicked information from those dicts

    @property
    def chain(self):
        """current network name (main, test, regtest)
        might have more values in elements/liquid
        """
        try:
            return self.info.get("chain")
        except BrokenCoreConnectionException:
            # This is the most important part to signal that the node-connection is broken without throwin an Exception
            return None

    @property
    def bitcoin_core_version_raw(self):
        try:
            return self.rpc.getnetworkinfo()["version"]
        except BrokenCoreConnectionException:
            # This is the most important part to signal that the node-connection is broken without throwin an Exception
            return 99999

    # ... and more derived properties which already calculate stuff based on those information

    @property
    def is_testnet(self):
        return is_testnet(self.chain)

    @property
    def is_running(self):
        if self.network_info["version"] == 999999:
            logger.debug(f"Node is not running")
            return False
        else:
            return True

    @property
    def network_parameters(self):
        """Uses an RPC call since AbstractNode has no cache"""
        if self.is_running:
            chain_value = self.chain
            network_params = get_network(chain_value)
            # Validate network parameters match the chain
            is_valid, error_msg = validate_network_for_chain(chain_value, network_params)
            if not is_valid:
                logger.warning(
                    f"Unsupported chain '{chain_value}' detected. {error_msg} "
                    "Wallet operations may fail with this chain configuration."
                )
                # Return safe fallback to prevent crashes during node info display
                # Use 'main' as it's the most stable/tested network in the codebase
                # Actual wallet operations will fail with clear error from Wallet.network
                return get_network("main")
            return network_params
        # Default to 'main' when node is not running - safe, stable fallback
        return get_network("main")

    def check_blockheight(self):
        """Should return True if there are new blocks available since check_info has been called
        (which updates the cached _info[] dict)
        """
        return self.info.get("blocks") != self.rpc.getblockcount()

    def is_device_supported(self, device_class_or_device_instance):
        """Lets the node deactivate specific devices. The parameter could be a device or a device_type
            You have to check yourself if overriding this method.
        e.g.
        if device_instance_or_device_class.__class__ == type:
            device_class = device_instance_or_device_class
        else:
            device_class = device_instance_or_device_class.__class__
        # example:
        # if BitcoinCore == device_class:
        #    return False
        return True
        """
        return True

    def node_info_template(self):
        """This should return the path to an info template as string"""
        return "node/components/bitcoin_core_info.jinja"

    def node_logo_template(self):
        """This should return the path to a logo template as string
        The template should contain the logo independent from the
        status of the node. It's used in the node selector.
        """
        return "node/components/node_logo.jinja"

    def node_connection_template(self):
        """This should return the path to a connection template as string"""
        return "includes/sidebar/components/node_connection.jinja"

    def delete_wallet_file(self, wallet) -> bool:
        """Deleting the wallet file located on the node. This only works if the node is on the same machine as Specter.
        Returns True if the wallet file could be deleted, otherwise returns False.

        In the case of an Abtract Node, we consider that method as an edge-case anyway and we just return False here.
        That is the normal usage if you don't have access to the internals of your Bitcoin Core.
        Overwrite as necessary.
        """
        return False


class Node(AbstractNode):
    """A Node represents the connection to a Bitcoin and/or Liquid (Full-) node.
    It can be created via constructor or from json. It mainly gives you a
    RPC object to use the JSON RPC API of the node. It also manages the stability of this connection. It will only
    persist healthy connections. One or more Nodes are managed via the NodeManager
    """

    external_node = True

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
        node_type,
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
        :param fullpath: it's assumed that you want to store it on disk AND decide about the fullpath upfront
        :param node_type: either "ELM" or "BTC", will impact autodetection (datadir and Env-vars)
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
        self.fullpath = fullpath
        self._node_type = node_type
        self.manager = manager
        self.proxy_url = manager.proxy_url
        self.only_tor = manager.only_tor
        try:
            self.rpc = self._get_rpc()
        except BrokenCoreConnectionException:
            self.rpc = None
        self._asset_labels = None
        self.check_info()

    @classmethod
    def from_json(cls, node_dict, manager, default_alias="", default_fullpath=""):
        """Create a Node from json"""
        name = node_dict.get("name", "")
        alias = node_dict.get("alias", default_alias)
        autodetect = node_dict.get("autodetect", True)
        node_type = node_dict.get("node_type", "BTC")
        datadir = node_dict.get("datadir", get_default_datadir(node_type=node_type))
        user = node_dict.get("user", "")
        password = node_dict.get("password", "")
        port = node_dict.get("port", None)
        host = node_dict.get("host", "localhost")
        protocol = node_dict.get("protocol", "http")
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
            fullpath,
            node_type,
            manager,
        )

    @property
    def json(self):
        """Get a json-representation of this Node"""
        node_json = super().json
        return deep_update(
            node_json,
            {
                "name": self.name,
                "alias": self.alias,
                "autodetect": self.autodetect,
                "datadir": self.datadir,
                "user": self.user,
                "password": self.password,
                "port": self.port,
                "host": self.host,
                "protocol": self.protocol,
                "node_type": self.node_type,
            },
        )

    def _get_rpc(self):
        """Checks if configurations have changed, compares with old rpc
        and returns new one if necessary.
        Aims to be exception safe, returns None if rpc is not working"""
        if hasattr(self, "_rpc"):
            rpc = self._rpc
        else:
            rpc = None
        if self.autodetect:
            try:
                if self.port:
                    # autodetect_rpc_confs is trying a RPC call
                    rpc_conf_arr = autodetect_rpc_confs(
                        self.node_type,
                        datadir=os.path.expanduser(self.datadir),
                        port=self.port,
                    )
                else:
                    rpc_conf_arr = autodetect_rpc_confs(
                        self.node_type, datadir=os.path.expanduser(self.datadir)
                    )
            except BrokenCoreConnectionException:
                return None
            if len(rpc_conf_arr) > 0:
                rpc = BitcoinRPC(
                    **rpc_conf_arr[0], proxy_url=self.proxy_url, only_tor=self.only_tor
                )
            return rpc
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
            logger.error(f"RPC connection is None in get_rpc. Returning None ...")
            return None
        # check if it's liquid
        try:
            res = rpc.getblockchaininfo()
            if is_liquid(res.get("chain")):
                # convert to LiquidRPC class
                rpc = LiquidRPC.from_bitcoin_rpc(rpc)
        except RpcError as rpce:
            if rpce.status_code == 401:
                return rpc  # The user is failing to configure correctly
            logger.error(rpce)
            return None
        except BrokenCoreConnectionException as bcce:
            logger.error(f"{bcce} while get_rpc for {rpc}")
            return None
        except Exception as e:
            logger.exception(e)
            return None
        if rpc.test_connection():
            return rpc
        else:
            logger.debug(
                f"Connection {rpc} fails test_connection() in get_rpc. Returning None ..."
            )
            return None

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
        """Changes the attributes of that node but only persists it, if the rpc.test_connection succeeds"""
        update_rpc = self.rpc is None or not self.rpc.test_connection()
        if autodetect is not None and self.autodetect != autodetect:
            logger.debug(f"{self} updating autodetect to {autodetect}")
            self.autodetect = autodetect
            update_rpc = True
        if datadir is not None and self.datadir != datadir:
            logger.debug(f"{self} updating datadir to {datadir}")
            self.datadir = datadir
            update_rpc = True
        if user is not None and self.user != user:
            logger.debug(f"{self} updating user to {user}")
            self.user = user
            update_rpc = True
        if password is not None and self.password != password:
            logger.debug(f"{self} updating password to XXXXXXXX")
            self.password = password
            update_rpc = True
        if port is not None and self.port != port:
            logger.debug(f"{self} updating port to {port}")
            self.port = port
            update_rpc = True
        if host is not None and self.host != host:
            logger.debug(f"{self} updating host to {host}")
            self.host = host
            update_rpc = True
        if protocol is not None and self.protocol != protocol:
            logger.debug(f"{self} updating protocol to {protocol}")
            self.protocol = protocol
            update_rpc = True
        if update_rpc:
            try:
                self.rpc = self._get_rpc()
                if self.rpc and self.rpc.test_connection():
                    logger.debug(f"persisting {self} in update_rpc")
                    write_node(self, self.fullpath)
            except BrokenCoreConnectionException:
                self._mark_node_as_broken()
                return False
        self.check_info()
        return False if not self.rpc else self.rpc.test_connection()

    def rename(self, new_name):
        logger.info("Renaming {}".format(self.alias))
        self.name = new_name
        logger.info(f"persisting {self} in rename")
        write_node(self, self.fullpath)

    def check_info(self):
        self._is_configured = self.rpc is not None
        if self.rpc is not None and self.rpc.test_connection():
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
                # Get and validate network parameters
                chain_value = self.chain
                network_params = get_network(chain_value)
                is_valid, error_msg = validate_network_for_chain(chain_value, network_params)
                if not is_valid:
                    logger.warning(
                        f"Unsupported chain '{chain_value}' detected. {error_msg} "
                        "Node info will display but wallet operations will fail."
                    )
                    # Use safe fallback for node display, but wallets will enforce validation
                    self._network_parameters = get_network("main")
                else:
                    self._network_parameters = network_params
                self._is_running = True
            except BrokenCoreConnectionException:
                self._mark_node_as_broken()
        else:
            if self.rpc is None:
                logger.warning(f"connection of {self} is None in check_info")
            elif not self.rpc.test_connection():
                logger.debug(
                    f"connection {self.rpc} failed test_connection in check_info:"
                )
            self._mark_node_as_broken()

    def test_rpc(self):
        """tests the rpc-connection and returns a dict which helps
        to derive what might be wrong with the config
        ToDo: list an example here.
        """
        rpc = self._get_rpc()
        if rpc is None:
            return {
                "out": "",
                "err": _("Connection to node failed"),
                "code": -1,
                "tests": {"connectable": False},
            }
        r = {}
        r["tests"] = {"connectable": False}
        r["err"] = ""
        r["code"] = 0
        try:
            r["tests"]["recent_version"] = (
                int(rpc.getnetworkinfo()["version"]) >= 200000
            )
            if not r["tests"]["recent_version"]:
                r["err"] = _("Core Node might be too old")

            r["tests"]["connectable"] = True
            r["tests"]["credentials"] = True
            try:
                rpc.listwallets()
                r["tests"]["wallets"] = True
            except RpcError as rpce:
                logger.info(f"Couldn't list wallets while test_rpc {rpce}")
                r["tests"]["wallets"] = False
                r["err"] = "Wallets disabled"

            r["out"] = json.dumps(rpc.getblockchaininfo(), indent=4)
        except BrokenCoreConnectionException as bcce:
            logger.info(f"Caught {bcce} while test_rpc")
            r["tests"]["connectable"] = False
            r["err"] = _("Failed to connect!")
            r["code"] = -1
        except RpcError as rpce:
            logger.info(
                f"Caught an RpcError while test_rpc status_code: {rpce.status_code} error_code: {rpce.error_code}"
            )
            r["tests"]["connectable"] = True
            r["code"] = rpc.r.status_code
            if rpce.status_code == 401:
                r["tests"]["credentials"] = False
                r["err"] = _("RPC authentication failed!")
            else:
                r["err"] = str(rpce.status_code)
        except Exception as e:
            logger.exception(
                "Caught an exception of type {} while test_rpc: {}".format(
                    type(e), str(e)
                )
            )
            r["out"] = ""
            if rpc.r is not None and "error" in rpc.r:
                r["err"] = rpc.r["error"]
                r["code"] = rpc.r.status_code
            else:
                r["err"] = _("Failed to connect")
                r["code"] = -1
        return r

    def _mark_node_as_broken(self):
        self._info = {"chain": None}
        self._network_info = {"subversion": "", "version": 999999}
        self._network_parameters = get_network("main")
        logger.debug(
            f"Node is not running, no RPC connection, check_info didn't succeed, setting RPC attribute to None ..."
        )
        self._info["chain"] = None
        self.rpc = None

    def abortrescanutxo(self):
        """use this to abort a rescan as it stores some state while rescanning"""
        self.rpc.scantxoutset("abort", [])
        # Bitcoin Core doesn't catch up right away
        # so app.specter.check() doesn't work
        self._info["utxorescan"] = None
        self.utxorescanwallet = None

    def is_liquid(self):
        return is_liquid(self.chain)

    def delete_wallet_file(self, wallet) -> bool:
        """Deleting the wallet file located on the node. This only works if the node is on the same machine as Specter.
        Returns True if the wallet file could be deleted, otherwise returns False."""
        datadir = ""
        if self.datadir == "":
            # In case someone did not toggle the auto-detect but still used the default location.
            # When you set up a new node and deactivate the auto-detect, the datadir is set to an empty string.
            logger.debug(
                f"The node datadir before get_default_datadir is: {self.datadir}"
            )
            datadir = get_default_datadir(self.node_type)
            logger.debug(f"The node datadir after get_default_datadir is: {datadir}")
        else:
            datadir = self.datadir
        wallet_file_removed = False
        path = ""
        # Check whether wallet was really unloaded
        wallet_rpc_path = os.path.join(wallet.manager.rpc_path, wallet.alias)
        # If we can unload the wallet via RPC it had not been unloaded properly before by the wallet manager
        try:
            self.rpc.unloadwallet(wallet_rpc_path)
            raise SpecterError(
                "Trying to delete the wallet file on the node but the wallet had not been unloaded properly."
            )
        except RpcError:
            pass
        if self.chain == "test":
            path = os.path.join(datadir, "testnet3/wallets", wallet_rpc_path)
        elif self.chain == "main":
            path = os.path.join(datadir, wallet_rpc_path)
        else:
            path = os.path.join(datadir, f"{self.chain}/wallets", wallet_rpc_path)
        try:
            shutil.rmtree(path, ignore_errors=False)
            logger.debug(f"Removing wallet file at: {path}")
            wallet_file_removed = True
        except FileNotFoundError:
            logger.debug(f"Could not find any wallet file at: {path}")
        return wallet_file_removed

    def no_tx_hint(self):
        """Returns the path to a template with some basic html and and a hint text to be used in the Transactions tab if there are no transactions"""
        return "node/components/no_tx_hint.jinja"

    @property
    def is_running(self):
        if self._network_info["version"] == 999999:
            logger.debug(f"Node is not running")
            return False
        else:
            return True

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
        except Exception as e:
            logger.exception(e)
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
    def taproot_support(self):
        try:
            return self.bitcoin_core_version_raw >= 220000
        except Exception as e:
            logger.exception(e)
            return False

    @property
    def asset_labels(self):
        if not self.is_liquid:
            return {}
        if self._asset_labels is None:
            asset_labels = self.rpc.dumpassetlabels()
            assets = {}
            LBTC = "LBTC" if self.chain == "liquidv1" else "tLBTC"
            for k in asset_labels:
                assets[asset_labels[k]] = k if k != "bitcoin" else LBTC
            self._asset_labels = assets
        return self._asset_labels

    @property
    def is_liquid(self):
        return is_liquid(self.chain)

    @property
    def rpc(self):
        """Returns None if rpc is broken"""
        if not hasattr(self, "_rpc"):
            self._rpc = self._get_rpc()
        elif self._rpc is None:
            self._rpc = self._get_rpc()
        return self._rpc

    @property
    def node_type(self):
        """either BTC or ELM. This is (only) used to enable autodetection and should get specified with the Constructor"""
        if hasattr(self, "_node_type"):
            return self._node_type
        return "BTC"

    @property
    def default_datadir(self):
        return get_default_datadir(self.node_type)

    @rpc.setter
    def rpc(self, value):
        if hasattr(self, "_rpc") and self._rpc != value:
            logger.debug(f"Updating {self}.rpc {self._rpc} with {value} (setter)")
        if hasattr(self, "_rpc") and value == None:
            logger.debug(f"Updating {self}.rpc {self._rpc} with None (setter)")
        self._rpc = value

    # UI specific stuff

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} fullpath={self.fullpath}>"
