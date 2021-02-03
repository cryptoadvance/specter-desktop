import os
import json
import logging
from cryptoadvance.specter.persistence import read_json_file, write_json_file
from cryptoadvance.specter.user import User
from flask_login import current_user, UserMixin

logger = logging.getLogger(__name__)


class ServiceSettingsManager:
    """
    The ServiceSettingsManager manages settings for services
    It's user-aware and so you have to pass in user-IDs whenever you want to
    load or store a setting
    """

    def __init__(self, specter, service_name):
        self.service_name = service_name
        data_folder = specter.data_folder
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        self.data_folder = os.path.join(data_folder, "services")
        # creating folder if not existing
        if not os.path.isdir(self.data_folder):
            os.mkdir(self.data_folder)
        self.load_settings()

    @property
    def settings_file(self):
        return os.path.join(self.data_folder, "%s.json" % self.service_name)

    def update(self, data_folder):

        self.load_settings()

    def load_settings(self):
        # if users.json file exists - load from it
        if os.path.isfile(self.settings_file):
            self.settings = read_json_file(self.settings_file)
        # otherwise - create one and assign unique id
        else:
            self.settings = {"admin": {}}
        # convert to User instances
        if not os.path.isfile(self.settings_file):
            self.save()

    def save(self):
        write_json_file(self.settings, self.settings_file)

    def set_key(self, user, key, value):
        if user not in self.settings:
            self.settings[user] = {}
        self.settings[user][key] = value
        self.save()

    def get_key(self, user, key):
        print(f"usertype: {type(user)}")
        if isinstance(user, UserMixin):
            user = user.id
        if user not in self.settings:
            self.settings[user] = {}
            self.save()
        if not self.settings[user].get(key):
            return ""
        return self.settings[user][key]
