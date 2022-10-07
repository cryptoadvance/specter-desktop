import json
import pytest

from flask_login import current_user
from flask_login.utils import login_user, logout_user
from mock import patch, Mock
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest import TestCase

from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.server import SpecterFlask
from cryptoadvance.specter.services.service import Service
from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorage,
    ServiceEncryptedStorageError,
    ServiceEncryptedStorageManager,
)
from cryptoadvance.specter.managers.service_manager import ServiceManager
from cryptoadvance.specter.user import User, hash_password


class FakeService(Service):
    # A dummy Service just used by the test suite
    id = "test_service"
    name = "Test Service"
    has_blueprint = False


# @patch("cryptoadvance.specter.services.service_manager.app")
# def test_ServiceManager_loads_services(empty_data_folder, app):
#     # app.config = MagicMock()
#     # app.config.get.return_value = "prod"
#     specter_mock = MagicMock()
#     specter_mock.data_folder.return_value = empty_data_folder

#     service_manager = ServiceManager(specter=specter_mock, devstatus_threshold="alpha")
#     services = service_manager.services
#     assert "swan" in services


def test_ServiceEncryptedStorage(empty_data_folder):
    specter_mock = Mock()
    specter_mock.config = {"uid": ""}
    specter_mock.user_manager = Mock()
    specter_mock.user_manager.users = [""]

    user1 = User.from_json(
        user_dict={
            "id": "user1",
            "username": "user1",
            "password": hash_password("somepassword"),
            "config": {},
            "is_admin": False,
            "services": None,
        },
        specter=specter_mock,
    )
    user2 = User.from_json(
        user_dict={
            "id": "user2",
            "username": "user2",
            "password": hash_password("somepassword"),
            "config": {},
            "is_admin": False,
            "services": None,
        },
        specter=specter_mock,
    )
    user1._generate_user_secret("muh")

    # Can set and get service storage fields
    service_storage = ServiceEncryptedStorage(empty_data_folder, user1)
    service_storage.set_service_data("a_service_id", {"somekey": "green"})
    assert service_storage.get_service_data("a_service_id") == {"somekey": "green"}
    assert service_storage.get_service_data("another_service_id") == {}

    # We expect a call for a user that isn't logged in to fail
    with pytest.raises(ServiceEncryptedStorageError) as execinfo:
        ServiceEncryptedStorage(empty_data_folder, user2)
    assert "must be authenticated with password" in str(execinfo.value)


def test_access_encrypted_storage_after_login(app_no_node: SpecterFlask):
    """ServiceEncryptedStorage should be accessible (decryptable) after user login"""
    # Create test users; automatically generates their `user_secret` and kept decrypted
    # in memory.
    user_manager: UserManager = app_no_node.specter.user_manager
    user_manager.create_user(
        user_id="bob",
        username="bob",
        plaintext_password="plain_pass_bob",
        config={},
    )
    user_manager.create_user(
        user_id="alice",
        username="alice",
        plaintext_password="plain_pass_alice",
        config={},
    )

    storage_manager = ServiceEncryptedStorageManager(
        user_manager.data_folder, user_manager
    )
    storage_manager.storage_by_user = {}

    # Need a simulated request context to enable `current_user` lookup
    with app_no_node.test_request_context():
        login_user(user_manager.get_user("bob"))

        # Test user's service_data should be decryptable but initially empty
        service_data = storage_manager.get_current_user_service_data(
            service_id=FakeService.id
        )
        assert service_data == {}
        storage_manager.update_current_user_service_data(
            service_id=FakeService.id, service_data={"somekey": "green"}
        )

        logout_user()

        # Meanwhile Alice's account storage will still be blank...
        login_user(user_manager.get_user("alice"))
        service_data = storage_manager.get_current_user_service_data(
            service_id=FakeService.id
        )
        assert (
            storage_manager.get_current_user_service_data(service_id=FakeService.id)
            == {}
        )

        logout_user()

        # ...while Bob's can be retrieved when he's logged in.
        login_user(user_manager.get_user("bob"))
        service_data = storage_manager.get_current_user_service_data(
            service_id=FakeService.id
        )
        assert storage_manager.get_current_user_service_data(
            service_id=FakeService.id
        ) == {"somekey": "green"}


def test_remove_all_services_from_user(app_no_node: SpecterFlask, empty_data_folder):
    """ServiceEncryptedStorage should be accessible (decryptable) after user login"""
    # Create test users; automatically generates their `user_secret` and kept decrypted
    # in memory.
    user_manager: UserManager = app_no_node.specter.user_manager
    user_manager.create_user(
        user_id="bob",
        username="bob",
        plaintext_password="plain_pass_bob",
        config={},
    )

    storage_manager = ServiceEncryptedStorageManager(
        user_manager.data_folder, user_manager
    )
    storage_manager.storage_by_user = {}

    # Need a simulated request context to enable `current_user` lookup
    with app_no_node.test_request_context():
        user = user_manager.get_user("bob")
        login_user(user)

        # Test user's service_data should be decryptable but initially empty
        service_data = storage_manager.get_current_user_service_data(
            service_id=FakeService.id
        )
        assert service_data == {}
        storage_manager.update_current_user_service_data(
            service_id=FakeService.id, service_data={"somekey": "green"}
        )

        # Check on disk. The <user>_services.json should now have our data.
        service_encrypted_storage_file = (
            storage_manager._get_current_user_service_storage().data_file
        )
        with open(service_encrypted_storage_file, "r") as storage_json_file:
            data_on_disk = json.load(storage_json_file)

        # Can't test the actual values because they're encrypted, but the Service.id key is plaintext
        assert FakeService.id in data_on_disk

        # Now remove all
        app_no_node.specter.service_manager.remove_all_services_from_user(user)

        # Verify data on disk; Bob's user should have his user_secret cleared.
        users_file = app_no_node.specter.user_manager.users_file
        with open(users_file, "r") as storage_json_file:
            data_on_disk = json.load(storage_json_file)
        found_bob = False
        for user_entry in data_on_disk:
            if user_entry["id"] == "bob":
                found_bob = True
                assert user_entry.get("encrypted_user_secret") is None
        assert found_bob

        # With no `user_secret` the decryption attempt must fail.
        with pytest.raises(ServiceEncryptedStorageError) as execinfo:
            storage_manager._get_current_user_service_storage()
        assert "must be authenticated with password" in str(execinfo.value)

        # Should now be cleared in memory (have to request raw data since we can't
        # decrypt)...
        service_encrypted_storage = storage_manager.get_raw_encrypted_data(user)
        assert service_encrypted_storage == {}

        # ...and on disk
        with open(service_encrypted_storage_file, "r") as storage_json_file:
            data_on_disk = json.load(storage_json_file)
        assert data_on_disk == {}
