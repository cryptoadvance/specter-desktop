from gc import callbacks
import os
import logging
import secrets
import shutil

from ..rpc import get_default_datadir, RPC_PORTS
from ..specter_error import SpecterError, SpecterInternalException
from ..persistence import PersistentObject, write_node, delete_file
from ..helpers import alias, calc_fullpath, load_jsons
from ..node import Node
from ..internal_node import InternalNode
from ..services import callbacks
from ..util.bitcoind_setup_tasks import setup_bitcoind_thread

logger = logging.getLogger(__name__)


class NodeManager:
    # chain is required to manage wallets when bitcoind is not running
    DEFAULT_ALIAS = "default"

    def __init__(
        self,
        proxy_url="socks5h://localhost:9050",
        only_tor=False,
        active_node="default",
        bitcoind_path="",
        internal_bitcoind_version="",
        data_folder="",
    ):
        self.nodes = {}
        self.data_folder = data_folder
        self._active_node = active_node
        self.proxy_url = proxy_url
        self.only_tor = only_tor
        self.bitcoind_path = bitcoind_path
        self.internal_bitcoind_version = internal_bitcoind_version
        self.load_from_disk(data_folder)
        internal_nodes = [
            node for node in self.nodes.values() if not node.external_node
        ]
        for node in internal_nodes:
            node.start()

    def load_from_disk(self, data_folder=None):
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        nodes_files = load_jsons(self.data_folder, key="name")
        for node_alias in nodes_files:
            try:
                self.nodes[
                    nodes_files[node_alias]["name"]
                ] = PersistentObject.from_json(
                    nodes_files[node_alias],
                    self,
                    default_alias=node_alias,
                    default_fullpath=calc_fullpath(self.data_folder, node_alias),
                )
            except SpecterInternalException as e:
                logger.error(f"Skipping node {node_alias} due to {e}")

        if not self.nodes:
            if os.environ.get("ELM_RPC_USER"):
                self.add_external_node(
                    node_type="ELM",
                    name="Blockstream Liquid",
                    autodetect=True,
                    datadir=get_default_datadir(node_type="ELM"),
                    user="",
                    password="",
                    port=7041,
                    host="localhost",
                    protocol="http",
                    default_alias=self.DEFAULT_ALIAS,
                )
            logger.info("Creating initial node-configuration")
            self.add_external_node(
                node_type="BTC",
                name="Bitcoin Core",
                autodetect=True,
                datadir=get_default_datadir(),
                user="",
                password="",
                port=8332,
                host="localhost",
                protocol="http",
                default_alias=self.DEFAULT_ALIAS,
            )

        # Just to be sure here ....
        has_default_node = False
        for name, node in self.nodes.items():
            if node.alias == self.DEFAULT_ALIAS:
                return
        # Make sure we always have a default node
        # (needed for the rpc-as-pin-authentication, created and used for raspiblitz)
        self.add_external_node(
            node_type="BTC",
            name="Bitcoin Core",
            autodetect=True,
            datadir=get_default_datadir(),
            user="",
            password="",
            port=8332,
            host="localhost",
            protocol="http",
            default_alias=self.DEFAULT_ALIAS,
        )

    @property
    def active_node(self):
        return self.get_by_alias(self._active_node)

    @property
    def nodes_names(self):
        return sorted(self.nodes.keys())

    def switch_node(self, node_alias):
        # this will throw an error if the node doesn't exist
        self._active_node = self.get_by_alias(node_alias).alias

    def default_node(self):
        return self.get_by_alias(self.DEFAULT_ALIAS)

    def get_by_alias(self, alias):
        for node_name in self.nodes:
            if self.nodes[node_name] and self.nodes[node_name].alias == alias:
                return self.nodes[node_name]
        raise SpecterError("Node %s does not exist!" % alias)

    def update_bitcoind_version(self, specter, version):
        stopped_nodes = []
        for node in (node for node in self.nodes.values() if not node.external_node):
            if node.is_bitcoind_running():
                node.stop()
                stopped_nodes.append(node.alias)
        shutil.rmtree(
            os.path.join(specter.data_folder, "bitcoin-binaries"),
            ignore_errors=True,
        )
        setup_bitcoind_thread(specter, version)
        for node in (node for node in self.nodes.values() if not node.external_node):
            node.version = version
            logger.info(f"persisting {node} in update_bitcoind_version")
            write_node(node, node.fullpath)
        for node_alias in stopped_nodes:
            self.get_by_alias(node_alias).start(timeout=60)

    def add_external_node(
        self,
        node_type,
        name,
        autodetect,
        datadir,
        user,
        password,
        port,
        host,
        protocol,
        default_alias=None,
    ):
        """Adding a node. Params:
        :param node_type: only valid for autodetect. Either BTC or ELM
        This should only be used for an external node. Use add_internal_node for internal node
        and if you have defined your own node-type, use save_node directly. to save the node (and create it yourself)
        """
        if not default_alias:
            node_alias = alias(name)
        else:
            node_alias = default_alias
        fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
        i = 2
        while os.path.isfile(fullpath):
            node_alias = alias("%s %d" % (name, i))
            fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
            i += 1

        node = Node(
            name,
            node_alias,
            autodetect,
            datadir,
            user,
            password,
            port,
            host,
            protocol,
            fullpath,
            node_type,
            self,
        )
        logger.info(f"persisting {node} in add_external_node")
        self.nodes[name] = node
        return self.save_node(node)

    def save_node(self, node):
        fullpath = (
            node.fullpath
            if hasattr(node, "fullpath")
            else calc_fullpath(self.data_folder, node.name)
        )
        write_node(node, fullpath)

        logger.info("Added new node {}".format(node.alias))
        return node

    def add_internal_node(
        self,
        name,
        network="main",
        port=None,
        default_alias=None,
        datadir=None,
    ):
        """Adding an internal node. Params:
        This should only be used for internal nodes. Use add__External_node for external nodes
        and if you have defined your own node-type, use save_node directly. to save the node (and create it yourself)
        """
        if not default_alias:
            node_alias = alias(name)
        else:
            node_alias = default_alias
        fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
        i = 2
        while os.path.isfile(fullpath):
            node_alias = alias("%s %d" % (name, i))
            fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
            i += 1
        if not datadir:
            datadir = os.path.join(self.data_folder, f"{node_alias}/.bitcoin-{network}")

        node = InternalNode(
            name,
            node_alias,
            False,
            datadir,
            "bitcoin",
            secrets.token_urlsafe(16),
            port if port else (RPC_PORTS[network] if network in RPC_PORTS else 8332),
            "localhost",
            "http",
            fullpath,
            self,
            self.bitcoind_path,
            network,
            self.internal_bitcoind_version,
        )
        self.nodes[name] = node
        return self.save_node(node)

    def delete_node(self, node, specter):
        logger.info("Deleting {}".format(node.alias))
        # Delete files
        delete_file(node.fullpath)
        delete_file(node.fullpath + ".bkp")
        if self._active_node == node.alias:
            specter.update_active_node(next(iter(self.nodes.values())).alias)
        del self.nodes[node.name]
        logger.info("Node {} was deleted successfully".format(node.alias))
