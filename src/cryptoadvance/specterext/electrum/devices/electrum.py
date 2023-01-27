from binascii import a2b_base64
from typing import List
from cryptoadvance.specter.util.base43 import b43_encode
from cryptoadvance.specter.device import Device


class Electrum(Device):
    device_type = "electrum"
    name = "Electrum"
    icon = "electrum/img/devices/electrum_icon.svg"
    template = "electrum/device/new_device_keys_electrum.jinja"

    sd_card_support = True
    qr_code_support = True
    qr_code_animate = "off"

    def create_psbts(self, base64_psbt, wallet):
        # remove non_witness utxo for QR code
        updated_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        psbts = {"qrcode": b43_encode(a2b_base64(updated_psbt)), "sdcard": base64_psbt}
        return psbts
