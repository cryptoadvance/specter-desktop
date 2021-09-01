from ..device import Device
import hwilib.commands as hwi_commands
import importlib


class HWIDevice(Device):

    hwi_support = True
    exportable_to_wallet = False

    def create_psbts(self, base64_psbt, wallet):
        return {"hwi": wallet.fill_psbt(base64_psbt)}

    @classmethod
    def enumerate(cls, *args, **kwargs):
        mod = importlib.import_module(f"hwilib.devices.{cls.device_type}")
        return mod.enumerate(*args, **kwargs)

    @classmethod
    def get_client(cls, *args, **kwargs):
        return hwi_commands.get_client(cls.device_type, *args, **kwargs)
