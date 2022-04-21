import json
import logging
import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.managers.singleton import ConfigurableSingleton
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.user import User

logger = logging.getLogger("__name__")


class ServiceEncryptedStorageError(Exception):
    pass


class ServiceEncryptedStorage(GenericDataManager):
    """
    Encrypted storage class for *ALL* Services-related secrets and config for a given user.
    The json file is stored as: <username>_services.json

    Each Service may specify its own json data format.

    Data is stored internally as a json string for easier encryption handling to disk.

    Note that this is storage is separate from the un-encrypted ServiceAnnotationsStorage.
    This storage is meant for secrets that must be encrypted and any Service-related config
    that the User might need to store (e.g. which Wallet is attached to the Service). This
    config data doesn't need to be encrypted, but we may as well store it here rather than
    adding data bloat to the User json.

    * `disable_decrypt`: Allows the ServiceEncryptedStorageManager to see which Services
        have data but without attempting to decrypt the values. This allows us to check
        if there is encrypted Service data even when we don't have the
        plaintext_user_secret.
    """

    def __init__(self, data_folder: str, user: User, disable_decrypt: bool = False):

        if not user.plaintext_user_secret and not disable_decrypt:
            raise ServiceEncryptedStorageError(
                f"User {user} must be authenticated with password before encrypted service data can be loaded"
            )

        # Must set the user before calling the parent's __init__(); it calls load()
        #   which then calls data_file below.
        self.user = user

        if disable_decrypt:
            super().__init__(data_folder, encryption_key=None)
        else:
            super().__init__(data_folder, encryption_key=user.plaintext_user_secret)

    @property
    def encrypted_fields(self):
        """We override the class member to force ALL data fields to be considered
        encrypted."""
        fields = list(self.data.keys())
        if "encrypted_storage_version" in fields:
            fields.pop(fields.index("encrypted_storage_version"))
        return fields

    @property
    def data_file(self):
        return os.path.join(self.data_folder, f"{self.user.username}_services.json")

    def set_service_data(self, service_id: str, data: dict, autosave: bool = True):
        """Store the api_data json blob as a string; completely overwrites previous state"""
        if data == {} and service_id in self.data:
            del self.data[service_id]
        else:
            self.data[service_id] = json.dumps(data)
        if autosave:
            self._save()

    def update_service_data(self, service_id: str, data: dict, autosave: bool = True):
        if data == {}:
            logger.debug("This is a nonsense no-op")
            return

        # Add or update fields; does not remove existing fields
        if service_id not in self.data:
            # Initialize a blank entry
            cur_data = {}
        else:
            cur_data = json.loads(self.data[service_id])
        cur_data.update(data)
        self.data[service_id] = json.dumps(cur_data)
        if autosave:
            self._save()

    def get_service_data(self, service_id: str) -> dict:
        service_data = self.data.get(service_id, None)
        if service_data:
            # Convert string back into json blob
            service_data = json.loads(service_data)
        else:
            service_data = {}
        return service_data


class ServiceUnencryptedStorage(ServiceEncryptedStorage):
    """In order to use ServiceEncryptedStorage but unencrypted, we derive from that class
    and change the datafile.
    """

    def __init__(self, data_folder: str, user: User, disable_decrypt: bool = False):
        if not disable_decrypt:
            raise Exception(
                "ServiceUnencryptedStorage needs to be initialized with disable_decrypt = True"
            )
        if disable_decrypt:
            super().__init__(data_folder, encryption_key=None, disable_decrypt=True)

    @property
    def data_file(self):
        return os.path.join(
            self.data_folder, f"{self.user.username}_unencrypted_services.json"
        )


class ServiceEncryptedStorageManager(ConfigurableSingleton):
    """Singleton that manages access to users' ServiceApiKeyStorage; context-aware so it
    knows who the current_user is for the given request context.

    Requires a one-time configuration call on startup in the ServiceManager.
    """

    @classmethod
    def configure_instance(cls, data_folder, user_manager):
        super().configure_instance()
        cls._instance.data_folder = data_folder
        cls._instance.user_manager = user_manager
        cls._instance.storage_by_user = {}

    def get_raw_encrypted_data(self, user: User) -> dict:
        """Doesn't attempt to decrypt the ServiceEncryptedStorage, just returns the
        user's full encrypted Service data json as-is."""
        return ServiceEncryptedStorage(
            self.data_folder, user, disable_decrypt=True
        ).data

    def _get_current_user_service_storage(self) -> ServiceEncryptedStorage:
        """Returns the storage-class for the current_user. Lazy_init if necessary"""
        user = self.user_manager.get_user()

        if user not in self.storage_by_user:
            self.storage_by_user[user] = ServiceEncryptedStorage(self.data_folder, user)
        return self.storage_by_user[user]

    def set_current_user_service_data(self, service_id: str, service_data: dict):
        self._get_current_user_service_storage().set_service_data(
            service_id, service_data
        )

    def update_current_user_service_data(self, service_id: str, service_data: dict):
        # Add or update fields; does not remove existing fields
        self._get_current_user_service_storage().update_service_data(
            service_id, service_data
        )

    def get_current_user_service_data(self, service_id: str) -> dict:
        service_storage = self._get_current_user_service_storage()
        if service_storage:
            return service_storage.get_service_data(service_id)

    def unload_current_user(self):
        """Clear user's ServiceEncryptedStorage from memory (but it remains safely on disk)"""
        user = self.user_manager.get_user()
        if user and user in self.storage_by_user:
            self.storage_by_user[user] = None

    def delete_all_service_data(self, user: User):
        """Completely removes all data in the User's ServiceEncryptedStorage from memory and on-disk."""
        # Clear it from memory...
        self.storage_by_user.pop(user, None)

        # ...and wipe the on-disk storage
        encrypted_storage = ServiceEncryptedStorage(
            self.data_folder, user, disable_decrypt=True
        )
        encrypted_storage.data = {}
        encrypted_storage._save()


class ServiceUnencryptedStorageManager(ServiceEncryptedStorageManager):
    def __init__(self, user_manager, data_folder):
        self.user_manager = user_manager
        self.data_folder = data_folder
        self.storage_by_user = {}

    def _get_current_user_service_storage(self) -> ServiceEncryptedStorage:
        """Returns the storage-class for the current_user. Lazy_init if necessary"""
        user = self.user_manager.get_user()

        if user not in self.storage_by_user:
            self.storage_by_user[user] = ServiceUnencryptedStorage(
                self.data_folder, user, disable_decrypt=True
            )
        return self.storage_by_user[user]
