from gc import callbacks
import os
import logging
import secrets
import shutil

from ..rpc import get_default_datadir, RPC_PORTS
from ..specter_error import SpecterError, SpecterInternalException
from ..persistence import PersistentObject, write_node, delete_file
from ..helpers import alias, calc_fullpath, load_jsons
from ..node import Node, NonExistingNode
from ..internal_node import InternalNode
from ..services import callbacks
from ..managers.service_manager import ExtensionManager
from ..util.bitcoind_setup_tasks import setup_bitcoind_thread

logger = logging.getLogger(__name__)


class NodeManager:
    def __init__(
        self,
        proxy_url="socks5h://localhost:9050",
        only_tor=False,
        active_node=None,
        bitcoind_path="",
        internal_bitcoind_version="",
        data_folder="",
        service_manager=None,
    ):
        self.nodes = {}
        # Dict is sth. like: {'nigiri_regtest': <Node name=Nigiri regtest fullpath=...>, 'default': <Node name=Bitcoin Core fullpath=...>}
        self.data_folder = data_folder
        self._active_node = active_node
        self.proxy_url = proxy_url
        self.only_tor = only_tor
        self.bitcoind_path = bitcoind_path
        self.internal_bitcoind_version = internal_bitcoind_version
        self.service_manager: ExtensionManager = service_manager
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
        logger.debug(nodes_files)
        for node_alias in nodes_files:
            try:
                valid_node = True
                node = PersistentObject.from_json(
                    nodes_files[node_alias],
                    self,
                    default_alias=nodes_files[node_alias]["alias"],
                    default_fullpath=calc_fullpath(self.data_folder, node_alias),
                )
                if (
                    node.__class__.__module__.split(".")[1] == "specterext"
                ):  # e.g. cryptoadvance.specterext.spectrum
                    if self.service_manager:
                        if not self.service_manager.is_class_from_loaded_extension(
                            node.__class__
                        ):
                            logger.warning(
                                f"Cannot Load {node} due to corresponding plugin not loaded"
                            )
                            continue
                    else:
                        logger.warning(
                            f"Cannot validate Node {node} to be a valid node, skipping"
                        )
                        continue
                self.nodes[node_alias] = node
                logger.info(f"Loaded Node {self.nodes[node_alias]}")
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
                    autodetect=False,
                    datadir=get_default_datadir(node_type="ELM"),
                    user="",
                    password="",
                    port=7041,
                    host="localhost",
                    protocol="http",
                )

    @property
    def active_node(self) -> Node:
        """returns the current active node or a NonExistingNode
        if no node is active, currently.
        """
        active_node = self.get_by_alias(self._active_node)
        return active_node if active_node else NonExistingNode()

    @property
    def nodes_names(self) -> list:
        """Returns a list of the names (not the aliases) of the nodes"""
        return [node.name for node in self.nodes.values()]

    def nodes_by_chain(self, chain: str) -> list:
        """Returns a list of nodes for a given blockchain"""
        return [node for node in self.nodes.values() if node.chain == chain]

    def switch_node(self, node_alias: str):
        """This will throw an SpecterError if the node doesn't exist.
        It won't persist anything! Use specter.update_active_node to persist!
        """
        new_node = self.get_by_alias(node_alias)
        if not new_node:
            raise SpecterError(f"Node alias {node_alias} does not exist!")
        logger.debug(f"Switching from {self._active_node} to {node_alias}.")
        self._active_node = node_alias

    def get_by_alias(self, alias: str) -> Node:
        """Returns a Node instance for the given alias.
        None if a node with that alias doesn't exist
        """
        for node in self.nodes.values():
            if node.alias == alias:
                return node
        return None

    def get_by_name(self, name: str) -> Node:
        """Returns a Node instance for the given alias.
        raises an SpecterError if it doesn't exist
        """
        for node in self.nodes.values():
            if node.name == name:
                return node
        raise SpecterError("Node name %s does not exist!" % name)

    def get_name_from_alias(self, alias: str) -> str:
        """Returns the name for a specific node alias
        raises an SpecterError if it doesn't exist
        """
        for node in self.nodes.values():
            if node.alias == alias:
                return node.name
        raise SpecterError("Node alias %s does not exist!" % alias)

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
        node_type: str,
        name: str,
        autodetect: bool,
        datadir,
        user: str,
        password: str,
        port: str,
        host: str,
        protocol: str,
    ):
        """Adding a node and saves it to disk as well. Params:
        * node_type: only valid for autodetect. Either BTC or ELM
        * name: A nice name for this node. The alias will get calculated out of that
        * autodetect (boolean): whether this node should get autodetected
        * datadir: questionable! Why is that here needed?!
        This should only be used for an external node. Use add_internal_node for internal node
        and if you have defined your own node type, use save_node directly to save the node (and create it yourself)
        """
        node_alias = alias(name)
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
        """writes the node to disk. Will also apply a fullpath based on the datadir of the
        NodeManager if the node doesn't have one."""
        if not hasattr(node, "fullpath"):
            node.fullpath = calc_fullpath(self.data_folder, node.alias)
        write_node(node, node.fullpath)
        logger.info(f"Saved new node {node.alias} at {node.fullpath}")

    def add_internal_node(
        self,
        name: str,
        network="main",
        port: str = None,
        datadir=None,
    ):
        """Adding an internal node. Params:
        This should only be used for internal nodes. Use add__External_node for external nodes
        and if you have defined your own node-type, use save_node directly. to save the node (and create it yourself)
        """
        node_alias = alias(name)
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
        self.save_node(node)
        return node

    def delete_node(self, node, specter):
        """Deletes the node. Also from the disk."""
        logger.info("Deleting {}".format(node.alias))
        try:
            # Delete from wallet manager
            del self.nodes[node.alias]
            # Delete files
            delete_file(node.fullpath)
            delete_file(node.fullpath + ".bkp")
            # Update the active node
            if self._active_node == node.alias and len(self.nodes) > 0:
                specter.update_active_node(
                    next(iter(self.nodes.values())).alias
                )  # This switches to the first node in the node list, which is usually the default node
            logger.info("Node {} was deleted successfully".format(node.alias))
        except KeyError:
            raise SpecterError(f"{node.name} not found, node could not be deleted.")
