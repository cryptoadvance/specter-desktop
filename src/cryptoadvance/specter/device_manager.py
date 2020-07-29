import os
import json
import logging
import time
import zipfile
from io import BytesIO
from .devices.coldcard import ColdCard
from .devices.trezor import Trezor
from .devices.ledger import Ledger
from .devices.keepkey import Keepkey
from .devices.specter import Specter
from .devices.cobo import Cobo
from .devices.generic import GenericDevice
from .devices.electrum import Electrum
from .devices.bitcoin_core import BitcoinCore
from .helpers import alias, load_jsons, fslock
from .rpc import get_default_datadir


logger = logging.getLogger(__name__)

device_classes = {
    'coldcard': ColdCard,
    'trezor': Trezor,
    'keepkey': Keepkey,
    'ledger': Ledger,
    'specter': Specter,
    'cobo': Cobo,
    'bitcoincore': BitcoinCore,
    'electrum': Electrum,
    'other': GenericDevice,
}

def get_device_class(device_type):
    if device_type in device_classes:
        return device_classes[device_type]
    return GenericDevice

class DeviceManager:
    ''' A DeviceManager mainly manages the persistence of a device-json-structures
        compliant to helper.load_jsons
    '''
    # of them via json-files in an empty data folder
    def __init__(self, data_folder):
        self.update(data_folder=data_folder)

    def update(self, data_folder=None):
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        devices = {}
        devices_files = load_jsons(self.data_folder, key="name")
        for device_alias in devices_files:
            fullpath = os.path.join(self.data_folder, "%s.json" % device_alias)
            devices[devices_files[device_alias]["name"]] = get_device_class(devices_files[device_alias]["type"]).from_json(
                devices_files[device_alias],
                self,
                default_alias=device_alias,
                default_fullpath=fullpath
            )
        self.devices = devices

    @property
    def devices_names(self):
        return sorted(self.devices.keys())

    def add_device(self, name, device_type, keys):
        device_alias = alias(name)
        fullpath = os.path.join(self.data_folder, "%s.json" % device_alias)
        i = 2
        while os.path.isfile(fullpath):
            device_alias = alias("%s %d" % (name, i))
            fullpath = os.path.join(self.data_folder, "%s.json" % device_alias)
            i += 1
        # remove duplicated keys if any exist
        non_dup_keys = []
        for key in keys:
            if key not in non_dup_keys:
                non_dup_keys.append(key)
        keys = non_dup_keys
        device = get_device_class(device_type)(name, device_alias, device_type, keys, fullpath, self)
        with fslock:
            with open(fullpath, "w") as file:
                file.write(json.dumps(device.json, indent=4))

        self.update()  # reload files
        return device

    def get_by_alias(self, device_alias):
        for device_name in self.devices:
            if self.devices[device_name].alias == device_alias:
                return self.devices[device_name]
        logger.error("Could not find Device %s" % device_alias)

    def remove_device(
        self,
        device,
        wallet_manager=None,
        bitcoin_datadir=get_default_datadir()
    ):
        os.remove(device.fullpath)
        if isinstance(device, BitcoinCore):
            device.delete(wallet_manager, bitcoin_datadir=bitcoin_datadir)
        self.update()
