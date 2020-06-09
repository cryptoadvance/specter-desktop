import os, json, logging
from .device import Device
from .helpers import alias, load_jsons


logger = logging.getLogger(__name__)

class DeviceManager:
    ''' A DeviceManager mainly manages the persistence of a device-json-structures
        compliant to helper.load_jsons
    '''
    # of them via json-files in an empty data folder
    def __init__(self, data_folder):
        self.update(data_folder)

    def update(self, data_folder=None):
        self.devices = {}
        if data_folder is not None:
            self.data_folder = data_folder
            if data_folder.startswith("~"):
                data_folder = os.path.expanduser(data_folder)
            # creating folders if they don't exist
            if not os.path.isdir(data_folder):
                os.mkdir(data_folder)
        devices_files = load_jsons(self.data_folder, key="name")
        for device in devices_files:
            self.devices[devices_files[device]["name"]] = (Device(devices_files[device], manager=self))
    
    @property
    def devices_names(self):
        return sorted(self.devices.keys())

    def add_device(self, name, device_type, keys):
        device = {
            "name": name,
            "type": device_type,
            "keys": []
        }
        fname = alias(name)
        i = 2
        while os.path.isfile(os.path.join(self.data_folder, "%s.json" % fname)):
            fname = alias("%s %d" % (name, i))
            i+=1

        for k in keys:
            if k["original"] not in [k["original"] for k in device["keys"]]:
                device["keys"].append(k)
        with open(os.path.join(self.data_folder, "%s.json" % fname), "w") as f:
            f.write(json.dumps(device, indent=4))
        self.update() # reload files
        return self.devices[name]

    def get_by_alias(self, fname):
        for device_name in self.devices:
            if self.devices[device_name]["alias"] == fname:
                return self.devices[device_name]
        logger.error("Could not find Device %s" % fname)

    def remove_device(self, device):
        os.remove(device["fullpath"])
        self.update()
