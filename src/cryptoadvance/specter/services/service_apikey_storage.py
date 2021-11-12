import json
import logging
import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.managers.user_manager import UserManager
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.user import User

logger = logging.getLogger("__name__")


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
            raise Exception(
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

    def set_api_data(self, service_type: str, api_data: dict, autosave: bool = True):
        # Store the api_data json blob as a string
        self.data[service_type] = json.dumps(api_data)
        if autosave:
            self._save()

    def get_api_data(self, service_type: str) -> dict:
        api_data = self.data.get(service_type, None)
        if api_data:
            # Convert string back into json blob
            api_data = json.loads(api_data)
        return api_data


class ServiceApiKeyStorageUserAware:
    """Store and receive your Secrets automagically by user"""

    def __init__(self, data_folder: str, user_manager: UserManager):
        self.data_folder = data_folder
        self.user_manager = user_manager
        self.user_storage_map = {}

    def _user_storage(self) -> ServiceApiKeyStorage:
        """Returns the storage-class for the current_user. Lazy_init if necessary"""
        user = self.user_manager.get_user()
        if user is None:
            raise SpecterError(f"User {user} not existing")

        if self.user_storage_map.get(user) is None:
            logger.info(f"creating ServiceApiKeyStorage for user {user}")
            self.user_storage_map[user] = ServiceApiKeyStorage(self.data_folder, user)
        return self.user_storage_map[user]

    def set_api_data(self, service_id: str, api_data: dict):
        self._user_storage().set_api_data(service_id, api_data)

    def get_api_data(self, service_id: str) -> dict:
        return self._user_storage().get_api_data(service_id)
