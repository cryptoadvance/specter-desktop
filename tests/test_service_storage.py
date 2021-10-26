import json, logging, pytest
from cryptoadvance.specter.services import ALL_SERVICES
from cryptoadvance.specter.services.base_service_storage import BaseServiceStorage
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import User, hash_password


# Have to add our pretend service to the list
EXAMPLE_SERVICE = "example"
ALL_SERVICES.append(EXAMPLE_SERVICE)


class ExampleServiceStorage(BaseServiceStorage):
    """
    Pretend service just for testing
    """

    service_type = EXAMPLE_SERVICE

    def __init__(self, data_folder, user):
        super().__init__(data_folder, user)
        self.data["testfield1"] = "This data is not encrypted"
        self.data["testfield2"] = "This data WILL BE encrypted"
        self.encrypted_fields.append("testfield2")


def test_service_storage_decrypt_api_keys(empty_data_folder):
    specter = Specter(data_folder=empty_data_folder)

    password = "somepassword"
    user = User.from_json(
        user_dict={
            "id": "someuser",
            "username": "someuser",
            "password": hash_password("somepassword"),
            "config": {},
            "is_admin": False,
            "services": None,
        },
        specter=specter,
    )

    # User must provide their password in order to decrypt their user_secret which is
    #   then used to decrypt/encrypt their service storage
    user.decrypt_user_secret(password)

    service_storage = ExampleServiceStorage(data_folder=specter.data_folder, user=user)
    service_storage.set_credentials(api_key="myapikey", api_secret="myapisecret")

    # Read the resulting storage file
    with open(service_storage.data_file, "r") as service_json_file:
        service_data = json.load(service_json_file)
    print(service_data)

    # Plaintext fields are readable...
    assert service_data["testfield1"] == service_storage.data["testfield1"]

    # ...while encrypted fields are not
    assert service_data["api_key"] != service_storage.data["api_key"]
    assert service_data["api_secret"] != service_storage.data["api_secret"]

    # Including any fields that are custom to this particular service
    assert service_data["testfield2"] != service_storage.data["testfield2"]

    # Re-instantiate the service storage so it has to load from the saved file...
    service_storage_2 = ExampleServiceStorage(
        data_folder=specter.data_folder, user=user
    )

    # ...and verify the field decryption
    (api_key, api_secret) = service_storage_2.get_credentials()
    assert api_key == service_storage.data["api_key"]
    assert api_secret == service_storage.data["api_secret"]

    # Including the custom field for this service
    assert service_storage_2.data["testfield2"] == service_storage.data["testfield2"]
