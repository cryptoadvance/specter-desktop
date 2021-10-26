import json, logging, pytest
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import User, hash_password, verify_password
from cryptoadvance.specter.managers.user_manager import UserManager


def test_password_hash():
    password = "somepassword"
    hashed_password = hash_password(password)

    assert verify_password(hashed_password, password)

    assert not verify_password(hashed_password, "wrongpassword")


def test_generate_user_secret_on_set_password(empty_data_folder):
    specter = Specter(data_folder=empty_data_folder)

    password = "somepassword"
    # user = specter.user_manager.add_user(
    # )
    # specter.user_manager.save()

    user = User.from_json(
        user_dict={
            "id": "someuser",
            "username": "someuser",
            "password": hash_password(password),
            "config": {},
            "is_admin": False,
            "services": None,
        },
        specter=specter,
    )

    assert user.encrypted_user_secret is None
    assert user.plaintext_user_secret is None

    new_password = "mynewpassphrase"
    user.set_password(new_password)

    assert user.encrypted_user_secret is not None
    assert user.plaintext_user_secret is not None

    print(user.plaintext_user_secret)

    # Reset the plaintext user_secret and test decryption
    user.plaintext_user_secret = None
    user.decrypt_user_secret(new_password)

    assert user.plaintext_user_secret is not None
