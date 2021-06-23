import json
from .key import Key
from .persistence import read_json_file, write_json_file
import logging
from .helpers import is_testnet, is_liquid

logger = logging.getLogger(__name__)


class Device:
    device_type = None  # this is saved to json
    name = "Unknown device"  # this is how device appears in UI
    icon = "other_icon.svg"

    # override these vars to add support
    # of different communication methods
    sd_card_support = False
    qr_code_support = False
    qr_code_support_verify = False
    qr_code_frame_rate = 3  # ~300 ms per frame
    # QR code animation options:
    # - "auto": click to animate if data is large
    # - "on": animate psbt by default
    # - "off": don't animate psbt even if it is huge
    qr_code_animate = "auto"
    hwi_support = False
    supports_hwi_toggle_passphrase = False
    supports_hwi_multisig_display_address = False
    hot_wallet = False
    bitcoin_core_support = True
    liquid_support = False

    def __init__(self, name, alias, keys, blinding_key, fullpath, manager):
        """
        From child classes call super().__init__ and also set
        support for communication methods
        """
        self.name = name
        self.alias = alias
        self.keys = keys
        self.fullpath = fullpath
        self.blinding_key = blinding_key
        self.manager = manager

    def create_psbts(self, base64_psbt, wallet):
        """
        Overwrite this method for a device.
        Possible keys:
        hwi, qrcode, sdcard
        """
        return {}

    @classmethod
    def from_json(
        cls,
        device_dict,
        manager,
        default_alias="",
        default_fullpath="",
        default_blinding_key="",
    ):
        name = device_dict["name"] if "name" in device_dict else ""
        alias = device_dict["alias"] if "alias" in device_dict else default_alias
        keys = [Key.from_json(key_dict) for key_dict in device_dict["keys"]]
        blinding_key = (
            device_dict["blinding_key"]
            if "blinding_key" in device_dict
            else default_blinding_key
        )
        fullpath = (
            device_dict["fullpath"] if "fullpath" in device_dict else default_fullpath
        )
        return cls(name, alias, keys, blinding_key, fullpath, manager)

    @property
    def json(self):
        return {
            "name": self.name,
            "alias": self.alias,
            "type": self.device_type,
            "keys": [key.json for key in self.keys],
            "blinding_key": self.blinding_key,
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
        if wallet_manager is None:
            return []
        wallets = []
        for wallet in wallet_manager.wallets.values():
            if self in wallet.devices:
                wallets.append(wallet)
        return wallets

    def set_type(self, device_type):
        self.device_type = device_type

        write_json_file(self.json, self.fullpath)
        self.manager.update()

    def set_blinding_key(self, blinding_key):
        self.blinding_key = blinding_key

        write_json_file(self.json, self.fullpath)
        self.manager.update()

    def key_types(self, network="main"):
        test = is_testnet(network)
        return [key.key_type for key in self.keys if (key.is_testnet == test)]

    def has_key_types(self, wallet_type, network="main"):
        if is_liquid(network) and not self.liquid_support:
            return False
        if wallet_type == "multisig":
            for key_type in self.key_types(network):
                if key_type in ["", "sh-wsh", "wsh"]:
                    return True
        elif wallet_type == "simple":
            for key_type in self.key_types(network):
                if key_type in ["", "sh-wpkh", "wpkh"]:
                    return True
        return "" in self.key_types(network)

    def no_key_found_reason(self, wallet_type, network="main"):
        if self.has_key_types(wallet_type, network=network):
            return ""
        if is_liquid(network) and not self.liquid_support:
            return "This device type does not yet support Liquid"
        reverse_network = "main" if is_testnet(network) else "test"
        if wallet_type == "multisig":
            for key_type in self.key_types(reverse_network):
                if key_type in ["", "sh-wsh", "wsh"]:
                    return "Multisig compatible keys were found, but for the wrong network, make sure to add keys for the right network."
        elif wallet_type == "simple":
            for key_type in self.key_types(reverse_network):
                if key_type in ["", "sh-wpkh", "wpkh"]:
                    return "Single-sig compatible keys were found, but for the wrong network, make sure to add keys for the right network.".format(
                        "Single key" if wallet_type == "simple" else "Multisig"
                    )
        return "No keys found with the correct derivation type for a {} wallet.".format(
            "single key" if wallet_type == "simple" else "multisig"
        )

    def __eq__(self, other):
        if other is None:
            return False
        return self.alias == other.alias

    def __hash__(self):
        return hash(self.alias)
