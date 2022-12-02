import json, logging, pytest
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import User, hash_password, verify_password


def test_password_hash():
    """
    verify_password should succeed when presented with hash_password and the same
    password that was hashed. It should fail when given a different password.
    """
    password = "somepassword"
    password_hash = hash_password(password)
    assert verify_password(password_hash, password)
    assert not verify_password(password_hash, "wrongpassword")


def test_generate_user_secret_on_decrypt_user_secret(empty_data_folder):
    """
    Should generate a user_secret if one does not yet exist when decrypt_user_secret
    is called (happens during the login flow).
    """
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)

    password = "somepassword"
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

    # Even though there's no user_secret yet, the flow calls decrypt anyway...
    user.decrypt_user_secret(password)

    # ...and a new user_secret is created and stored encrypted and plaintext
    assert user.encrypted_user_secret is not None
    assert user.plaintext_user_secret is not None


def test_generate_user_secret_on_set_password(empty_data_folder):
    """
    Should generate a user_secret if one does not yet exist when the User's password
    is changed via set_password.
    """
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)

    password = "somepassword"
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

    # Reset the plaintext user_secret and test decryption
    user.plaintext_user_secret = None
    user.decrypt_user_secret(new_password)

    assert user.plaintext_user_secret is not None


def test_reencrypt_user_secret_on_set_password(empty_data_folder):
    """
    Should re-encrypt the user_secret when the user changes their password.
    """
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)

    password = "somepassword"
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

    # Force generation of a new user_secret
    user.decrypt_user_secret(password)
    assert user.encrypted_user_secret is not None
    assert user.plaintext_user_secret is not None

    first_encrypted_user_secret = user.encrypted_user_secret
    first_plaintext_user_secret = user.plaintext_user_secret

    new_password = "mynewpassphrase"
    user.set_password(new_password)

    # The new encrypted_user_secret will be different...
    assert first_encrypted_user_secret != user.encrypted_user_secret

    # ...but the plaintext_user_secret remains unchanged
    assert first_plaintext_user_secret == user.plaintext_user_secret


def test_reencrypt_user_secret_on_iterations_increase(empty_data_folder):
    """
    Should re-encrypt the user_secret when the User.encryption_iterations is increased
    """
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)

    password = "somepassword"
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

    # Override current default iterations setting
    original_encryption_iterations = user.encryption_iterations
    user.encryption_iterations -= 10000

    # Force generation of a new user_secret
    user.decrypt_user_secret(password)
    assert user.encrypted_user_secret is not None
    assert user.plaintext_user_secret is not None
    assert user.encrypted_user_secret["iterations"] < original_encryption_iterations

    first_encrypted_user_secret = user.encrypted_user_secret
    first_plaintext_user_secret = user.plaintext_user_secret

    # Reset iterations to default
    user.encryption_iterations = original_encryption_iterations

    # On decrypt, should automatically re-encrypt the `user_secret`
    user.decrypt_user_secret(password)
    assert user.encrypted_user_secret["iterations"] == original_encryption_iterations

    # The new encrypted_user_secret will be different...
    assert first_encrypted_user_secret != user.encrypted_user_secret

    # ...but the plaintext_user_secret remains unchanged
    assert first_plaintext_user_secret == user.plaintext_user_secret
