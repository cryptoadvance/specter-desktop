from ..device import Device


class GenericDevice(Device):
    device_type = "other"
    name = "Other"

    sd_card_support = True
    qr_code_support = True

    def __init__(self, name, alias, keys, fullpath, manager):
        super().__init__(name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        # in QR codes keep only xpubs
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=True)
        # in SD card put as much as possible
        sd_psbt = wallet.fill_psbt(base64_psbt, non_witness=True, xpubs=True)
        psbts = {"qrcode": qr_psbt, "sdcard": sd_psbt}
        return psbts
