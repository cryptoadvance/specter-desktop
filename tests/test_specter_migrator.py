import json
import logging
import os
import tarfile

import pytest
import requests
from cryptoadvance.specter.util.specter_migrator import (
    MigDataManager,
    SpecterMigration,
    SpecterMigrator,
)
from mock import Mock, patch
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError

logger = logging.getLogger(__name__)


def test_SpecterMigration():
    # If i started first with 1.6.1 and the migration has been implemented in 1.7.0, please do it
    assert SpecterMigration.should_execute_cls("v1.6.1", "v1.7.0")
    # Don't do it
    assert not SpecterMigration.should_execute_cls("v1.7.0", "v1.7.0")
    assert not SpecterMigration.should_execute_cls("v1.5.0", "v1.5.0")
    assert not SpecterMigration.should_execute_cls("v1.6.1", "v1.5.0")


def test_SpecterMigrator_classnaming():
    for clazz in SpecterMigrator.get_migration_classes():
        # instantiation of a migration-class should not have any side-effects:
        mig_obj: SpecterMigration = clazz(Mock())
        # will also tests the prefix implicitely
        assert (
            SpecterMigrator.calculate_id(mig_obj) >= 0
        ), "a migration-class needs an id (int)"
        # If implemented right, this should not throw an Exception:
        assert type(mig_obj.description) == str


def test_SpecterMigrator_versioning(empty_data_folder, caplog):
    caplog.set_level(logging.DEBUG)
    with patch(
        "cryptoadvance.specter.util.specter_migrator.VersionChecker"
    ) as mock_version_checker_class:
        # Specifiy a mock which will represent the VersionChecker Object
        the_obj = Mock()
        # Specify that the mock should return a funny version
        the_obj._get_current_version.return_value = "v1.5.0"
        # Specify that the constructor of the mock_version_checker_class should return the_obj
        mock_version_checker_class.side_effect = [the_obj]
        mm = SpecterMigrator(empty_data_folder)
        mm.plan_migration()
        assert mm.current_binary_version == "v1.5.0"
        assert "Skipping class SpecterMigration_0000" in caplog.text
        assert (
            "Skipping class SpecterMigration_0001" not in caplog.text
        )  # this one overwrites should_execute


def test_SpecterMigrator_versioning2(empty_data_folder, caplog):
    caplog.set_level(logging.DEBUG)
    with patch(
        "cryptoadvance.specter.util.specter_migrator.VersionChecker"
    ) as mock_version_checker_class:
        # Specifiy a mock which will represent the VersionChecker Object
        the_obj = Mock()
        # Specify that the mock should return a funny version
        the_obj._get_current_version.return_value = "v1.7.1"
        # Specify that the constructor of the mock_version_checker_class should return the_obj
        mock_version_checker_class.side_effect = [the_obj]
        mm = SpecterMigrator(empty_data_folder)
        assert mm.current_binary_version == "v1.7.1"
        assert "Skipping class SpecterMigration_0000" not in caplog.text
        assert "Skipping class SpecterMigration_0001" not in caplog.text


def _check_port_free(port=8332):
    # For external nodes, we assume that there are already running
    try:
        result = requests.get(f"http://localhost:{port}")
        return False
    except (ConnectionRefusedError, ConnectionError, NewConnectionError):
        pass
    return True


def test_SpecterMigrator(empty_data_folder, caplog):

    caplog.set_level(logging.DEBUG)
    assert _check_port_free(), "You probably have a bitcoind running on port 8332"
    assert MigDataManager.initial_data()["events"] == []
    assert MigDataManager.initial_data()["migration_executions"] == []
    assert len(os.listdir(empty_data_folder)) == 0
    # For migration1
    btc_tar = tarfile.open(
        "./tests/helpers_testdata/bitcoin_minimum_mainnet_datadir.tgz", "r:gz"
    )
    btc_tar.extractall(os.path.join(empty_data_folder, ".bitcoin"))
    # Fake the existence of bitcoin-binaries
    os.makedirs(os.path.join(empty_data_folder, "bitcoin-binaries"))
    assert len(os.listdir(empty_data_folder)) == 2

    # Patch the Class where it's used, not where it's defined
    with patch(
        "cryptoadvance.specter.util.specter_migrator.VersionChecker"
    ) as mock_version_checker_class:
        # Specifiy a mock which will represent the VersionChecker Object
        the_obj = Mock()
        # Specify that the mock should return a funny version
        the_obj._get_current_version.return_value = "v1.6.1"
        # Specify that the constructor of the mock_version_checker_class should return the_obj
        mock_version_checker_class.side_effect = [the_obj]
        mm = SpecterMigrator(empty_data_folder)
        assert mm.current_binary_version == "v1.6.1"

        # not executed yet
        assert "Setting execution log status of 1 to completed" not in caplog.text
        # initally, zero executed migrations
        assert len(mm.mig.migration_executions) == 0
        # With instantiation, the event get stored just right away
        assert mm.mig.latest_event["version"] == "v1.6.1"
        mylist = mm.plan_migration()

        # This assertion will break every time you create a new migration-script
        assert len(mylist) == 2

        mm.execute_migrations(mylist)
        assert len(mm.mig.migration_executions) == 2
        assert "Setting execution log status of 1 to completed" in caplog.text
        assert "Setting execution log status of 2 to completed" in caplog.text

        assert mm.mig.migration_executions[0]["migration_id"] == 1
        print("Content of nodes/specter_bitcoin/.bitcoin-main")
        print(
            os.listdir(
                os.path.join(
                    empty_data_folder,
                    "nodes",
                    "specter_bitcoin",
                    ".bitcoin-main",
                )
            )
        )
        assert os.path.isdir(
            os.path.join(
                empty_data_folder,
                "nodes",
                "specter_bitcoin",
                ".bitcoin-main",
                "chainstate",
            )
        )
        print("Content of nodes")
        print(os.listdir(os.path.join(empty_data_folder, "nodes")))
