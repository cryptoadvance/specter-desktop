import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.user import User


class ServiceApiKeyStorage(GenericDataManager):
    """
    Encrypted storage class for *ALL* Services-related API secrets for a given user.
    The json file is stored as: <username>_services.json

    Each `service_type` that is passed in should come from:
        cryptoadvance.specter.services.ALL_SERVICE_TYPES
    """

    def __init__(self, data_folder: str, user: User):
        if not user.plaintext_user_secret:
            raise Exception(
                "User must be authenticated with password before encrypted service data can be loaded"
            )

        # Must set the user before calling the parent's __init__(); it calls load()
        #   which then calls data_file below.
        self.user = user

        super().__init__(data_folder, encryption_key=user.plaintext_user_secret)

    @property
    # TODO: Change to json blob
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

    def set_credentials(self, service_type: str, api_key: str, api_secret: str):
        self.data[f"{service_type}_api_key"] = api_key
        self.data[f"{service_type}_api_secret"] = api_secret
        self._save()

    def get_credentials(self, service_type: str):
        return (
            self.data.get(f"{service_type}_api_key", None),
            self.data.get(f"{service_type}_api_secret", None),
        )

    def set_additional_field(
        self, service_type: str, field_name: str, field_value: str
    ):
        """Store any other arbitrary encrypted field for the given Service"""
        self.data[f"{service_type}_{field_name}"] = field_value
        self._save()

    def get_additional_field(self, service_type: str, field_name: str):
        return self.data.get(f"{service_type}_{field_name}", None)
