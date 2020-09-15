from .hwi_device import HWIDevice


class BitBox2(HWIDevice):
    device_type = "bitbox02"
    name = "BitBox2"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
