from .sd_card_device import SDCardDevice
from ..serializations import PSBT


class Specter(SDCardDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        SDCardDevice.__init__(self, name, alias, 'specter', keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = SDCardDevice.create_psbts(self, base64_psbt, wallet)
        qr_psbt = PSBT()
        qr_psbt.deserialize(base64_psbt)
        for inp in qr_psbt.inputs + qr_psbt.outputs:
            inp.witness_script = b""
            inp.redeem_script = b""
            if len(inp.hd_keypaths) > 0:
                k = list(inp.hd_keypaths.keys())[0]
                # proprietary field - wallet derivation path
                # only contains two last derivation indexes - change and index
                inp.unknown[b"\xfc\xca\x01" + wallet.fingerprint] = b"".join([i.to_bytes(4, "little") for i in inp.hd_keypaths[k][-2:]])
                inp.hd_keypaths = {}
        psbts['qrcode'] = qr_psbt.serialize()
        return psbts
