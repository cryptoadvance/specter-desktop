import os
import logging

from cryptography.fernet import Fernet

from ..persistence import read_json_file, write_json_file


logger = logging.getLogger(__name__)


class GenericDataManager:
    """
    A GenericDataManager manages json-data in self.data in a json file. It's meant to
    be derived from. See OtpManager
    """

    name_of_json_file = "some_data.json"

    @classmethod
    def initial_data(cls):
        return {}

    @classmethod
    def convert_to_list_of_type(cls, some_list):
        """This is not yet used but might be convenient
        An array of elements get converted to a list of a specific types
        Maybe this method simply does nothing, though
        """
        return some_list
        # example implementation for users:
        # return [User.from_json(u, self.specter) for u in some_list]

    @classmethod
    def convert_to_list_of_dict(cls, some_list):
        """This is not yet used but might be convenient
        An array of a specific type gets converted to a list of dicts
        Maybe this method simply does nothing, though
        """
        return some_list
        # example implementation for users:
        # return [u.json for u in some_list]

    @classmethod
    def encrypt_string(cls, message, key):
        fernet = Fernet(key)
        return fernet.encrypt(message.encode())

    @classmethod
    def decrypt_string(cls, message, key):
        fernet = Fernet(key)
        return fernet.encrypt(message.encode())

    def __init__(self, data_folder):
        # password indicates that the data needs to be encrypted at rest. Specter should
        #   never internally store the password. It is only provided here to decrypt
        #   storage!
        self.data_folder = data_folder
        self.load()

    @property
    def data_file(self):
        return os.path.join(self.data_folder, self.__class__.name_of_json_file)

    def load(self):
        # if whatever-the-name.json file exists - load from it
        if os.path.isfile(self.data_file):
            logger.debug(f"Loading existing file {self.data_file}")
            self.data = read_json_file(self.data_file)
        # otherwise - create one and assign unique id
        else:
            logger.debug(f"{self.data_file} not existing. Creating ...")
            self.data = self.__class__.initial_data()
            self._save()

    def _save(self):
        # data_json = convert_to_list_of_dict(self.data)
        write_json_file(self.data, self.data_file)
