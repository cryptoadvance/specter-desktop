from .hwi_device import HWIDevice
from .hwi.bitbox02 import enumerate as bitbox02_enumerate, Bitbox02Client


class BitBox02(HWIDevice):
    device_type = "bitbox02"
    name = "BitBox02"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return bitbox02_enumerate(*args, **kwargs)

    @classmethod
    def get_client(cls, *args, **kwargs):
        return Bitbox02Client(*args, **kwargs)
