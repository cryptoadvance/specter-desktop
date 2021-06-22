from binascii import a2b_base64
from typing import List
from . import DeviceTypes
from ..util.base43 import b43_encode
from ..device import Device


class Electrum(Device):
    device_type = DeviceTypes.ELECTRUM
    name = "Electrum"
    icon = "electrum_icon.svg"

    sd_card_support = True
    qr_code_support = True
    qr_code_animate = "off"

    def create_psbts(self, base64_psbt, wallet):
        # remove non_witness utxo for QR code
        updated_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        psbts = {"qrcode": b43_encode(a2b_base64(updated_psbt)), "sdcard": base64_psbt}
        return psbts
