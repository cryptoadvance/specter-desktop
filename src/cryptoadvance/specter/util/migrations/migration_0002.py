import logging
import os
import shutil

from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError

from cryptoadvance.specter.specter_error import SpecterError
from ...config import BaseConfig
from ..specter_migrator import SpecterMigration
from ...helpers import load_jsons
from ...persistence import write_json_file
from ...managers.node_manager import NodeManager
import requests

logger = logging.getLogger(__name__)


class SpecterMigration_0002(SpecterMigration):
    version = "v1.12.0"  # the version this migration has been rolled out
    # irrelevant though because we'll execute this script in any case
    # as we can't have yet a say on when specter has been started first

    def should_execute(self):
        # This Migration cannot rely on the default-mechanism as the migration_framework was not
        # in place when the functionality has been implemented
        return True

    @property
    def description(self) -> str:
        return """Node-class migration:
            We introduced the Spectrum Node on an extension. With that, we made the choice of 
            the Node to be instantiated much more flexible. The node.json gets an attribute called
            python_class which is the fully qualified package name of the class the NodeManager
            should instantiate.
            This migrates all the node.json files to the new format.
            Effectively it will:
            * Iterate over all nodes in ~/.specter/nodes/*.json
            * load each node.json and adds the correct python_class 
            * stores it again
            In order to reverse this migration, you do need to reverse the addition of the 
            python_class like this:
            
            sudo apt-get install moreutils jq
            cd ~/.specter/nodes
            # remove python_class key
            for file in `ls *.json`; do jq 'del(.python_class)' $file | sponge $file ; done
            cd ..
            jq 'del(.migration_executions[] | select(.migration_id == 2))' migration_data.json | sponge migration_data.json

        """
        # In an early iteration of the migration, the key "external_node" has been deleted as well.
        # However, this breaks backwards compatibility. So in order to keep that (for some time),
        # we don't delete that key (see below)
        # If we do at some point in time (and we should), this rollback procedure might be helpful:
        # adding the external_node key again:
        # for file in `ls *.json`; do jq '. | select(.python_class=="cryptoadvance.specter.internal_node.InternalNode") + {"external_node":false} , . | select(.python_class=="cryptoadvance.specter.node.Node") + {"external_node":true}'  $file | sponge $file ; done

    def execute(self):
        node_folder = os.path.join(self.data_folder, "nodes")
        if not os.path.isdir(node_folder):
            logger.info("No node_folder found in {self.data_folder}. Nothing to do")
            return

        nodes = {}
        logger.info(f"Loading all json-files from {node_folder}")
        nodes_files = load_jsons(node_folder, key="alias")
        logger.info(
            f"iterating these nodes: {[node_alias for node_alias in nodes_files ]}"
        )
        for node_alias in nodes_files:

            fullpath = os.path.join(self.data_folder, "%s.json" % node_alias)
            if nodes_files[node_alias].get("external_node"):
                logger.info(f"Migrating node {node_alias} to Node class.")
                nodes_files[node_alias][
                    "python_class"
                ] = "cryptoadvance.specter.node.Node"
            else:
                logger.info(f"Migrating node {node_alias} to InternalNode class.")
                nodes_files[node_alias][
                    "python_class"
                ] = "cryptoadvance.specter.internal_node.InternalNode"
            # As described above, the "external_node" attribute is not deleted for backwards compatibility
            # This code might come in handy, for a future migration which is doing that.
            # if nodes_files[node_alias].get("external_node"):
            #    logger.info(f"Deleting external_node key of {node_alias} in node.json")
            #    del nodes_files[node_alias]["external_node"]

            write_json_file(
                nodes_files[node_alias], nodes_files[node_alias]["fullpath"]
            )

        # And you get something like this:

        # {
        #     "name": "Specter Bitcoin",
        #     "python_class": "cryptoadvance.specter.node.Node",
        #     "alias": "specter_bitcoin",
        #     "autodetect": false,
        #     "datadir": "/home/someuser/.specter/nodes/specter_bitcoin/.bitcoin-main",
        #     "user": "bitcoin",
        #     "password": "3ah0yc-2dDEwUSqHuuZi-w",
        #     "port": 8332,
        #     "host": "localhost",
        #     "protocol": "http",
        #     "fullpath": "/home/someuser/.specter/nodes/specter_bitcoin.json",
        #     "bitcoind_path": "/home/someuser/.specter/bitcoin-binaries/bin/bitcoind",
        #     "bitcoind_network": "main",
        #     "version": "0.21.1"
        # }
