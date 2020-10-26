import json
from .key import Key
from .persistence import read_json_file, write_json_file
import logging

logger = logging.getLogger()


class Device:
    device_type = None  # this is saved to json
    name = "Unknown device"  # this is how device appears in UI

    # override these vars to add support
    # of different communication methods
    sd_card_support = False
    qr_code_support = False
    hwi_support = False
    supports_hwi_toggle_passphrase = False
    supports_hwi_multisig_display_address = False
    hot_wallet = False

    def __init__(self, name, alias, keys, fullpath, manager):
        """
        From child classes call super().__init__ and also set
        support for communication methods
        """
        self.name = name
        self.alias = alias
        self.keys = keys
        self.fullpath = fullpath
        self.manager = manager

    def create_psbts(self, base64_psbt, wallet):
        """
        Overwrite this method for a device.
        Possible keys:
        hwi, qrcode, sdcard
        """
        return {}

    @classmethod
    def from_json(cls, device_dict, manager, default_alias="", default_fullpath=""):
        name = device_dict["name"] if "name" in device_dict else ""
        alias = device_dict["alias"] if "alias" in device_dict else default_alias
        keys = [Key.from_json(key_dict) for key_dict in device_dict["keys"]]
        fullpath = (
            device_dict["fullpath"] if "fullpath" in device_dict else default_fullpath
        )
        return cls(name, alias, keys, fullpath, manager)

    @property
    def json(self):
        return {
            "name": self.name,
            "alias": self.alias,
            "type": self.device_type,
            "keys": [key.json for key in self.keys],
            "fullpath": self.fullpath,
        }

    def _update_keys(self):
        write_json_file(self.json, self.fullpath)
        self.manager.update()

    def remove_key(self, key):
        self.keys = [k for k in self.keys if k != key]
        self._update_keys()

    def add_keys(self, keys):
        for key in keys:
            if key not in self.keys:
                self.keys.append(key)
        self._update_keys()

    def rename(self, new_name):
        logger.info("Renaming {}".format(self.alias))
        self.name = new_name
        write_json_file(self.json, self.fullpath)
        self.manager.update()

    def wallets(self, wallet_manager):
        wallets = []
        for wallet in wallet_manager.wallets.values():
            if self in wallet.devices:
                wallets.append(wallet)
        return wallets

    def set_type(self, device_type):
        self.device_type = device_type

        write_json_file(self.json, self.fullpath)
        self.manager.update()

    def key_types(self, network="main"):
        test = network != "main"
        return [key.key_type for key in self.keys if (key.is_testnet == test)]

    def __eq__(self, other):
        if other is None:
            return False
        return self.alias == other.alias

    def __hash__(self):
        return hash(self.alias)
