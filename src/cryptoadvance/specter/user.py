import os
import shutil
import hashlib
import binascii
import json
from flask_login import UserMixin
from .specter_error import SpecterError
from .persistence import read_json_file, write_json_file, delete_folder
from .managers.wallet_manager import WalletManager
from .managers.device_manager import DeviceManager
from .helpers import deep_update


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
    def __init__(self, id, username, password, config, specter, is_admin=False):
        self.id = id
        self.username = username
        self.password = password
        self.config = config
        self.is_admin = is_admin
        self.uid = specter.config["uid"]
        self.specter = specter
        self.wallet_manager = None
        self.device_manager = None
        self.manager = None

    @property
    def folder_id(self):
        if self.is_admin:
            return ""
        return f"_{self.id}"

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        """pass a json or a plain-password here"""
        try:
            if value.get("salt") and value.get("pwdhash"):
                self._password = value
        except:
            salted_hashed_password = hash_password(value)
            self._password = salted_hashed_password

    @classmethod
    def from_json(cls, user_dict, specter):
        # TODO: Unify admin in backwards compatible way
        try:
            if not user_dict["is_admin"]:
                return cls(
                    user_dict["id"],
                    user_dict["username"],
                    user_dict["password"],
                    user_dict["config"],
                    specter,
                )
            else:
                return cls(
                    user_dict["id"],
                    user_dict["username"],
                    user_dict["password"],
                    {},
                    specter,
                    is_admin=True,
                )
        except Exception as e:
            raise SpecterError(f"Unable to parse user JSON.:{e}")

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

    def check(self):
        self.check_device_manager()
        self.check_wallet_manager()

    def check_wallet_manager(self):
        """Updates wallet manager for this user"""
        # if chain, user or data folder changed
        wallet_manager = self.wallet_manager
        wallets_rpcpath = "specter%s" % self.uid
        wallets_folder = os.path.join(
            self.specter.data_folder, f"wallets{self.folder_id}"
        )
        if (
            wallet_manager is None
            or wallet_manager.data_folder != wallets_folder
            or wallet_manager.rpc_path != wallets_rpcpath
            or wallet_manager.chain != self.specter.chain
        ):

            wallet_manager = WalletManager(
                self.specter.bitcoin_core_version_raw,
                wallets_folder,
                self.specter.rpc,
                self.specter.chain,
                self.device_manager,
                path=wallets_rpcpath,
            )
            self.wallet_manager = wallet_manager
        else:
            wallet_manager.update(
                wallets_folder, self.specter.rpc, chain=self.specter.chain
            )

    def check_device_manager(self, user=None):
        """Updates device manager for this user"""
        devices_folder = os.path.join(
            self.specter.data_folder, f"devices{self.folder_id}"
        )
        if self.device_manager is None:
            self.device_manager = DeviceManager(devices_folder)
        else:
            self.device_manager.update(data_folder=devices_folder)

    def save_info(self, delete=False):
        if self.manager is None:
            self.manager = self.specter.user_manager
        users = self.manager.users
        existing = self in users

        # update specter users
        if not existing and not delete:
            self.specter.add_user(self)
        if existing and delete:
            self.specter.delete_user(self)
        self.manager.save()

    def update_asset_label(self, asset, label, chain):
        if "asset_labels" not in self.config:
            self.config["asset_labels"] = {}
        deep_update(self.config["asset_labels"], {chain: {asset: label}})
        self.save_info()

    def set_explorer(self, explorer_id, explorer):
        if "explorers" not in self.config:
            self.config["explorers"] = (
                {"main": "", "test": "", "regtest": "", "signet": ""},
            )
        self.config["explorers"][self.specter.chain] = explorer
        if "explorer_id" not in self.config:
            self.config["explorer_id"] = {
                "main": "CUSTOM",
                "test": "CUSTOM",
                "regtest": "CUSTOM",
                "signet": "CUSTOM",
            }
        self.config["explorer_id"][self.specter.chain] = explorer_id
        self.save_info()

    def set_fee_estimator(self, fee_estimator, custom_url):
        self.config["fee_estimator"] = fee_estimator
        if fee_estimator == "custom":
            self.config["fee_estimator_custom_url"] = custom_url
        self.save_info()

    def set_hwi_bridge_url(self, url):
        self.config["hwi_bridge_url"] = url
        self.save_info()

    def set_unit(self, unit):
        self.config["unit"] = unit
        self.save_info()

    def set_price_check(self, price_check_bool):
        self.config["price_check"] = price_check_bool
        self.save_info()

    def set_hide_sensitive_info(self, hide_sensitive_info_bool):
        self.config["hide_sensitive_info"] = hide_sensitive_info_bool
        self.save_info()

    def set_price_provider(self, price_provider):
        self.config["price_provider"] = price_provider
        self.save_info()

    def set_weight_unit(self, weight_unit):
        self.config["weight_unit"] = weight_unit
        self.save_info()

    def set_alt_rate(self, alt_rate):
        self.config["alt_rate"] = alt_rate
        self.save_info()

    def set_alt_symbol(self, alt_symbol):
        self.config["alt_symbol"] = alt_symbol
        self.save_info()

    def delete(self):
        # we delete wallet manager and device manager in save_info
        self.save_info(delete=True)

    def __eq__(self, other):
        if other == None:
            return False
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
