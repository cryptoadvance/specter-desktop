import os
import shutil
import hashlib
import binascii
import json

from base64 import b64encode, b64decode
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from cryptography.fernet import Fernet
from flask_login import UserMixin

from .specter_error import SpecterError
from .persistence import read_json_file, write_json_file, delete_folder
from .managers.wallet_manager import WalletManager
from .managers.device_manager import DeviceManager
from .helpers import deep_update


def hash_password(plaintext_password):
    """Hash a password for storing."""
    salt = binascii.b2a_base64(hashlib.sha256(os.urandom(60)).digest()).strip()
    pwdhash = (
        binascii.b2a_base64(
            hashlib.pbkdf2_hmac(
                "sha256", plaintext_password.encode("utf-8"), salt, 10000
            )
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
    """
    The user_secret is used to encrypt/decrypt other user-specific data
    (e.g. services data). It is encrypted for storage using the user's
    password (the method == "none" auth type cannot enable options that
    require encrypted storage because it has no password). user_secret is
    decrypted on login (see: SpecterFlask.login()) and stored in memory
    in plaintext.
    """

    def __init__(
        self,
        id,
        username,
        hashed_password,
        config,
        specter,
        encrypted_user_secret=None,
        is_admin=False,
        services=None,
    ):
        self.id = id
        self.username = username
        self.hashed_password = hashed_password
        self.config = config
        self.encrypted_user_secret = encrypted_user_secret
        self.plaintext_user_secret = None
        self.is_admin = is_admin
        self.uid = specter.config["uid"]
        self.specter = specter
        self.wallet_manager = None
        self.device_manager = None
        self.manager = None
        self.services = services

    # TODO: User obj instantiation belongs in UserManager
    @classmethod
    def from_json(cls, user_dict, specter):
        try:
            user_args = {
                "id": user_dict["id"],
                "username": user_dict["username"],
                "hashed_password": user_dict["password"],
                "config": {},
                "specter": specter,
                "encrypted_user_secret": user_dict.get("encrypted_user_secret", None),
                "services": user_dict.get("services", None),
            }
            if not user_dict["is_admin"]:
                user_args["config"] = user_dict["config"]
                return cls(**user_args)
            else:
                user_args["is_admin"] = True
                return cls(**user_args)

        except Exception as e:
            raise SpecterError(f"Unable to parse user JSON.:{e}")

    @property
    def folder_id(self):
        if self.is_admin:
            return ""
        return f"_{self.id}"

    def _encrypt_user_secret(self, plaintext_password):
        # See: https://qvault.io/cryptography/aes-256-cipher-python-cryptography-examples/
        # generate a random salt
        salt = get_random_bytes(AES.block_size)

        # use the Scrypt KDF to get a private key from the password
        private_key = hashlib.scrypt(
            plaintext_password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32
        )

        # create cipher config
        cipher_config = AES.new(private_key, AES.MODE_GCM)

        # return a dictionary with the encrypted text
        cipher_text, tag = cipher_config.encrypt_and_digest(self.plaintext_user_secret)
        self.encrypted_user_secret = {
            "cipher_text": b64encode(cipher_text).decode("utf-8"),
            "salt": b64encode(salt).decode("utf-8"),
            "nonce": b64encode(cipher_config.nonce).decode("utf-8"),
            "tag": b64encode(tag).decode("utf-8"),
        }

    def decrypt_user_secret(self, plaintext_password):
        # See: https://qvault.io/cryptography/aes-256-cipher-python-cryptography-examples/
        if not self.encrypted_user_secret:
            self._generate_user_secret(plaintext_password)

        # decode the dictionary entries from base64
        salt = b64decode(self.encrypted_user_secret["salt"])
        cipher_text = b64decode(self.encrypted_user_secret["cipher_text"])
        nonce = b64decode(self.encrypted_user_secret["nonce"])
        tag = b64decode(self.encrypted_user_secret["tag"])

        # generate the private key from the password and salt
        private_key = hashlib.scrypt(
            plaintext_password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32
        )

        # create the cipher config
        cipher = AES.new(private_key, AES.MODE_GCM, nonce=nonce)

        # decrypt the cipher text
        self.plaintext_user_secret = cipher.decrypt_and_verify(cipher_text, tag)

    def _generate_user_secret(self, plaintext_password):
        # Encryption using the user_secret uses a Fernet key. But the Fernet
        #   key itself will be encrypted with the user's password.
        self.plaintext_user_secret = Fernet.generate_key()
        self._encrypt_user_secret(plaintext_password)
        self.save_info()

    def set_password(self, plaintext_password):
        # Hash the incoming plaintext password and update the encrypted
        #   user_secret as needed.
        self.hashed_password = hash_password(plaintext_password)

        # Must keep encrypted_user_secret in sync with password changes
        if self.encrypted_user_secret is None:
            self._generate_user_secret(plaintext_password)
        else:
            if self.plaintext_user_secret is None:
                raise Exception(
                    "encrypted_user_secret wasn't decrypted during user login"
                )
            self._encrypt_user_secret(plaintext_password)

    @property
    def json(self):
        user_dict = {
            "id": self.id,
            "username": self.username,
            "password": self.hashed_password,  # TODO: Migrate attr name to "hashed_password"?
            "is_admin": self.is_admin,
            "encrypted_user_secret": self.encrypted_user_secret,
            "services": self.services,
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

    # TODO: Refactor this into UserManager
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

    # TODO: Refactor calling code to explicitly call User.save() rather than embedding
    #   self.save_info() on every update and setter. It ends up saving to disk multiple
    #   times for a single Settings submit.
    def update_asset_label(self, asset, label, chain):
        if "asset_labels" not in self.config:
            self.config["asset_labels"] = {}
        if not label:
            if self.config["asset_labels"].get(chain, {}).get(asset):
                del self.config["asset_labels"][chain][asset]
        else:
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

    def set_autohide_sensitive_info_timeout(self, timeout_minutes):
        self.config["autohide_sensitive_info_timeout_minutes"] = timeout_minutes
        self.save_info()

    def set_autologout_timeout(self, timeout_hours):
        self.config["autologout_timeout_hours"] = timeout_hours
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
