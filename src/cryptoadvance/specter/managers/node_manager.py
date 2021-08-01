import os
import logging
import secrets
import shutil

from ..rpc import get_default_datadir, RPC_PORTS
from ..specter_error import SpecterError
from ..persistence import write_node, delete_file
from ..helpers import alias, load_jsons
from ..node import Node
from ..internal_node import InternalNode
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
        self.data_folder = data_folder
        self._active_node = active_node
        self.proxy_url = proxy_url
        self.only_tor = only_tor
        self.bitcoind_path = bitcoind_path
        self.internal_bitcoind_version = internal_bitcoind_version
        self.update(data_folder)
        internal_nodes = [
            node for node in self.nodes.values() if not node.external_node
        ]
        for node in internal_nodes:
            node.start()

    def update(self, data_folder=None):
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        nodes = {}
        nodes_files = load_jsons(self.data_folder, key="name")
        for node_alias in nodes_files:
            fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
            node_class = (
                Node if nodes_files[node_alias]["external_node"] else InternalNode
            )
            nodes[nodes_files[node_alias]["name"]] = node_class.from_json(
                nodes_files[node_alias],
                self,
                default_alias=node_alias,
                default_fullpath=fullpath,
            )
        if not nodes:
            self.add_node(
                name="Bitcoin Core",
                autodetect=True,
                datadir=get_default_datadir(),
                user="",
                password="",
                port=8332,
                host="localhost",
                protocol="http",
                external_node=True,
                default_alias=self.DEFAULT_ALIAS,
            )
        else:
            self.nodes = nodes

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

    def add_node(
        self,
        name,
        autodetect,
        datadir,
        user,
        password,
        port,
        host,
        protocol,
        external_node,
        default_alias=None,
    ):
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
            external_node,
            fullpath,
            self,
        )
        logger.info(f"persisting {node} in add_node")
        write_node(node, fullpath)
        self.update()  # reload files
        logger.info("Added new node {}".format(node.alias))
        return node

    def add_internal_node(
        self,
        name,
        network="main",
        port=None,
        default_alias=None,
    ):
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

        node = InternalNode(
            name,
            node_alias,
            False,
            os.path.join(self.data_folder, f"{node_alias}/.bitcoin-{network}"),
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
        logger.info(f"persisting {node} in add_internal_node")
        write_node(node, fullpath)
        self.update()  # reload files
        logger.info("Added new internal node {}".format(node.alias))
        return node

    def delete_node(self, node, specter):
        logger.info("Deleting {}".format(node.alias))
        # Delete files
        delete_file(node.fullpath)
        delete_file(node.fullpath + ".bkp")
        if self._active_node == node.alias:
            specter.update_active_node(next(iter(self.nodes.values())).alias)
        del self.nodes[node.name]
        self.update()
        logger.info("Node {} was deleted successfully".format(node.alias))
