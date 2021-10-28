import json, logging, pytest
from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import User, hash_password


class ExampleStorage(GenericDataManager):
    """
    Pretend storage class just for testing
    """

    encrypted_fields = [
        "testfield2",
    ]


def test_storage_field_encrypt_decrypt(empty_data_folder):
    """
    Storage class should be able to use the associated User's decrypted user_secret
    to encrypt and decrypt the specified encrypted_fields to and from on-disk
    json. When loaded into memory, all fields -- whether encrypted or not -- should
    be plaintext readable.
    """
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

    storage = ExampleStorage(
        data_folder=specter.data_folder, encryption_key=user.plaintext_user_secret
    )
    storage.data["testfield1"] = "This data is not encrypted"
    storage.data["testfield2"] = "This data WILL BE encrypted"
    storage._save()

    # Read the resulting storage file
    with open(storage.data_file, "r") as storage_json_file:
        data_on_disk = json.load(storage_json_file)
    print(data_on_disk)

    # Plaintext fields are readable...
    assert data_on_disk["testfield1"] == storage.data["testfield1"]

    # ...while encrypted fields are not
    assert data_on_disk["testfield2"] != storage.data["testfield2"]

    # Re-instantiate the storage so it has to load from the saved file...
    storage_2 = ExampleStorage(
        data_folder=specter.data_folder, encryption_key=user.plaintext_user_secret
    )

    # ...and verify the field decryption
    assert storage_2.data["testfield2"] == storage.data["testfield2"]
    assert data_on_disk["testfield2"] != storage_2.data["testfield2"]
