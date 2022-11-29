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
        # Dict is sth. like: {'nigiri_regtest': <Node name=Nigiri regtest fullpath=...>, 'default': <Node name=Bitcoin Core fullpath=...>}
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
        nodes_files = load_jsons(self.data_folder, key="alias")
        for node_alias in nodes_files:
            try:
                self.nodes[node_alias] = PersistentObject.from_json(
                    nodes_files[node_alias],
                    self,
                    default_alias=nodes_files[node_alias]["alias"],
                    default_fullpath=calc_fullpath(self.data_folder, node_alias),
                )
            except SpecterInternalException as e:
                logger.error(f"Skipping node {node_alias} due to {e}")

        if not self.nodes:
            if os.environ.get("ELM_RPC_USER"):
                logger.debug(
                    "Creating an external Elements node with the initial configuration."
                )
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
            logger.debug(
                "Creating an external BTC node with the initial configuration."
            )
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

        # Make sure we always have the default node
        # (needed for the rpc-as-pin-authentication used on Raspiblitz)
        has_default_node = False
        for node in self.nodes.values():
            if node.alias == self.DEFAULT_ALIAS:
                has_default_node = True
        # Recreate the default node if it doesn't exist anymore
        if not has_default_node:
            logger.debug("Recreating the default node.")
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
    def active_node(self) -> Node:
        return self.get_by_alias(self._active_node)

    @property
    def nodes_names(self) -> list:
        """Returns a list of the names (not the aliases) of the nodes"""
        return [node.name for node in self.nodes.values()]

    def nodes_by_chain(self, chain: str) -> list:
        """Returns a list of nodes for a given blockchain"""
        return [node for node in self.nodes.values() if node.chain == chain]

    def switch_node(self, node_alias: str):
        # This will throw an error if the node doesn't exist
        logger.debug(f"Switching from {self._active_node} to {node_alias}.")
        self._active_node = self.get_by_alias(node_alias).alias

    def default_node(self) -> Node:
        return self.get_by_alias(self.DEFAULT_ALIAS)

    def get_by_alias(self, alias: str) -> Node:
        for node in self.nodes.values():
            if node.alias == alias:
                return node
        raise SpecterError("Node alias %s does not exist!" % alias)

    def get_by_name(self, name: str) -> Node:
        for node in self.nodes.values():
            if node.name == name:
                return node
        raise SpecterError("Node name %s does not exist!" % name)

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
        and if you have defined your own node type, use save_node directly to save the node (and create it yourself)
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
        logger.debug(f"Persisting {node_alias} from an add_external_node call.")
        self.nodes[node_alias] = node
        self.save_node(node)
        return node

    def save_node(self, node):
        fullpath = (
            node.fullpath
            if hasattr(node, "fullpath")
            else calc_fullpath(self.data_folder, node.alias)
        )
        write_node(node, fullpath)
        logger.info("Added new node {}".format(node.alias))

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
        self.nodes[node_alias] = node
        return node

    def delete_node(self, node, specter):
        logger.info("Deleting {}".format(node.alias))
        try:
            # Delete from wallet manager
            del self.nodes[node.alias]
            # Delete files
            delete_file(node.fullpath)
            delete_file(node.fullpath + ".bkp")
            # Update the active node
            if self._active_node == node.alias:
                specter.update_active_node(
                    next(iter(self.nodes.values())).alias
                )  # This switches to the first node in the node list, which is usually the default node
            logger.info("Node {} was deleted successfully".format(node.alias))
        except KeyError:
            raise SpecterError(f"{node.name} not found, node could not be deleted.")
