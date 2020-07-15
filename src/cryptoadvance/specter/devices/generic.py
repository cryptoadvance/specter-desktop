from ..device import Device

class GenericDevice(Device):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        super().__init__(name, alias, 'other', keys, fullpath, manager)
        self.sd_card_support = True
        self.qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = {
            'qrcode': base64_psbt,
            'sdcard': base64_psbt,
        }
        return psbts
