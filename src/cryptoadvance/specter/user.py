import base64
import binascii
import cryptography
import hashlib
import json
import logging
import os
import shutil

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from flask_login import UserMixin

from .specter_error import SpecterError, handle_exception
from .persistence import read_json_file, write_json_file, delete_folder
from .managers.wallet_manager import WalletManager
from .managers.device_manager import DeviceManager
from .helpers import deep_update


logger = logging.getLogger(__name__)


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


class UserSecretException(Exception):
    pass


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
        password_hash,
        config,
        specter,
        encrypted_user_secret=None,
        is_admin=False,
        services=[],
    ):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.config = config
        self.encrypted_user_secret = encrypted_user_secret
        self.plaintext_user_secret = None
        self.is_admin = is_admin
        self.uid = specter.config["uid"]
        self.specter = specter
        self.wallet_manager = None
        self.device_manager = None
        self.manager = None
        self._services = services

        # Iterations will need to be increased over time to keep ahead of CPU advances.
        self.encryption_iterations = 390000

    # TODO: User obj instantiation belongs in UserManager
    @classmethod
    def from_json(cls, user_dict, specter):
        try:
            user_args = {
                "id": user_dict["id"],
                "username": user_dict["username"],
                "password_hash": user_dict[
                    "password"
                ],  # TODO: Migrate attr name to "password_hash"?
                "config": {},
                "specter": specter,
                "encrypted_user_secret": user_dict.get("encrypted_user_secret", None),
                "services": user_dict.get("services", []),
            }
            if not user_dict["is_admin"]:
                user_args["config"] = user_dict["config"]
                return cls(**user_args)
            else:
                user_args["is_admin"] = True
                return cls(**user_args)

        except Exception as e:
            handle_exception(e)
            raise SpecterError(f"Unable to parse user JSON.:{e}")

    @property
    def folder_id(self):
        if self.is_admin:
            return ""
        return f"_{self.id}"

    @property
    def services(self):
        if not self._services:
            self._services = []
        return self._services

    @property
    def is_user_secret_decrypted(self):
        return self.plaintext_user_secret is not None

    def _encrypt_user_secret(self, plaintext_password):
        """
        Implementation taken from the pyca/cryptography docs:
        https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
        """
        salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.encryption_iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(plaintext_password.encode()))
        f = Fernet(key)
        token = f.encrypt(self.plaintext_user_secret)

        self.encrypted_user_secret = {
            "token": token.decode(),
            "salt": base64.b64encode(salt).decode(),
            "iterations": self.encryption_iterations,
        }

    def decrypt_user_secret(self, plaintext_password):
        # see: https://cryptography.io/en/latest/fernet/#using-passwords-with-fernet
        if not self.encrypted_user_secret:
            self._generate_user_secret(plaintext_password)

        token = self.encrypted_user_secret["token"].encode()
        salt = base64.b64decode(self.encrypted_user_secret["salt"])
        iterations = self.encrypted_user_secret["iterations"]

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=iterations,
        )
        key = base64.urlsafe_b64encode(kdf.derive(plaintext_password.encode()))
        f = Fernet(key)

        self.plaintext_user_secret = f.decrypt(token)

        # If this encrypted_user_secret has an outdated (weaker) number of iterations,
        #   re-encrypt with the current higher iteration count.
        if iterations < self.encryption_iterations:
            self._encrypt_user_secret(plaintext_password)

    def _generate_user_secret(self, plaintext_password):
        """
        Generates and stores the user_secret in memory. Also stores it encrypted
        to disk.

        Encryption using the user_secret uses a Fernet key. But the Fernet
        key itself will be encrypted with the user's password.
        """
        self.plaintext_user_secret = Fernet.generate_key()
        self._encrypt_user_secret(plaintext_password)
        self.save_info()
        logger.debug("Generated user_secret")

    def delete_user_secret(self, autosave: bool = True):
        self.encrypted_user_secret = None
        self.plaintext_user_secret = None
        if autosave:
            self.save_info()

    def set_password(self, plaintext_password):
        """Hash the incoming plaintext password and update the encrypted user_secret as
        needed.

        Remember that the underlying user_secret doesn't change if the user changes
        their password; it's the same user_secret but it just needs to be
        re-encrypted using the new password.
        """
        # Check the encrypted_user_secret before saving password change!
        if self.encrypted_user_secret is None:
            # First time this user is initializing their user_secret
            self._generate_user_secret(plaintext_password)
        else:
            if self.plaintext_user_secret is None:
                # encrypted_user_secret hasn't been decrypted in memory; try to decrypt
                # it now (will only work if we're re-enabling the same password for the
                # admin account).
                try:
                    self.decrypt_user_secret(plaintext_password)
                except cryptography.fernet.InvalidToken as e:
                    # Existing encrypted_user_secret cannot be decrypted with this new
                    # password! Alert the calling code to handle (either provide the
                    # previous password to decrypt/re-encrypt or delete all existing
                    # encrypted data for this user (admin) because it's no longer
                    # decryptable).
                    logger.warn(e)
                    raise UserSecretException(
                        "Cannot decrypt existing encrypted_user_secret with the provided password"
                    )
            else:
                # Must keep re-encrypt encrypted_user_secret with the new password.
                self._encrypt_user_secret(plaintext_password)

        self.password_hash = hash_password(plaintext_password)

    @property
    def json(self):
        user_dict = {
            "id": self.id,
            "username": self.username,
            "password": self.password_hash,  # TODO: Migrate attr name to "password_hash"?
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
            self.specter.user_manager.add_user(self)
        if existing and delete:
            self.specter.delete_user(self)
        self.manager.save()

    def add_service(self, service_id: str, autosave: bool = True):
        """Add a Service to the User. Only updates what is listed in the sidebar."""
        if service_id not in self._services:
            self._services.append(service_id)
        if autosave:
            self.save_info()

    def has_service(self, service_id: str) -> bool:
        """Returns true if the User has that service"""
        return service_id in self._services

    def remove_service(self, service_id: str, autosave: bool = True):
        """Remove a Service from the User. Only updates what is listed in the sidebar."""
        if service_id in self.services:
            self.services.remove(service_id)
        if autosave:
            self.save_info()

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
