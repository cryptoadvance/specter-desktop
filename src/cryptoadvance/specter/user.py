import os
import shutil
import hashlib
import binascii
import json
from flask_login import UserMixin
from .specter_error import SpecterError
from .helpers import fslock


def hash_password(password):
    """Hash a password for storing."""
    salt = binascii.b2a_base64(hashlib.sha256(os.urandom(60)).digest()).strip()
    pwdhash = (
        binascii.b2a_base64(
            hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 10000)
        )
        .strip()
        .decode()
    )
    return {"salt": salt.decode(), "pwdhash": pwdhash}


def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    pwdhash = hashlib.pbkdf2_hmac(
        "sha256",
        provided_password.encode("utf-8"),
        stored_password["salt"].encode(),
        10000,
    )
    return pwdhash == binascii.a2b_base64(stored_password["pwdhash"])


def get_users_json(specter):
    users = [
        {
            "id": "admin",
            "username": "admin",
            "password": hash_password("admin"),
            "is_admin": True,
        }
    ]

    # if users.json file exists - load from it
    if os.path.isfile(os.path.join(specter.data_folder, "users.json")):
        with fslock:
            with open(os.path.join(specter.data_folder, "users.json"), "r") as f:
                users = json.load(f)
    # otherwise - create one and assign unique id
    else:
        save_users_json(specter, users)
    return users


def save_users_json(specter, users):
    with fslock:
        with open(os.path.join(specter.data_folder, "users.json"), "w") as f:
            json.dump(users, f, indent=4)


class User(UserMixin):
    def __init__(self, id, username, password, config, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.config = config
        self.is_admin = is_admin

    @classmethod
    def from_json(cls, user_dict):
        # TODO: Unify admin in backwards compatible way
        try:
            if not user_dict["is_admin"]:
                return cls(
                    user_dict["id"],
                    user_dict["username"],
                    user_dict["password"],
                    user_dict["config"],
                )
            else:
                return cls(
                    user_dict["id"],
                    user_dict["username"],
                    user_dict["password"],
                    {},
                    is_admin=True,
                )
        except:
            raise SpecterError("Unable to parse user JSON.")

    @classmethod
    def get_user(cls, specter, id):
        users = get_users_json(specter)
        for user_dict in users:
            user = User.from_json(user_dict)
            if user.id == id:
                return user

    @classmethod
    def get_user_by_name(cls, specter, username):
        users = get_users_json(specter)
        for user_dict in users:
            user = User.from_json(user_dict)
            if user.username == username:
                return user

    @classmethod
    def get_all_users(cls, specter):
        users_dicts = get_users_json(specter)
        users = []
        for user_dict in users_dicts:
            user = User.from_json(user_dict)
            users.append(user)
        return users

    @property
    def json(self):
        user_dict = {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "is_admin": self.is_admin,
        }
        if not self.is_admin:
            user_dict["config"] = self.config
        return user_dict

    def save_info(self, specter, delete=False):
        users = get_users_json(specter)
        existing = False
        for i in range(len(users)):
            if users[i]["id"] == self.id:
                if not delete:
                    users[i] = self.json
                    existing = True
                else:
                    del users[i]
                break
        if not existing and not delete:
            users.append(self.json)

        save_users_json(specter, users)

    def set_explorer(self, specter, explorer):
        self.config["explorers"][specter.chain] = explorer
        self.save_info(specter)

    def set_hwi_bridge_url(self, specter, url):
        self.config["hwi_bridge_url"] = url
        self.save_info(specter)

    def set_unit(self, specter, unit):
        self.config["unit"] = unit
        self.save_info(specter)

    def delete(self, specter):
        devices_datadir_path = os.path.join(
            os.path.join(specter.data_folder, "devices_{}".format(self.id))
        )
        wallets_datadir_path = os.path.join(
            os.path.join(specter.data_folder, "wallets_{}".format(self.id))
        )
        if os.path.exists(devices_datadir_path):
            shutil.rmtree(devices_datadir_path)
        if os.path.exists(wallets_datadir_path):
            shutil.rmtree(wallets_datadir_path)
        self.save_info(specter, delete=True)
