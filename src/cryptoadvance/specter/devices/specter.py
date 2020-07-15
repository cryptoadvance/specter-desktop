import hashlib
from .hwi_device import HWIDevice
from hwilib.serializations import PSBT

class Specter(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        super().__init__(name, alias, 'specter', keys, fullpath, manager)
        self.exportable_to_wallet = True
        self.sd_card_support = False
        self.qr_code_support = True
        self.wallet_export_type = 'qr'
        self.supports_hwi_multisig_display_address = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        qr_psbt = PSBT()
        qr_psbt.deserialize(base64_psbt)
        # replace with compressed wallet information
        for inp in qr_psbt.inputs + qr_psbt.outputs:
            inp.witness_script = b""
            inp.redeem_script = b""
            if len(inp.hd_keypaths) > 0:
                k = list(inp.hd_keypaths.keys())[0]
                # proprietary field - wallet derivation path
                # only contains two last derivation indexes - change and index
                inp.unknown[b"\xfc\xca\x01" + get_wallet_fingerprint(wallet)] = b"".join([i.to_bytes(4, "little") for i in inp.hd_keypaths[k][-2:]])
                inp.hd_keypaths = {}
        psbts['qrcode'] = qr_psbt.serialize()
        return psbts

    def export_wallet(self, wallet):
        return wallet.name + "&" + get_wallet_qr_descriptor(wallet)

def get_wallet_qr_descriptor(wallet):
        return wallet.recv_descriptor.split("#")[0].replace("/0/*", "")

def get_wallet_fingerprint(wallet):
    """ Unique fingerprint of the wallet - first 4 bytes of hash160 of its descriptor """
    h256 = hashlib.sha256(get_wallet_qr_descriptor(wallet).encode()).digest()
    h160 = hashlib.new('ripemd160', h256).digest()
    return h160[:4]
