import logging
import os
import shutil

from cryptoadvance.specter.specter_error import SpecterError
from ..specter_migrator import SpecterMigration
from ..managers.node_manager import NodeManager

logger = logging.getLogger(__name__)


class SpecterMigration_0001(SpecterMigration):
    version = "v1.6.1"  # the version this migration has been rolled out

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
        # potentially we could dynamically figure out which version it is but 1.3.1 used:
        bitcoin_version = "0.21.0"
        logger.info(".bitcoin directory detected in {self.data_folder}. Migrating ...")
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
        logger.info(f"Creating {definition_file}")
        nm = NodeManager(
            data_folder=os.path.join(self.data_folder, "nodes"),
            bitcoind_path=os.path.join(
                self.data_folder, "bitcoin-binaries", "bin", "bitcoind"
            ),
            internal_bitcoind_version=bitcoin_version,
        )
        node = nm.add_internal_node(recommended_name)

        #         {
        #     "name": "Specter Bitcoin",
        #     "alias": "specter_bitcoin",
        #     "autodetect": false,
        #     "datadir": "/home/kim/.specter/nodes/specter_bitcoin/.bitcoin-main",
        #     "user": "bitcoin",
        #     "password": "3ah0yc-2dDEwUSqHuuZi-w",
        #     "port": 8332,
        #     "host": "localhost",
        #     "protocol": "http",
        #     "external_node": false,
        #     "fullpath": "/home/kim/.specter/nodes/specter_bitcoin.json",
        #     "bitcoind_path": "/home/kim/.specter/bitcoin-binaries/bin/bitcoind",
        #     "bitcoind_network": "main",
        #     "version": "0.21.1"
        # }

        logger.debug(
            f"migration_0000 is an example method showing how to implement a migration"
        )

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
