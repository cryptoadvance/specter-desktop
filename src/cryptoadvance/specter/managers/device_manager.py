import os
import json
import logging
from flask_babel import lazy_gettext as _

from ..helpers import alias, load_jsons
from ..rpc import get_default_datadir

from ..devices import __all__ as device_classes
from ..devices.generic import GenericDevice  # default device type
from ..persistence import write_device, delete_file, delete_folder

logger = logging.getLogger(__name__)


def get_device_class(device_type):
    """Look up device class by its type"""
    for cls in device_classes:
        if device_type == cls.device_type:
            return cls
    return GenericDevice


class DeviceManager:
    """A DeviceManager mainly manages the persistence of a device-json-structures
    compliant to helper.load_jsons
    """

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
            devices[devices_files[device_alias]["name"]] = get_device_class(
                devices_files[device_alias]["type"]
            ).from_json(
                devices_files[device_alias],
                self,
                default_alias=device_alias,
                default_fullpath=fullpath,
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
        device = get_device_class(device_type)(
            name, device_alias, keys, "", fullpath, self
        )
        write_device(device, fullpath)
        self.update()  # reload files
        return device

    def get_by_alias(self, device_alias):
        for device_name in self.devices:
            if self.devices[device_name].alias == device_alias:
                return self.devices[device_name]
        logger.error(_("Could not find Device {}").format(device_alias))

    def remove_device(
        self,
        device,
        wallet_manager=None,
        bitcoin_datadir=get_default_datadir(),
        chain="main",
    ):
        delete_file(device.fullpath)
        # if device can delete itself - call it
        if hasattr(device, "delete"):
            device.delete(wallet_manager, bitcoin_datadir=bitcoin_datadir, chain=chain)
        self.update()

    @property
    def supported_devices(self):
        return device_classes

    def supported_devices_for_chain(self, specter):
        if not specter.chain:
            return [
                device_class
                for device_class in device_classes
                if device_class.device_type != "bitcoincore"
                and device_class.device_type != "elementscore"
            ]
        elif specter.is_liquid:
            return [
                device_class
                for device_class in device_classes
                if device_class.liquid_support
            ]
        else:
            return [
                device_class
                for device_class in device_classes
                if device_class.bitcoin_core_support
            ]

    def delete(self, specter):
        """Deletes all the devices"""
        for d in self.devices:
            device = self.devices[d]
            self.remove_device(device)
        delete_folder(self.data_folder)
