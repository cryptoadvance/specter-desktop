from ..device import Device
import hwilib.commands as hwi_commands

class HWIDevice(Device):

    hwi_support = True
    exportable_to_wallet = False

    def __init__(self, name, alias, keys, fullpath, manager):
        Device.__init__(self, name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        return {'hwi': wallet.fill_psbt(base64_psbt)}

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return [ dev for dev
        		 in hwi_commands.enumerate(*args, **kwargs)
        		 if dev["type"] == cls.device_type
        		]

    @classmethod
    def get_client(cls, *args, **kwargs):
        return hwi_commands.get_client(cls.device_type, *args, **kwargs)
