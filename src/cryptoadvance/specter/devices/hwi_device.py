from ..device import Device
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
