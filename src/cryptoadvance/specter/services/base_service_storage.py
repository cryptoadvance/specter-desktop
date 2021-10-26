import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.user import User


from . import ALL_SERVICES


class BaseServiceStorage(GenericDataManager):
    """
    Base on-disk encrypted storage class for Services. Each Service will implement
    their own ServiceStorage class as needed.

    ServiceStorage is linked to a specific user. The json file is stored as:
    <username>_<service>.json
    """

    encrypted_fields = ["api_key", "api_secret"]

    # Must be specified in each implementation class
    service_type = None

    def __init__(self, data_folder: str, user: User):
        if self.__class__.service_type not in ALL_SERVICES:
            raise Exception("Must set service_type in the implementation class")
        if not user.plaintext_user_secret:
            raise Exception(
                "User must be authenticated with password before encrypted service data can be loaded"
            )

        # Must set the user before calling the parent's __init__(); it calls load()
        #   which then calls data_file below.
        self.user = user

        super().__init__(data_folder, encryption_key=user.plaintext_user_secret)

    @property
    def data_file(self):
        return os.path.join(
            self.data_folder, f"{self.user.username}_{self.__class__.service_type}.json"
        )

    def set_credentials(self, api_key: str, api_secret: str):
        self.data["api_key"] = api_key
        self.data["api_secret"] = api_secret
        self._save()

    def get_credentials(self):
        return (self.data.get("api_key", None), self.data.get("api_secret", None))
