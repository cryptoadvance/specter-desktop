import logging
import json
import os
import tarfile
import time

from cryptoadvance.specter.specter_migrator import SpecterMigrator

logger = logging.getLogger(__name__)


def test_SpecterMigrator(empty_data_folder, caplog):
    caplog.set_level(logging.DEBUG)
    # For migration1
    btc_tar = tarfile.open(
        "./tests/helpers_testdata/bitcoin_minimum_mainnet_datadir.tgz", "r:gz"
    )
    btc_tar.extractall(os.path.join(empty_data_folder, ".bitcoin"))
    # Fake the existence of bitcoin-binaries
    os.makedirs(os.path.join(empty_data_folder, "bitcoin-binaries"))

    mm = SpecterMigrator(empty_data_folder)
    # With instantiation, the event get stored just right away
    assert mm.mig.latest_event["version"] == "custom"
    mylist = mm.plan_migration()
    # This assertion will break every time you create a new migration-script
    assert len(mylist) == 2

    mm.execute_migrations(mylist)
    assert len(mm.mig.migration_executions) == 2

    assert mm.mig.migration_executions[0]["migration_no"] == 0
    # Nothing to test here

    assert mm.mig.migration_executions[1]["migration_no"] == 1
    assert os.path.isdir(
        os.path.join(
            empty_data_folder, "nodes", "specter_bitcoin", ".bitcoin-main", "chainstate"
        )
    )
    specter_bitcoin_json = os.path.join(
        empty_data_folder, "nodes", "specter_bitcoin.json"
    )
    assert os.path.isfile(specter_bitcoin_json)
    with open(specter_bitcoin_json) as jsonfile:
        config = json.loads(jsonfile.read())
    assert config["name"] == "specter_bitcoin"
    assert config["alias"] == "specter_bitcoin"
    assert config["autodetect"] == False
    assert config["datadir"].endswith("nodes/specter_bitcoin/.bitcoin-main")
    assert config["user"] == "bitcoin"
    assert config["password"]
    assert config["port"] == 8332
    assert config["host"] == "localhost"
    assert config["external_node"] == False
    # yeah, some more but should be ok
