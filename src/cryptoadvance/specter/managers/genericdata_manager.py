import copy
import logging
import os

from cryptography.fernet import Fernet

from ..persistence import read_json_file, write_json_file


logger = logging.getLogger(__name__)


class GenericDataManager:
    """
    A GenericDataManager manages json-data in self.data in a json file. It's meant to
    be derived from. See OtpManager.

    Supports encrypting individual attributes rest. Expects a Fernet key that is unique
    to the user to encrypt/decrypt.
    """

    name_of_json_file = "some_data.json"
    encrypted_fields = []

    # Track any changes to our encryption implementation so we can migrate up any older
    #   data as we go.
    encrypted_storage_version = 1

    @classmethod
    def initial_data(cls):
        return {}

    def __init__(self, data_folder, encryption_key=None):
        # encryption_key indicates that the encrypted_fields (if any) need to be
        #   encrypted at rest.
        self.data_folder = data_folder
        self.encryption_key = encryption_key
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
            logger.debug(f"{self.data_file} doesn't exist. Creating ...")
            self.data = self.__class__.initial_data()
            self._save()

        if self.encryption_key:
            # Decrypt the encrypted fields and store in memory as plaintext
            fernet = Fernet(self.encryption_key)

            if (
                "encrypted_storage_version" in self.data
                and self.encrypted_storage_version
                != self.data["encrypted_storage_version"]
            ):
                raise Exception(
                    "Upgrading a previous encryption version is not yet implemented"
                )

            for attr in self.encrypted_fields:
                if attr in self.data and self.data[attr] is not None:
                    self.data[attr] = fernet.decrypt(self.data[attr].encode()).decode()

    def _save(self):
        if self.encryption_key:
            # Preserve the in-memory data but encrypt a copy to write to disk
            fernet = Fernet(self.encryption_key)
            output_dict = copy.deepcopy(self.data)
            for attr in self.encrypted_fields:
                if attr in output_dict and output_dict[attr] is not None:
                    output_dict[attr] = fernet.encrypt(
                        output_dict[attr].encode()
                    ).decode()
        else:
            output_dict = self.data

        if self.encrypted_fields:
            output_dict["encrypted_storage_version"] = self.encrypted_storage_version

        write_json_file(output_dict, self.data_file)
