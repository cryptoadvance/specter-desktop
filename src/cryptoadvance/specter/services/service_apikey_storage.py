import json
import logging
import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.managers.singleton import ConfigurableSingleton
from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.user import User

logger = logging.getLogger("__name__")


class ServiceApiKeyStorageError(Exception):
    pass


class ServiceApiKeyStorage(GenericDataManager):
    """
    Encrypted storage class for *ALL* Services-related API secrets for a given user.
    The json file is stored as: <username>_services.json

    Data is stored internally as a json string for easier encryption handling to disk.

    Each `service_type` that is passed in should come from:
        cryptoadvance.specter.services.ALL_SERVICE_TYPES
    """

    def __init__(self, data_folder: str, user: User):
        if not user.plaintext_user_secret:
            raise ServiceApiKeyStorageError(
                f"User {user} must be authenticated with password before encrypted service data can be loaded"
            )

        # Must set the user before calling the parent's __init__(); it calls load()
        #   which then calls data_file below.
        self.user = user

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

    def set_api_data(self, service_id: str, api_data: dict, autosave: bool = True):
        # Store the api_data json blob as a string
        self.data[service_id] = json.dumps(api_data)
        if autosave:
            self._save()

    def get_api_data(self, service_id: str) -> dict:
        api_data = self.data.get(service_id, None)
        if api_data:
            # Convert string back into json blob
            api_data = json.loads(api_data)
        else:
            api_data = {}
        return api_data



class ServiceApiKeyStorageManager(ConfigurableSingleton):
    """ Singleton that manages access to users' ServiceApiKeyStorage; context-aware so it
        knows who the current_user is for the given request context.

        Requires a one-time configuration call on startup in the ServiceManager.
    """
    @classmethod
    def configure_instance(cls, specter):
        super().configure_instance()
        cls._instance.data_folder = specter.data_folder
        cls._instance.user_manager = specter.user_manager
        cls._instance.storage_by_user = {}

    def _get_current_user_api_key_storage(self) -> ServiceApiKeyStorage:
        """Returns the storage-class for the current_user. Lazy_init if necessary"""
        user = self.user_manager.get_user()
        if user is None:
            raise SpecterError(f"User {user} not existing")

        if self.storage_by_user.get(user) is None:
            logger.info(f"Loaded ServiceApiKeyStorage for user {user}")
            self.storage_by_user[user] = ServiceApiKeyStorage(self.data_folder, user)
        return self.storage_by_user[user]

    def set_current_user_api_data(self, service_id: str, api_data: dict):
        self._get_current_user_api_key_storage().set_api_data(service_id, api_data)

    def get_current_user_api_data(self, service_id: str) -> dict:
        return self._get_current_user_api_key_storage().get_api_data(service_id)
    
    def unload_current_user(self):
        """ Clear user's ServiceApiKeyStorage from memory (but it remains safely on disk) """
        user = self.user_manager.get_user()
        if user and user in self.storage_by_user:
            self.storage_by_user[user] = None