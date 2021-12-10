import os
import json
import logging
from cryptoadvance.specter.persistence import read_json_file, write_json_file
from cryptoadvance.specter.user import User
from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from flask_login import current_user, UserMixin

logger = logging.getLogger(__name__)


# TODO: This is outdated/unused now that we have the encrypted ServiceApiKeyStorage
class ServiceSettingsManager(GenericDataManager):
    """
    The ServiceSettingsManager manages settings for services
    It's user-aware and so you have to pass in user-IDs whenever you want to
    load or store a setting
    """

    name_of_json_file = "some_data.json"

    def __init__(self, data_folder, service_name):
        self.service_name = service_name
        super().__init__(data_folder)

    @property
    def data_file(self):
        return os.path.join(self.data_folder, "%s.json" % self.service_name)

    def update(self, data_folder):

        self.load_settings()

    def set_key(self, user, key, value):
        if user not in self.data:
            self.data[user] = {}
        self.data[user][key] = value
        self._save()

    def get_key(self, user, key):
        print(f"usertype: {type(user)}")
        if isinstance(user, UserMixin):
            user = user.id
        if user not in self.data:
            self.data[user] = {}
            self._save()
        if not self.data[user].get(key):
            return ""
        return self.data[user][key]
