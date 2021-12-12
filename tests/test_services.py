from flask_login.utils import login_user
import pytest
from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorage,
    ServiceApiKeyStorageUserAware,
)
from cryptoadvance.specter.services.service_manager import ServiceManager
from cryptoadvance.specter.services.service_settings_manager import (
    ServiceSettingsManager,
)
from mock import patch, Mock

from cryptoadvance.specter.user import User, hash_password


def test_ServiceSettingsManager(specter_regtest_configured):
    # A DeviceManager manages devices, specifically the persistence
    # of them via json-files in an empty data folder
    um = ServiceSettingsManager(specter_regtest_configured.data_folder, "vaultoro")

    with pytest.raises(Exception):
        assert um.get_key("admin", "wurstbrot")
    um.set_key("admin", "wurstbrot", "lecker")
    assert um.get_key("admin", "wurstbrot") == "lecker"
    um.set_key("admin", "other_key", {"yet_a_key": "yet_a_value"})
    assert um.get_key("admin", "other_key") == {"yet_a_key": "yet_a_value"}
    assert um.get_key("admin", "wurstbrot") == "lecker"


@patch("cryptoadvance.specter.services.service_manager.app")
def test_ServiceManager(empty_data_folder, app):
    print(app)
    app.config = Mock()
    app.config.get.return_value = "prod"
    specter_mock = Mock()
    specter_mock.config = Mock()
    specter_mock.config.get.return_value = ["dummyservice"]
    assert specter_mock.config.get("services", []) == ["dummyservice"]
    specter_mock.data_folder.return_value = empty_data_folder

    sm = ServiceManager(specter_mock, "alpha")
    scls = sm.get_service_classes()
    assert len(scls) == 3
    assert scls[0].id == "dummyservice"
    assert scls[1].id == "swan"
    assert scls[2].id == "vaultoro"
    # assert False


def test_ServiceApiKeyStorage(empty_data_folder):
    specter_mock = Mock()
    specter_mock.config = {"uid": ""}
    specter_mock.user_manager = Mock()
    specter_mock.user_manager.users = [""]

    someuser = User.from_json(
        user_dict={
            "id": "someuser",
            "username": "someuser",
            "password": hash_password("somepassword"),
            "config": {},
            "is_admin": False,
            "services": None,
        },
        specter=specter_mock,
    )
    someuser._generate_user_secret("muh")
    saks = ServiceEncryptedStorage(empty_data_folder, someuser)
    saks.set_service_data("a_service_id", {"somekey": "green"})
    assert saks.get_service_data("a_service_id") == {"somekey": "green"}
    assert saks.get_service_data("another_service_id") == None
    saks.set_service_data("another_service_id", {"somekey": "red"})
    assert saks.get_service_data("another_service_id") == {"somekey": "red"}
    saks.set_service_data("a_service_id", {"somekey": "blue"})
    assert saks.get_service_data("a_service_id") == {"somekey": "blue"}
    assert saks.get_service_data("another_service_id") == {"somekey": "red"}


def test_ServiceApiKeyStorageUserAware(app, empty_data_folder, user_manager):
    saksua = ServiceApiKeyStorageUserAware(empty_data_folder, user_manager)
    with app.app_context():
        saksua.set_api_data("a_service_id", {"somekey": "green"})
        assert saksua.get_api_data("a_service_id") == {"somekey": "green"}
        assert saksua.get_api_data("another_service_id") == None
        saksua.set_api_data("another_service_id", {"somekey": "red"})
        assert saksua.get_api_data("another_service_id") == {"somekey": "red"}
        saksua.set_api_data("a_service_id", {"somekey": "blue"})
        assert saksua.get_api_data("a_service_id") == {"somekey": "blue"}
        assert saksua.get_api_data("another_service_id") == {"somekey": "red"}

        with app.test_request_context():
            login_user(user_manager.get_user("bob"))
            assert saksua.get_api_data("a_service_id") == None
            saksua.set_api_data("a_service_id", {"someotherkey": "green"})
            assert saksua.get_api_data("a_service_id") == {"someotherkey": "green"}
