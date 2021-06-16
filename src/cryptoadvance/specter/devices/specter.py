import hashlib
from . import DeviceTypes
from .sd_card_device import SDCardDevice
from .hwi.specter_diy import enumerate as specter_enumerate, SpecterClient
from ..helpers import to_ascii20
from embit import bip32
from embit.psbt import PSBT
from embit.liquid.pset import PSET
from embit.liquid.transaction import LSIGHASH
from binascii import a2b_base64, b2a_base64


class Specter(SDCardDevice):
    device_type = DeviceTypes.SPECTERDIY
    name = "Specter-DIY"
    icon = "specter_icon.svg"

    exportable_to_wallet = True
    sd_card_support = True
    qr_code_support = True
    qr_code_support_verify = True
    wallet_export_type = "qr"
    supports_hwi_multisig_display_address = True
    liquid_support = True

    def create_psbts(self, base64_psbt, wallet):
        try:
            # remove rangeproofs and add sighash alls
            psbt = PSET.from_string(base64_psbt)
            for out in psbt.outputs:
                out.range_proof = None
                out.surjection_proof = None
            for inp in psbt.inputs:
                if not inp.sighash_type:
                    inp.sighash_type = LSIGHASH.ALL
            base64_psbt = psbt.to_string()
        except:
            pass
        psbts = super().create_psbts(base64_psbt, wallet)
        # remove non-witness utxo if they are there to reduce QR code size
        updated_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        try:
            qr_psbt = PSBT.from_string(updated_psbt)
        except:
            qr_psbt = PSET.from_string(updated_psbt)
        # find my key
        fgp = None
        derivation = None
        for k in wallet.keys:
            if k in self.keys and k.fingerprint and k.derivation:
                fgp = bytes.fromhex(k.fingerprint)
                derivation = bip32.parse_path(k.derivation)
                break
        # remove unnecessary derivations from inputs and outputs
        for inp in qr_psbt.inputs + qr_psbt.outputs:
            # keep only my derivation
            for k in list(inp.bip32_derivations.keys()):
                if fgp and inp.bip32_derivations[k].fingerprint != fgp:
                    inp.bip32_derivations.pop(k, None)
        # remove scripts from outputs (DIY should know about the wallet)
        for out in qr_psbt.outputs:
            out.witness_script = None
            out.redeem_script = None
        # remove partial sigs from inputs
        for inp in qr_psbt.inputs:
            inp.partial_sigs = {}
        psbts["qrcode"] = qr_psbt.to_string()

        # we can add xpubs to SD card, but non_witness can be too large for MCU
        psbts["sdcard"] = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=True)
        return psbts

    def export_wallet(self, wallet):
        return (
            "addwallet "
            + to_ascii20(wallet.name)
            + "&"
            + get_wallet_qr_descriptor(wallet)
        )

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return specter_enumerate(*args, **kwargs)

    @classmethod
    def get_client(cls, *args, **kwargs):
        return SpecterClient(*args, **kwargs)


def get_wallet_qr_descriptor(wallet):
    return wallet.recv_descriptor.split("#")[0].replace("/0/*", "")


def get_wallet_fingerprint(wallet):
    """
    Unique fingerprint of the wallet -
    first 4 bytes of hash160 of its descriptor
    """
    h256 = hashlib.sha256(get_wallet_qr_descriptor(wallet).encode()).digest()
    h160 = hashlib.new("ripemd160", h256).digest()
    return h160[:4]
