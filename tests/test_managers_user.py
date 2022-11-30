import json
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.managers.user_manager import UserManager


def test_create_user(empty_data_folder):
    """
    Should add a new User to the `users` list, generate a user_secret, and write
    the new User to json storage.
    """
    specter = Specter(data_folder=empty_data_folder, checker_threads=False)
    user_manager = UserManager(specter=specter)

    password = "somepassword"
    user_id = "someuser"
    username = "someuser"
    config = {}

    user = user_manager.create_user(
        user_id=user_id, username=username, plaintext_password=password, config=config
    )

    # new User was added to `users`
    assert user in user_manager.users

    # Generated a `user_secret`
    assert user.encrypted_user_secret is not None
    assert user.plaintext_user_secret is not None

    # Already written to persistent storage
    with open(user_manager.users_file) as user_json_file:
        user_json = json.load(user_json_file)
        assert user_id in [u.get("id") for u in user_json]
