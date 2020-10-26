from ..device import Device


class GenericDevice(Device):
    device_type = "other"
    name = "Other"

    sd_card_support = True
    qr_code_support = True

    def __init__(self, name, alias, keys, fullpath, manager):
        super().__init__(name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        psbts = {"qrcode": base64_psbt, "sdcard": base64_psbt}
        return psbts
