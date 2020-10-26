import os
import shutil
import hashlib
import binascii
import json
from flask_login import UserMixin
from .specter_error import SpecterError
from .persistence import read_json_file, write_json_file, delete_folder


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


class User(UserMixin):
    def __init__(self, id, username, password, config, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.config = config
        self.is_admin = is_admin
        self.wallet_manager = None
        self.device_manager = None
        self.manager = None

    @property
    def folder_id(self):
        if self.is_admin:
            return ""
        return f"_{self.id}"

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
        if self.manager is None:
            self.manager = specter.user_manager
        users = self.manager.users
        existing = self in users

        # update specter users
        if not existing and not delete:
            specter.add_user(self)
        if existing and delete:
            specter.delete_user(self)
        self.manager.save()

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
        # we delete wallet manager and device manager in save_info
        self.save_info(specter, delete=True)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.id == other
        return self.id == other.id

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        # to make lookups in dicts by user id
        return hash(self.id)

    def __str__(self):
        return self.id

    def __repr__(self):
        return f"User({self.id})"
