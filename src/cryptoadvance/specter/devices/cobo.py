import hashlib
from ..device import Device
from hwilib.serializations import PSBT
from binascii import a2b_base64
from .. import bcur

class Cobo(Device):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        super().__init__(name, alias, 'cobo', keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        # TODO - convert to bc-ur
        raw_psbt = a2b_base64(base64_psbt)
        enc, hsh = bcur.bcur_encode(raw_psbt)
        psbt = ("ur:bytes/%s/%s"% (hsh, enc)).upper()
        psbts = { 'qrcode': psbt }
        return psbts