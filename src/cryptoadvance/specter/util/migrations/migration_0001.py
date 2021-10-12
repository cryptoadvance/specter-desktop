import logging
import os
import shutil

from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError

from cryptoadvance.specter.specter_error import SpecterError
from ...config import BaseConfig
from ..specter_migrator import SpecterMigration
from ...helpers import load_jsons
from ...managers.node_manager import NodeManager
import requests

logger = logging.getLogger(__name__)


class SpecterMigration_0001(SpecterMigration):
    version = "v1.6.1"  # the version this migration has been rolled out
    # irrelevant though because we'll execute this script in any case
    # as we can't have yet a say on when specter has been started first

    def should_execute(self):
        # This Migration cannot rely on the default-mechanism as the migration_framework was not
        # in place when the functionality has been implemented
        return True

    @property
    def description(self) -> str:
        return """Single-Node migration:
            In v1.3.1 Single Node implementation has been implemented
            Later we had multiple nodes. This migrates the single installation to one of many.
            Effectively it will:
            * Check whether an internal node was existing in ~/.specter/.bitcoin
            * Check whether a new internal default node (bitcoin/main) is NOT existing
            * Move the ~/.specter/.bitcoin to ~/.specter/nodes/specter_bitcoin/.bitcoin-main
            * Creates a json-definition in ~/.specter/nodes/specter_bitcoin.json
        """

    def execute(self):
        source_folder = os.path.join(self.data_folder, ".bitcoin")
        if not os.path.isdir(source_folder):
            logger.info(
                "No .bitcoin directory found in {self.data_folder}. Nothing to do"
            )
            return
        if not os.path.isdir(os.path.join(self.data_folder, "bitcoin-binaries")):
            raise SpecterError(
                "Could not proceed with migration as bitcoin-binaries are not existing."
            )
        if not self._check_port_free():
            logger.error(
                "There is already a Node with the default port configured or running. Won't migrate!"
            )
            return
        # The version will be the version shipped with specter
        bitcoin_version = BaseConfig.INTERNAL_BITCOIND_VERSION
        logger.info(f".bitcoin directory detected in {self.data_folder}. Migrating ...")
        recommended_name = self._find_appropriate_name()
        target_folder = os.path.join(self.data_folder, "nodes", recommended_name)
        logger.info(f"Migrating to folder {target_folder}")
        os.makedirs(target_folder)
        logger.info(f"Moving .bitcoin to folder {target_folder}")
        shutil.move(source_folder, os.path.join(target_folder, ".bitcoin-main"))
        if os.path.isdir(os.path.join(source_folder, "bitcoin.conf")):
            logger.info("Removing bitcoin.conf file")
            os.remove(os.path.join(source_folder, "bitcoin.conf"))
        definition_file = os.path.join(target_folder, "specter_bitcoin.json")
        logger.info(
            f"Creating {definition_file}. This will cause some warnings and even errors about not being able to connect to the node which can be ignored."
        )
        nm = NodeManager(
            data_folder=os.path.join(self.data_folder, "nodes"),
            bitcoind_path=os.path.join(
                self.data_folder, "bitcoin-binaries", "bin", "bitcoind"
            ),
            internal_bitcoind_version=bitcoin_version,
        )
        # Should create a json (see fullpath) like the one below:
        node = nm.add_internal_node(recommended_name)

        # {
        #     "name": "Specter Bitcoin",
        #     "alias": "specter_bitcoin",
        #     "autodetect": false,
        #     "datadir": "/home/someuser/.specter/nodes/specter_bitcoin/.bitcoin-main",
        #     "user": "bitcoin",
        #     "password": "3ah0yc-2dDEwUSqHuuZi-w",
        #     "port": 8332,
        #     "host": "localhost",
        #     "protocol": "http",
        #     "external_node": false,
        #     "fullpath": "/home/someuser/.specter/nodes/specter_bitcoin.json",
        #     "bitcoind_path": "/home/someuser/.specter/bitcoin-binaries/bin/bitcoind",
        #     "bitcoind_network": "main",
        #     "version": "0.21.1"
        # }

    def _find_appropriate_name(self):
        if not os.path.isdir(os.path.join(self.data_folder, "nodes")):
            return "specter_bitcoin"
        if not os.path.isdir(
            os.path.join(self.data_folder, "nodes", "specter_bitcoin")
        ):
            return "specter_bitcoin"
        # Hmm, now it gets a bit trieckier
        if not os.path.isdir(
            os.path.join(self.data_folder, "nodes", "specter_migrated")
        ):
            return "specter_migrated"
        # Now it's getting fishy
        raise SpecterError(
            "I found a node called 'specter_migrated'. This migration script should not run twice."
        )

    def _check_port_free(self, port=8332):
        # For external nodes, we assume that there are already running
        try:
            result = requests.get(f"http://localhost:{port}")
            return False
        except (ConnectionRefusedError, ConnectionError, NewConnectionError):
            pass
        # Now let's check internal Nodes
        if os.path.isfile(os.path.join(self.data_folder, "nodes")):
            configs = load_jsons(os.path.join(self.data_folder, "nodes"))
            ports = [node.port for node in configs.keys()]
            if port in ports:
                return False
        return True
