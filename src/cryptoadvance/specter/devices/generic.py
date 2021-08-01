from . import DeviceTypes
from ..device import Device


class GenericDevice(Device):
    device_type = DeviceTypes.GENERICDEVICE
    name = "Other"

    sd_card_support = True
    qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        # in QR codes keep only xpubs
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=True)
        # in SD card put as much as possible
        sd_psbt = wallet.fill_psbt(base64_psbt, non_witness=True, xpubs=True)
        psbts = {"qrcode": qr_psbt, "sdcard": sd_psbt}
        return psbts
