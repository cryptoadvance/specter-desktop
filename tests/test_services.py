import pytest

from flask_login import current_user
from flask_login.utils import login_user
from mock import patch, Mock
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.server import SpecterFlask
from cryptoadvance.specter.services.service import Service
from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorage,
    ServiceEncryptedStorageManager
)
from cryptoadvance.specter.services.service_manager import ServiceManager
from cryptoadvance.specter.user import User, hash_password


class TestService(Service):
    # A dummy Service just used by the test suite
    id = "test_service"
    name = "Test Service"
    has_blueprint = False


@patch("cryptoadvance.specter.services.service_manager.app")
def test_ServiceManager(empty_data_folder, app):
    # app.config = MagicMock()
    # app.config.get.return_value = "prod"
    specter_mock = MagicMock()
    specter_mock.data_folder.return_value = empty_data_folder

    service_manager = ServiceManager(specter=specter_mock, devstatus_threshold="alpha")
    services = service_manager.services
    assert "swan" in services


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
    service_storage = ServiceEncryptedStorage(empty_data_folder, user1)
    service_storage.set_service_data("a_service_id", {"somekey": "green"})
    assert service_storage.get_service_data("a_service_id") == {"somekey": "green"}
    assert service_storage.get_service_data("another_service_id") == {}

    service_storage.set_service_data("another_service_id", {"somekey": "red"})
    assert service_storage.get_service_data("another_service_id") == {"somekey": "red"}

    service_storage.set_service_data("a_service_id", {"somekey": "blue"})
    assert service_storage.get_service_data("a_service_id") == {"somekey": "blue"}
    assert service_storage.get_service_data("another_service_id") == {"somekey": "red"}

    # # We expect a call for a user that isn't logged in to fail
    # service_storage = ServiceEncryptedStorage(empty_data_folder, user2)



def test_ServiceEncryptedStorageManager(app: SpecterFlask, empty_data_folder: TemporaryDirectory, user_manager: UserManager):
    with app.app_context():
        storage_manager = ServiceEncryptedStorageManager.get_instance()

        with app.test_request_context():
            login_user(user_manager.get_user("bob"))
            current_user
            service_data = storage_manager.get_current_user_service_data(service_id=TestService.id)
            assert service_data == {}
            storage_manager.update_current_user_service_data(service_id=TestService.id, service_data={"somekey": "green"})
            assert storage_manager.get_current_user_service_data(service_id=TestService.id) == {"somekey": "green"}
