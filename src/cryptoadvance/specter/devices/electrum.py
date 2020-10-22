from binascii import a2b_base64
from ..util.base43 import b43_encode
from typing import List
from ..device import Device


class Electrum(Device):
    device_type = "electrum"
    name = "Electrum"

    sd_card_support = True
    qr_code_support = True

    def __init__(self, name, alias, keys, fullpath, manager):
        super().__init__(name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        # remove non_witness utxo for QR code
        updated_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        psbts = {"qrcode": b43_encode(a2b_base64(updated_psbt)), "sdcard": base64_psbt}
        return psbts
