import json
import logging
import pytest

from flask_login import current_user
from flask_login.utils import login_user, logout_user
from mock import patch, Mock
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock
from unittest import TestCase
from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceUnencryptedStorage,
)

from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.server import SpecterFlask
from cryptoadvance.specter.services.service import Service
from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorage,
    ServiceEncryptedStorageError,
    ServiceEncryptedStorageManager,
)
from cryptoadvance.specter.managers.service_manager import ExtensionManager
from cryptoadvance.specter.user import User, hash_password


class FakeServiceNoEncryption(Service):
    # A dummy Service just used by the test suite
    id = "test_service_no_encryption"
    name = "Test Service no encryption"
    has_blueprint = False
    encrypt_data = False


class FakeService(Service):
    # A dummy Service just used by the test suite
    id = "test_service"
    name = "Test Service"
    has_blueprint = False
    encrypt_data = True


# @patch("cryptoadvance.specter.services.service_manager.app")
# def test_ExtensionManager_loads_services(empty_data_folder, app):
#     # app.config = MagicMock()
#     # app.config.get.return_value = "prod"
#     specter_mock = MagicMock()
#     specter_mock.data_folder.return_value = empty_data_folder

#     service_manager = ExtensionManager(specter=specter_mock, devstatus_threshold="alpha")
#     services = service_manager.services
#     assert "swan" in services


@pytest.fixture
def specter_mock():
    specter_mock = Mock()
    specter_mock.config = {"uid": ""}
    specter_mock.user_manager = Mock()
    specter_mock.user_manager.users = [""]
    return specter_mock


@pytest.fixture
def user1(specter_mock):
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
    return user1


@pytest.fixture
def user2(specter_mock):
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
    return user2


def test_ServiceEncryptedStorage(empty_data_folder, user1, user2):
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


def test_remove_encrypted_services_from_user(
    app_no_node: SpecterFlask, empty_data_folder
):
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

    storage_manager = app_no_node.specter.service_encrypted_storage_manager
    service_manager = app_no_node.specter.service_manager
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

        # Remove all services that need encryption
        # we add the fakeservice to the service_manager.services otherwise delete_services_with_encrypted_storage doesn't know it exists
        # strictly speaking the important call is here user.delete_user_secret(autosave=True) which will execute regardless of adding fakeservice
        fake_service = FakeService(True, app_no_node.specter)
        service_manager.services[fake_service.id] = fake_service
        assert fake_service.id in service_manager.services

        # also add it to the user, and check later it was remove from the user
        user.add_service(fake_service.id)
        assert user.has_service(fake_service.id)

        app_no_node.specter.service_manager.delete_services_with_encrypted_storage(user)
        # the user should not have the fake_service activated any more
        assert not user.has_service(fake_service.id)
        # the service_manager on the other hand keeps all services, no matter what
        assert service_manager.services[fake_service.id]

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

        logout_user()
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


def test_check_differences_between_encrypted_and_non_encrypted_services(
    app_no_node: SpecterFlask, empty_data_folder
):
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

    service_manager = app_no_node.specter.service_manager
    user = user_manager.get_user("bob")

    def setup_services():
        # Remove all services that need encryption
        # we add the fakeservice to the service_manager.services otherwise delete_services_with_encrypted_storage doesn't know it exists
        # strictly speaking the important call is here user.delete_user_secret(autosave=True) which will execute regardless of adding fakeservice
        fake_service = FakeService(True, app_no_node.specter)
        fake_service_no_encryption = FakeServiceNoEncryption(True, app_no_node.specter)
        service_manager.services[fake_service.id] = fake_service
        service_manager.services[
            fake_service_no_encryption.id
        ] = fake_service_no_encryption
        assert fake_service.id in service_manager.services
        assert fake_service_no_encryption.id in service_manager.services

        # also add it to the user, and check later it was remove from the user
        user.add_service(fake_service.id)
        user.add_service(fake_service_no_encryption.id)
        assert user.has_service(fake_service.id)
        assert user.has_service(fake_service_no_encryption.id)

        return fake_service, fake_service_no_encryption

    fake_service, fake_service_no_encryption = setup_services()
    # delete the encrypted ones
    app_no_node.specter.service_manager.delete_services_with_encrypted_storage(user)
    assert not user.has_service(fake_service.id)
    assert user.has_service(fake_service_no_encryption.id)
    # delete the unencrypted ones
    app_no_node.specter.service_manager.delete_services_with_unencrypted_storage(user)
    assert not user.has_service(fake_service_no_encryption.id)

    # now setup again and check a different order of execution
    fake_service, fake_service_no_encryption = setup_services()
    # delete the unencrypted ones
    app_no_node.specter.service_manager.delete_services_with_unencrypted_storage(user)
    assert not user.has_service(fake_service_no_encryption.id)
    assert user.has_service(fake_service.id)
    # delete the encrypted ones
    app_no_node.specter.service_manager.delete_services_with_encrypted_storage(user)
    # the user should not have the fake_service activated any more
    assert not user.has_service(fake_service.id)

    # the service_manager on the other hand keeps all services, no matter what
    assert service_manager.services[fake_service.id]
    assert service_manager.services[fake_service_no_encryption.id]


def test_ServiceUnEncryptedStorage(empty_data_folder, user1, user2):
    user1._generate_user_secret("muh")

    # Can set and get service storage fields
    service_storage = ServiceUnencryptedStorage(
        empty_data_folder, user1, disable_decrypt=True
    )
    service_storage.set_service_data("a_service_id", {"somekey": "green"})
    assert service_storage.get_service_data("a_service_id") == {"somekey": "green"}
    assert service_storage.get_service_data("another_service_id") == {}


def test_both_Storages_in_parallel(empty_data_folder, user1, user2):
    user1._generate_user_secret("muh")

    # Can set and get service storage fields unecrypted
    service_storage_unenc = ServiceUnencryptedStorage(
        empty_data_folder, user1, disable_decrypt=True
    )
    service_storage_unenc.set_service_data("a_service_id", {"somekey": "green"})
    assert service_storage_unenc.get_service_data("a_service_id") == {
        "somekey": "green"
    }
    assert service_storage_unenc.get_service_data("another_service_id") == {}

    # Can set and get service storage fields encrypted
    service_storage_enc = ServiceEncryptedStorage(empty_data_folder, user1)
    service_storage_enc.set_service_data("a_service_id", {"somekey": "red"})
    assert service_storage_enc.get_service_data("a_service_id") == {"somekey": "red"}

    # asserting again the unencrypted values
    assert service_storage_unenc.get_service_data("a_service_id") == {
        "somekey": "green"
    }

    # changing unencrypted
    service_storage_unenc.set_service_data("a_service_id", {"somekey": "light_green"})

    assert service_storage_unenc.get_service_data("a_service_id") == {
        "somekey": "light_green"
    }
    assert service_storage_enc.get_service_data("a_service_id") == {"somekey": "red"}

    # changing encrypted
    service_storage_enc.set_service_data("a_service_id", {"somekey": "light_red"})

    assert service_storage_unenc.get_service_data("a_service_id") == {
        "somekey": "light_green"
    }
    assert service_storage_enc.get_service_data("a_service_id") == {
        "somekey": "light_red"
    }


class MyTestService(Service):
    id = "test_service"

    @classmethod
    def default_address_label(cls):
        # A non i18n version of this method
        # return str(_("Reserved for {}").format(cls.name))
        return str("Reserved for {}").format(cls.name)


def test_Service_reserve_address(empty_data_folder, caplog):
    wallet_mock = MagicMock()

    MyTestService.reserve_address(wallet_mock, "a", "someLabel")
    assert wallet_mock.associate_address_with_service.assert_called_once


def test_reserve_addresses_with_mocks(empty_data_folder, caplog):
    caplog.set_level(logging.DEBUG)
    specter_mock = MagicMock()
    specter_mock.data_folder = empty_data_folder
    s = MyTestService(True, specter_mock)

    wallet_mock = MagicMock()
    # We assume that we haven't yet reserved any addresses:
    wallet_mock.get_associated_addresses.return_value = []
    # We assume that those are the unused addresses returned by the wallet
    wallet_mock.get_address.side_effect = ["a", "b", "c", "d", "e", "f"]
    # We assume that the next unused address is #5
    wallet_mock.address_index = 5

    addr_obj_mock = MagicMock()
    addr_obj_mock.used = False
    addr_obj_mock.is_reserved = False

    wallet_mock.get_address_obj.return_value = addr_obj_mock

    addresses = s.reserve_addresses(wallet_mock, "someLabel", 2, False)
    print(addresses)
    # address_index stays the same. the get_address logic is
    # taking care that no reserved addresses are handed out.
    assert wallet_mock.address_index == 5
    assert addresses == ["a", "b"]


def test_reserve_addresses_with_an_actual_wallet(trezor_wallet_acc6):
    wallet = trezor_wallet_acc6
    specter_mock = MagicMock()
    test_service = MyTestService(True, specter_mock)
    # Reserve first address
    test_service.reserve_address(
        wallet, "bcrt1qqvqdt5nsjhzrxcvhyz3m29f8qwyd4lrcpmtzy9", "reserved_for_john_nash"
    )
    first_address_address_obj = wallet.get_address_obj(
        "bcrt1qqvqdt5nsjhzrxcvhyz3m29f8qwyd4lrcpmtzy9"
    )
    # Check that labeling works
    assert first_address_address_obj["label"] == "reserved_for_john_nash"
    # Simulating that the address has been used (for the definition of "usage" see the check_unused() method in wallet.py)
    wallet._addresses.set_used(["bcrt1qqvqdt5nsjhzrxcvhyz3m29f8qwyd4lrcpmtzy9"])
    wallet.getnewaddress()
    assert wallet.address_index == 1
    assert first_address_address_obj["used"] == True
    # Check that the correct addresses are reserved, should be #2, #4, #6 - since #0 has been used and there is a gap of one address in between
    addresses = test_service.reserve_addresses(wallet, "satoshi_dice", 3)
    assert addresses == [
        "bcrt1qyqta5muj054x43cmk8rv43up84kefz9ej3y27n",
        "bcrt1qcswaeygm5w0y7xysqkn4uy9d6u0x6yxtlyntn6",
        "bcrt1qwjz0ez6g763cfty6pf984247yngfs75h2n6ccz",
    ]
    address_obj_list = wallet.get_associated_addresses("test_service")
    # Reserving 3 addresses results in an empty list since we already have 3 unused addresses (the first one was used) reserved
    addresses = test_service.reserve_addresses(wallet, "satoshi_dice", 3)
    assert addresses == []
    # Check labeling
    assert [address_obj["label"] for address_obj in address_obj_list] == [
        "reserved_for_john_nash",
        "satoshi_dice",
        "satoshi_dice",
        "satoshi_dice",
    ]
