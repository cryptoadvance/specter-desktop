"""
Blockstream Jade Devices
************************
"""

from .jadepy.jade import JadeAPI, JadeError
from serial.tools import list_ports

from typing import List, Union
from hwilib.descriptor import PubkeyProvider
from hwilib.hwwclient import HardwareWalletClient
from hwilib.errors import (
    ActionCanceledError,
    BadArgumentError,
    DeviceConnectionError,
    DeviceFailureError,
    UnavailableActionError,
    common_err_msgs,
    handle_errors,
)
from hwilib.common import (
    AddressType,
    Chain,
)
from hwilib.key import ExtendedKey, parse_path
from hwilib.psbt import PSBT
from hwilib.tx import CTransaction
from hwilib._script import (
    is_p2sh,
    is_p2wpkh,
    is_p2wsh,
    is_witness,
)

import logging
import os

# embit-related things
from embit import ec, bip32
from embit.psbt import PSBT
from embit import script
from embit.liquid.pset import PSET
from embit import hashes
from embit.util import secp256k1
from embit.liquid.finalizer import finalize_psbt

JADE_VENDOR_ID = 0x10C4
JADE_DEVICE_ID = 0xEA60

py_enumerate = (
    enumerate  # To use the enumerate built-in, since the name is overridden below
)

logger = logging.getLogger(__name__)


def jade_exception(f):
    def func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            raise BadArgumentError(str(e))
        except JadeError as e:
            if e.code == -32000:  # CBOR_RPC_USER_CANCELLED
                raise ActionCanceledError("{} canceled by user".format(f.__name__))
            elif e.code == -32602:  # CBOR_RPC_BAD_PARAMETERS
                raise BadArgumentError(e.message)
            elif e.code == -32603:  # CBOR_RPC_INTERNAL_ERROR
                raise DeviceFailureError(e.message)
            elif e.code == -32002:  # CBOR_RPC_HW_LOCKED
                raise DeviceConnectionError("Device is locked")
            elif e.code == -32003:  # CBOR_RPC_NETWORK_MISMATCH
                raise DeviceConnectionError("Network/chain selection error")
            elif e.code in [
                -32600,
                -32601,
                -32001,
            ]:  # CBOR_RPC_INVALID_REQUEST, CBOR_RPC_UNKNOWN_METHOD, CBOR_RPC_PROTOCOL_ERROR
                raise DeviceConnectionError("Messaging/communiciation error")
            else:
                raise e

    return func


# This class extends the HardwareWalletClient for Blockstream Jade specific things
class JadeClient(HardwareWalletClient):

    NETWORKS = {Chain.MAIN: "mainnet", Chain.TEST: "testnet", Chain.REGTEST: "regtest"}
    liquid_network = None

    def set_liquid_network(self, chain):
        self.liquid_network = "liquid" if chain == "liquidv1" else "localtest-liquid"

    def _network(self):
        if self.liquid_network:
            return self.liquid_network
        return JadeClient.NETWORKS.get(self.chain, "mainnet")

    ADDRTYPES = {
        AddressType.LEGACY: "pkh(k)",
        AddressType.WIT: "wpkh(k)",
        AddressType.SH_WIT: "sh(wpkh(k))",
    }

    @staticmethod
    def _convertAddrType(addrType):
        return JadeClient.ADDRTYPES[addrType]

    def __init__(self, path: str, password: str = "", expert: bool = False) -> None:
        super(JadeClient, self).__init__(path, password, expert)
        self.jade = JadeAPI.create_serial(path)
        self.jade.connect()

        # Push some host entropy into jade
        self.jade.add_entropy(os.urandom(32))

        # Do the PIN thing if required
        # NOTE: uses standard 'requests' networking to connect to blind pinserver
        try:
            while not self.jade.auth_user(self._network()):
                logging.debug("Incorrect PIN provided")
        except:
            try:
                self.chain = Chain.TEST
                while not self.jade.auth_user(self._network()):
                    logging.debug("Incorrect PIN provided")
            except:
                self.chain = Chain.REGTEST
                while not self.jade.auth_user(self._network()):
                    logging.debug("Incorrect PIN provided")

    # Retrieves the public key at the specified BIP 32 derivation path
    @jade_exception
    def get_pubkey_at_path(self, bip32_path: str) -> ExtendedKey:
        path = parse_path(bip32_path)
        xpub = self.jade.get_xpub(self._network(), path)
        ext_key = ExtendedKey.deserialize(xpub)
        return ext_key

    @jade_exception
    def get_master_blinding_key(self) -> str:
        mbk = self.jade.get_master_blinding_key()
        assert len(mbk) == 32
        bkey = ec.PrivateKey(mbk)
        return bkey.wif()

    # Walk the PSBT looking for inputs we can sign.  Push any signatures into the
    # 'partial_sigs' map in the input, and return the updated PSBT.
    @jade_exception
    def sign_tx(self, tx: PSBT) -> PSBT:
        """
        Sign a transaction with the Blockstream Jade.

        - Jade can only be used to sign single-key inputs at this time.   It cannot sign multisig or arbitrary scripts.
        """

        c_txn = CTransaction(tx.tx)
        master_fp = self.get_master_fingerprint()
        signing_pubkeys = [None] * len(tx.inputs)

        # Signing input details
        jade_inputs = []
        for n_vin, (txin, psbtin) in py_enumerate(zip(c_txn.vin, tx.inputs)):
            # Get bip32 path to use to sign, if required for this input
            path = None
            for pubkey, origin in psbtin.hd_keypaths.items():
                if origin.fingerprint == master_fp and len(origin.path) > 0:
                    # Our input
                    if (
                        pubkey not in psbtin.partial_sigs
                        or not psbtin.partial_sigs[pubkey]
                    ):
                        # hw to sign this input - it is not already signed
                        signing_pubkeys[n_vin] = pubkey
                        path = origin.path

            # Get the tx and prevout/scriptcode
            utxo = None
            input_txn_bytes = None
            if psbtin.witness_utxo:
                utxo = psbtin.witness_utxo
            if psbtin.non_witness_utxo:
                if txin.prevout.hash != psbtin.non_witness_utxo.sha256:
                    raise BadArgumentError(
                        "Input {} has a non_witness_utxo with the wrong hash".format(
                            n_vin
                        )
                    )
                utxo = psbtin.non_witness_utxo.vout[txin.prevout.n]
                input_txn_bytes = psbtin.non_witness_utxo.serialize_without_witness()

            scriptcode = utxo.scriptPubKey

            if is_p2sh(scriptcode):
                scriptcode = psbtin.redeem_script

            witness_input, witness_version, witness_program = is_witness(scriptcode)

            if witness_input:
                if is_p2wsh(scriptcode):
                    scriptcode = psbtin.witness_script
                elif is_p2wpkh(scriptcode):
                    scriptcode = b"\x76\xa9\x14" + witness_program + b"\x88\xac"
                else:
                    scriptcode = None

            # Build the input and add to the list
            jade_inputs.append(
                {
                    "is_witness": witness_input,
                    "input_tx": input_txn_bytes,
                    "script": scriptcode,
                    "path": path,
                }
            )

        # Change output details
        # This is optional, in that if we send it Jade validates the change output script
        # and the user need not confirm that ouptut.  If not passed the change output must
        # be confirmed by the user on the hwwallet screen, like any other spend output.
        change = [None] * len(tx.outputs)
        for n_vout, (txout, psbtout) in py_enumerate(zip(c_txn.vout, tx.outputs)):
            for pubkey, origin in psbtout.hd_keypaths.items():
                # Considers 'our' outputs as change as far as Jade is concerned
                # ie. can be auto-confirmed.
                # Is this ok, or should check path also, assuming bip44-like ?
                if origin.fingerprint == master_fp and len(origin.path) > 0:
                    addr_type = None
                    if txout.is_p2pkh():
                        addr_type = AddressType.LEGACY
                    elif txout.is_witness()[0] and not txout.is_p2wsh():
                        addr_type = AddressType.WIT
                    elif txout.is_p2sh():
                        addr_type = AddressType.SH_WIT  # is it really though ?

                    if addr_type:
                        addr_type = self._convertAddrType(addr_type)
                        change[n_vout] = {"path": origin.path, "variant": addr_type}

        # The txn itself
        txn_bytes = c_txn.serialize_without_witness()

        # Request Jade generate the signatures for our inputs.
        # Change details are passed to be validated on the hw (user does not confirm)
        signatures = self.jade.sign_tx(self._network(), txn_bytes, jade_inputs, change)

        # Push sigs into PSBT structure as appropriate
        for psbtin, pubkey, sig in zip(tx.inputs, signing_pubkeys, signatures):
            if pubkey and sig:
                psbtin.partial_sigs[pubkey] = sig

        # Return the updated psbt
        return tx

    # Sign message, confirmed on device
    @jade_exception
    def sign_message(self, message: Union[str, bytes], bip32_path: str) -> str:
        path = parse_path(bip32_path)
        if isinstance(message, bytes) or isinstance(message, bytearray):
            message = message.decode("utf-8")
        signature = self.jade.sign_message(path, message)
        return signature

    # Display address of specified type on the device. Only supports single-key based addresses atm.
    @jade_exception
    def display_singlesig_address(self, bip32_path: str, addr_type: AddressType) -> str:
        path = parse_path(bip32_path)
        addr_type = self._convertAddrType(addr_type)
        address = self.jade.get_receive_address(
            self._network(), path, variant=addr_type
        )
        return address

    def display_multisig_address(
        self, threshold: int, pubkeys: List[PubkeyProvider], addr_type: AddressType
    ) -> str:
        """
        The Blockstream Jade does not support multisig addresses.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support generic multisig P2SH address display"
        )

    # Setup a new device
    def setup_device(self, label="", passphrase=""):
        """
        The Blockstream Jade does not support setup via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support software setup"
        )

    # Wipe this device
    def wipe_device(self):
        """
        The Blockstream Jade does not support wiping via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support wiping via software"
        )

    # Restore device from mnemonic or xprv
    def restore_device(self, label="", word_count=24):
        """
        The Blockstream Jade does not support restoring via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support restoring via software"
        )

    # Begin backup process
    def backup_device(self, label="", passphrase=""):
        """
        The Blockstream Jade does not support backing up via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support creating a backup via software"
        )

    # Close the device
    def close(self):
        self.jade.disconnect()

    # Prompt pin
    def prompt_pin(self):
        """
        The Blockstream Jade does not need a PIN sent from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not need a PIN sent from the host"
        )

    # Send pin
    def send_pin(self, pin):
        """
        The Blockstream Jade does not need a PIN sent from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not need a PIN sent from the host"
        )

    # Toggle passphrase
    def toggle_passphrase(self):
        """
        The Blockstream Jade does not support toggling passphrase from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The Blockstream Jade does not support toggling passphrase from the host"
        )

    def _blind(self, pset, seed: bytes = None):
        if seed is None:
            seed = pset.unknown.get(b"\xfc\x07specter\x00", os.urandom(32))
        txseed = pset.txseed(seed)
        # assign blinding factors to all outputs
        blinding_outs = []
        commitments = []
        # because we do sha once (cause taproot), and they want sha twice
        hash_prevouts = hashes.sha256(pset.blinded_tx.hash_prevouts())
        last_i = 0
        last_commitment = {}
        for i, out in py_enumerate(pset.outputs):
            # skip ones where we don't need blinding
            if out.blinding_pubkey is None:
                commitments.append(None)
                continue
            commitment = self.jade.get_commitments(
                bytes(reversed(out.asset)), out.value, hash_prevouts, i, vbf=None
            )
            commitment["blinding_key"] = out.blinding_pubkey
            commitments.append(commitment)
            last_i = i
            last_commitment = commitments[-1]
            out.asset_blinding_factor = commitment["abf"]
            out.value_blinding_factor = commitment["vbf"]
            blinding_outs.append(out)
        if len(blinding_outs) == 0:
            raise Exception("Nothing to blind")
        # calculate last vbf
        vals = [sc.value for sc in pset.inputs + blinding_outs]
        abfs = [
            sc.asset_blinding_factor or b"\x00" * 32
            for sc in pset.inputs + blinding_outs
        ]
        vbfs = [
            sc.value_blinding_factor or b"\x00" * 32
            for sc in pset.inputs + blinding_outs
        ]
        last_vbf = secp256k1.pedersen_blind_generator_blind_sum(
            vals, abfs, vbfs, len(pset.inputs)
        )
        last_out = blinding_outs[-1]
        new_last_commitment = self.jade.get_commitments(
            bytes(reversed(last_out.asset)),
            last_out.value,
            hash_prevouts,
            last_i,
            vbf=last_vbf,
        )
        # check abf didn't change
        assert new_last_commitment["abf"] == last_out.asset_blinding_factor
        # set new values in the last commitment
        last_commitment.update(new_last_commitment)
        blinding_outs[-1].value_blinding_factor = last_vbf

        # calculate commitments (surj proof etc)

        in_tags = [inp.asset for inp in pset.inputs]
        in_gens = [secp256k1.generator_parse(inp.utxo.asset) for inp in pset.inputs]

        for i, out in py_enumerate(pset.outputs):
            if out.blinding_pubkey is None:
                continue
            gen = secp256k1.generator_generate_blinded(
                out.asset, out.asset_blinding_factor
            )
            out.asset_commitment = secp256k1.generator_serialize(gen)
            value_commitment = secp256k1.pedersen_commit(
                out.value_blinding_factor, out.value, gen
            )
            out.value_commitment = secp256k1.pedersen_commitment_serialize(
                value_commitment
            )

            proof_seed = hashes.tagged_hash(
                "liquid/surjection_proof", txseed + i.to_bytes(4, "little")
            )
            proof, in_idx = secp256k1.surjectionproof_initialize(
                in_tags, out.asset, proof_seed
            )
            secp256k1.surjectionproof_generate(
                proof,
                in_idx,
                in_gens,
                gen,
                pset.inputs[in_idx].asset_blinding_factor,
                out.asset_blinding_factor,
            )
            out.surjection_proof = secp256k1.surjectionproof_serialize(proof)
            del proof

            # generate range proof
            rangeproof_nonce = hashes.tagged_hash(
                "liquid/range_proof", txseed + i.to_bytes(4, "little")
            )
            # reblind with extra message for unblinding
            out.reblind(
                rangeproof_nonce,
                extra_message=out.unknown.get(b"\xfc\x07specter\x01", b""),
            )

        return commitments

    def sign_pset(self, b64pset: str) -> str:
        """Signs specter-desktop specific Liquid PSET transaction"""
        mfp = self.get_master_fingerprint()
        pset = PSET.from_string(b64pset)
        commitments = self._blind(pset)

        ins = [
            {
                "is_witness": True,
                # "input_tx": inp.non_witness_utxo.serialize(),
                "script": inp.witness_script.data
                if inp.witness_script
                else script.p2pkh_from_p2wpkh(inp.script_pubkey).data,
                "value_commitment": inp.witness_utxo.value,
                "path": [
                    der
                    for der in inp.bip32_derivations.values()
                    if der.fingerprint == mfp
                ][0].derivation,
            }
            for inp in pset.inputs
        ]
        change = [
            {
                "path": [
                    der
                    for pub, der in out.bip32_derivations.items()
                    if der.fingerprint == mfp
                ][0].derivation,
                "variant": self._get_script_type(out),
            }
            if out.bip32_derivations and self._get_script_type(out) is not None
            else None
            for out in pset.outputs
        ]
        rawtx = pset.blinded_tx.serialize()

        signatures = self.jade.sign_liquid_tx(
            self._network(), rawtx, ins, commitments, change
        )
        for i, inp in py_enumerate(pset.inputs):
            inp.partial_sigs[
                [
                    pub
                    for pub, der in inp.bip32_derivations.items()
                    if der.fingerprint == mfp
                ][0]
            ] = signatures[i]
        # we must finalize here because it has different commitments and only supports singlesig
        return str(finalize_psbt(pset))

    def _get_script_type(self, out):
        if out.script_pubkey.script_type() == "p2pkh":
            return "pkh(k)"
        elif out.script_pubkey.script_type() == "p2wpkh":
            return "wpkh(k)"
        elif out.script_pubkey.script_type() == "p2sh":
            if out.redeem_script.script_type() == "p2wpkh":
                return "sh(wpkh(k))"
        # otherwise None
        return None


def enumerate(password=""):
    results = []

    # Jade is not really an HID device, it shows as a serial/com port device.
    # Scan com ports looking for the relevant vid and pid, and use 'path' to
    # hold the path to the serial port device, eg. /dev/ttyUSB0
    for devinfo in list_ports.comports():
        if devinfo.vid == JADE_VENDOR_ID and devinfo.pid == JADE_DEVICE_ID:
            d_data = {}
            d_data["type"] = "jade"
            d_data["path"] = devinfo.device
            d_data["needs_pin_sent"] = False
            d_data["needs_passphrase_sent"] = False

            client = None
            with handle_errors(common_err_msgs["enumerate"], d_data):
                client = JadeClient(devinfo.device, password)
                d_data["fingerprint"] = client.get_master_fingerprint().hex()

            if client:
                client.close()

            results.append(d_data)

    return results
