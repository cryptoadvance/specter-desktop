import hashlib
from . import DeviceTypes
from .sd_card_device import SDCardDevice
from .hwi.specter_diy import enumerate as specter_enumerate, SpecterClient
from ..helpers import to_ascii20
from embit import bip32
from embit.psbt import PSBT, DerivationPath
from embit.liquid.pset import PSET
from embit.liquid.transaction import LSIGHASH
from binascii import a2b_base64, b2a_base64
from embit.liquid.networks import get_network
from embit.hashes import hash160
import logging

logger = logging.getLogger(__name__)


def fill_external_wallet_derivations(psbt, wallet):
    # fill derivations for receiving wallets if they own address
    net = get_network(wallet.manager.chain)
    wallets = wallet.manager.wallets.values()
    for out in psbt.outputs:
        try:  # if we fail - not a big deal
            # check if output derivation is empty
            if out.bip32_derivations:
                continue
            try:
                # if there is no address representation - continue
                addr = out.script_pubkey.address(net)
            except:
                continue
            for w in wallets:
                # skip sending wallet
                if w == wallet:
                    continue
                if not w.is_address_mine(addr):
                    continue
                # we get here if wallet owns address
                info = w.get_address_info(addr)
                derivation = [int(info.change), int(info.index)]
                # we first one key and build derivation for it
                # it's enough for DIY to do the res
                k = w.keys[0]
                key = bip32.HDKey.from_string(k.xpub)
                if k.fingerprint != "":
                    fingerprint = bytes.fromhex(k.fingerprint)
                else:
                    fingerprint = key.my_fingerprint
                if k.derivation != "":
                    der = bip32.parse_path(k.derivation)
                else:
                    der = []
                pub = key.derive(derivation).key
                out.bip32_derivations[pub] = DerivationPath(
                    fingerprint, der + derivation
                )
                break
        except Exception as e:
            logger.exception(e)


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
    taproot_support = True

    def create_psbts(self, base64_psbt, wallet):
        # liquid transaction
        if base64_psbt.startswith("cHNl"):
            # remove rangeproofs and add sighash alls
            psbt = PSET.from_string(base64_psbt)
            # make sure we have tx blinding seed in the transaction
            if psbt.unknown.get(b"\xfc\x07specter\x00"):
                for out in psbt.outputs:
                    out.range_proof = None
                    # out.surjection_proof = None
                    # we know assets - we can blind it
                    if out.asset:
                        out.asset_commitment = None
                        out.asset_blinding_factor = None
                    # we know value - we can blind it
                    if out.value:
                        out.value_commitment = None
                        out.value_blinding_factor = None
                for inp in psbt.inputs:
                    if inp.value and inp.asset:
                        inp.range_proof = None
        else:
            psbt = PSBT.from_string(base64_psbt)

        fill_external_wallet_derivations(psbt, wallet)

        base64_psbt = psbt.to_string()
        psbts = super().create_psbts(base64_psbt, wallet)
        # remove non-witness utxo if they are there to reduce QR code size
        updated_psbt = wallet.fill_psbt(
            base64_psbt, non_witness=False, xpubs=False, taproot_derivations=True
        )
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
            # keep only one derivation path (idealy ours)
            found = False
            pubkeys = list(inp.bip32_derivations.keys())
            for i, pub in enumerate(pubkeys):
                if fgp and inp.bip32_derivations[pub].fingerprint != fgp:
                    # only pop if we already saw our derivation
                    # or if it's not the last one
                    if found or i < len(pubkeys) - 1:
                        inp.bip32_derivations.pop(k, None)
                else:
                    found = True
        # remove scripts from outputs (DIY should know about the wallet)
        for out in qr_psbt.outputs:
            out.witness_script = None
            out.redeem_script = None
        # remove partial sigs from inputs
        for inp in qr_psbt.inputs:
            inp.partial_sigs = {}
        psbts["qrcode"] = qr_psbt.to_string()

        # we can add xpubs to SD card, but non_witness can be too large for MCU
        psbts["sdcard"] = wallet.fill_psbt(
            base64_psbt, non_witness=False, xpubs=True, taproot_derivations=True
        )
        psbts["hwi"] = wallet.fill_psbt(
            base64_psbt, non_witness=False, xpubs=True, taproot_derivations=True
        )
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
    h160 = hash160(get_wallet_qr_descriptor(wallet).encode())
    return h160[:4]
