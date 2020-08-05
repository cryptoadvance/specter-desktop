from ..device import Device


class GenericDevice(Device):
    device_type = "other"
    name = "Other"

    def __init__(self, name, alias, keys, fullpath, manager):
        super().__init__(name, alias, keys, fullpath, manager)
        self.sd_card_support = True
        self.qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = {
            'qrcode': base64_psbt,
            'sdcard': base64_psbt,
        }
        return psbts
