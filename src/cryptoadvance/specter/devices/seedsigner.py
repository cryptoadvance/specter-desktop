from . import DeviceTypes
from ..device import Device


class SeedSignerDevice(Device):
    device_type = DeviceTypes.SEEDSIGNER
    name = "SeedSigner"
    icon = "seedsigner_icon.svg"

    sd_card_support = False
    qr_code_support = True
    qr_code_frame_rate = 2  # 500 ms per frame
    qr_code_animate = "on"

    def create_psbts(self, base64_psbt, wallet):
        # in QR codes keep only xpubs
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=True)
        # in SD card put as much as possible
        psbts = {"qrcode": qr_psbt}
        return psbts
