"""
Blockstream Jade Devices
************************
"""

from .jadepy import jade
from .jadepy.jade import JadeAPI, JadeError
from serial.tools import list_ports

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from hwilib.descriptor import PubkeyProvider, MultisigDescriptor
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
from hwilib.key import ExtendedKey, parse_path, KeyOriginInfo, is_hardened
from hwilib.psbt import PSBT
from hwilib.tx import CTransaction
from hwilib._script import (
    is_p2sh,
    is_p2wpkh,
    is_p2wsh,
    is_witness,
    parse_multisig,
)

import logging
import os
import hashlib

# embit-related things
from embit import ec, bip32
from embit.psbt import PSBT
from embit import script
from embit.liquid.pset import PSET
from embit import hashes
from embit.util import secp256k1
from embit.liquid.finalizer import finalize_psbt
from embit.liquid.transaction import write_commitment

# The test emulator port
SIMULATOR_PATH = "tcp:127.0.0.1:2222"

JADE_DEVICE_IDS = [(0x10C4, 0xEA60), (0x1A86, 0x55D4)]
HAS_NETWORKING = hasattr(jade, "_http_request")

py_enumerate = (
    enumerate  # To use the enumerate built-in, since the name is overridden below
)

logger = logging.getLogger(__name__)


def jade_exception(f: Callable[..., Any]) -> Any:
    @wraps(f)
    def func(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            raise BadArgumentError(str(e))
        except JadeError as e:
            if e.code == JadeError.USER_CANCELLED:
                raise ActionCanceledError(f"{f.__name__} canceled by user")
            elif e.code == JadeError.BAD_PARAMETERS:
                raise BadArgumentError(e.message)
            elif e.code == JadeError.INTERNAL_ERROR:
                raise DeviceFailureError(e.message)
            elif e.code == JadeError.HW_LOCKED:
                raise DeviceConnectionError("Device is locked")
            elif e.code == JadeError.NETWORK_MISMATCH:
                raise DeviceConnectionError("Network/chain selection error")
            elif e.code in [
                JadeError.INVALID_REQUEST,
                JadeError.UNKNOWN_METHOD,
                JadeError.PROTOCOL_ERROR,
            ]:
                raise DeviceConnectionError("Messaging/communiciation error")
            else:
                raise e

    return func


# This class extends the HardwareWalletClient for Blockstream Jade specific things
class JadeClient(HardwareWalletClient):

    NETWORKS = {
        Chain.MAIN: "mainnet",
        Chain.TEST: "testnet",
        Chain.REGTEST: "localtest",
    }
    liquid_network = None

    def set_liquid_network(self, chain):
        if chain == "liquidv1":
            self.liquid_network = "liquid"
        elif chain == "liquidtestnet":
            self.liquid_network = "testnet-liquid"
        else:
            self.liquid_network = "localtest-liquid"

    def _network(self):
        if self.liquid_network:
            return self.liquid_network
        return JadeClient.NETWORKS.get(self.chain, "mainnet")

    ADDRTYPES = {
        AddressType.LEGACY: "pkh(k)",
        AddressType.WIT: "wpkh(k)",
        AddressType.SH_WIT: "sh(wpkh(k))",
    }
    MULTI_ADDRTYPES = {
        AddressType.LEGACY: "sh(multi(k))",
        AddressType.WIT: "wsh(multi(k))",
        AddressType.SH_WIT: "sh(wsh(multi(k)))",
    }

    @staticmethod
    def _convertAddrType(addrType, multisig=False):
        if multisig:
            return JadeClient.MULTI_ADDRTYPES[addrType]
        return JadeClient.ADDRTYPES[addrType]

    @staticmethod
    def _get_multisig_name(
        type: str, threshold: int, signers: List[Tuple[bytes, Sequence[int]]]
    ) -> str:
        # Concatenate script-type, threshold, and all signers fingerprints and derivation paths (sorted)
        summary = type + "|" + str(threshold) + "|"
        for fingerprint, path in sorted(signers):
            summary += fingerprint.hex() + "|" + str(path) + "|"

        # Hash it, get the first 6-bytes as hex, prepend with 'hwi'
        hash_summary = hashlib.sha256(summary.encode()).digest().hex()
        return "hwi" + hash_summary[:12]

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
        """
        # Helper to get multisig record for change output
        def _parse_signers(
            hd_keypath_origins: List[KeyOriginInfo],
        ) -> Tuple[List[Tuple[bytes, Sequence[int]]], List[Sequence[int]]]:
            # Split the path at the last hardened path element
            def _split_at_last_hardened_element(
                path: Sequence[int],
            ) -> Tuple[Sequence[int], Sequence[int]]:
                for i in range(len(path), 0, -1):
                    if is_hardened(path[i - 1]):
                        return (path[:i], path[i:])
                return ([], path)

            signers = []
            paths = []
            for origin in hd_keypath_origins:
                prefix, suffix = _split_at_last_hardened_element(origin.path)
                signers.append((origin.fingerprint, prefix))
                paths.append(suffix)
            # sort signers and paths like in multisig registration
            signers, paths = [list(a) for a in zip(*sorted(zip(signers, paths)))]

            return signers, paths

        c_txn = CTransaction(tx.tx)
        master_fp = self.get_master_fingerprint()
        signing_singlesigs = False
        signing_multisigs = {}
        need_to_sign = True

        while need_to_sign:
            signing_pubkeys: List[Optional[bytes]] = [None] * len(tx.inputs)
            need_to_sign = False

            # Signing input details
            jade_inputs = []
            for n_vin, (txin, psbtin) in py_enumerate(zip(c_txn.vin, tx.inputs)):
                # Get bip32 path to use to sign, if required for this input
                path = None
                multisig_input = len(psbtin.hd_keypaths) > 1
                for pubkey, origin in psbtin.hd_keypaths.items():
                    if origin.fingerprint == master_fp and len(origin.path) > 0:
                        if not multisig_input:
                            signing_singlesigs = True

                        if psbtin.partial_sigs.get(pubkey, None) is None:
                            # hw to sign this input - it is not already signed
                            if signing_pubkeys[n_vin] is None:
                                signing_pubkeys[n_vin] = pubkey
                                path = origin.path
                            else:
                                # Additional signature needed for this input - ie. a multisig where this wallet is
                                # multiple signers?  Clumsy, but just loop and go through the signing procedure again.
                                need_to_sign = True

                # Get the tx and prevout/scriptcode
                utxo = None
                p2sh = False
                input_txn_bytes = None
                if psbtin.witness_utxo:
                    utxo = psbtin.witness_utxo
                if psbtin.non_witness_utxo:
                    utxo = psbtin.non_witness_utxo.vout[txin.prevout.n]
                    input_txn_bytes = (
                        psbtin.non_witness_utxo.serialize_without_witness()
                    )
                if utxo is None:
                    raise Exception(
                        "PSBT is missing input utxo information, cannot sign"
                    )
                scriptcode = utxo.scriptPubKey

                if is_p2sh(scriptcode):
                    scriptcode = psbtin.redeem_script
                    p2sh = True

                witness_input, witness_version, witness_program = is_witness(scriptcode)

                if witness_input:
                    if is_p2wsh(scriptcode):
                        scriptcode = psbtin.witness_script
                    elif is_p2wpkh(scriptcode):
                        scriptcode = b"\x76\xa9\x14" + witness_program + b"\x88\xac"
                    else:
                        continue

                # If we are signing a multisig input, deduce the potential
                # registration details and cache as a potential change wallet
                if multisig_input and path and scriptcode and (p2sh or witness_input):
                    parsed = parse_multisig(scriptcode)
                    if parsed:
                        addr_type = (
                            AddressType.LEGACY
                            if not witness_input
                            else AddressType.WIT
                            if not p2sh
                            else AddressType.SH_WIT
                        )
                        script_variant = self._convertAddrType(addr_type, multisig=True)
                        threshold = parsed[0]

                        pubkeys = parsed[1]
                        hd_keypath_origins = [
                            psbtin.hd_keypaths[pubkey] for pubkey in pubkeys
                        ]

                        signers, paths = _parse_signers(hd_keypath_origins)

                        multisig_name = self._get_multisig_name(
                            script_variant, threshold, signers
                        )
                        signing_multisigs[multisig_name] = (
                            script_variant,
                            threshold,
                            signers,
                        )

                # Build the input and add to the list - include some host entropy for AE sigs (although we won't verify)
                jade_inputs.append(
                    {
                        "is_witness": witness_input,
                        "input_tx": input_txn_bytes,
                        "script": scriptcode,
                        "path": path,
                        "ae_host_entropy": os.urandom(32),
                        "ae_host_commitment": os.urandom(32),
                    }
                )

            # Change output details
            # This is optional, in that if we send it Jade validates the change output script
            # and the user need not confirm that ouptut.  If not passed the change output must
            # be confirmed by the user on the hwwallet screen, like any other spend output.
            change: List[Optional[Dict[str, Any]]] = [None] * len(tx.outputs)

            # If signing multisig inputs, get registered multisigs details in case we
            # see any multisig outputs which may be change which we can auto-validate.
            # ie. filter speculative 'signing multisigs' to ones actually registered on the hw
            candidate_multisigs = {}

            if signing_multisigs:
                # register multisig if xpubs are known
                if tx.xpub and len(signing_multisigs) == 1:
                    msigname = list(signing_multisigs.keys())[0]
                    signers = []
                    origins = []
                    for xpub in tx.xpub:
                        hd = bip32.HDKey.parse(xpub)
                        origin = tx.xpub[xpub]
                        origins.append((origin.fingerprint, origin.path))

                        signers.append(
                            {
                                "fingerprint": origin.fingerprint,
                                "derivation": origin.path,
                                "xpub": str(hd),
                                "path": [],
                            }
                        )

                    # sort origins and signers together
                    origins, signers = [
                        list(a) for a in zip(*sorted(zip(origins, signers)))
                    ]

                    # Get a deterministic name for this multisig wallet
                    script_variant = signing_multisigs[msigname][0]
                    thresh = signing_multisigs[msigname][1]
                    num_signers = signing_multisigs[msigname][2]
                    multisig_name = self._get_multisig_name(
                        script_variant, thresh, origins
                    )
                    # stupid sanity check of the fingerprints and origins
                    if multisig_name == msigname:
                        # Need to ensure this multisig wallet is registered first
                        # (Note: 're-registering' is a no-op)
                        self.jade.register_multisig(
                            self._network(),
                            multisig_name,
                            script_variant,
                            True,  # always use sorted
                            thresh,
                            signers,
                        )
                #
                registered_multisigs = self.jade.get_registered_multisigs()
                signing_multisigs = {
                    k: v
                    for k, v in signing_multisigs.items()
                    if k in registered_multisigs
                    and registered_multisigs[k]["variant"] == v[0]
                    and registered_multisigs[k]["threshold"] == v[1]
                    and registered_multisigs[k]["num_signers"] == len(v[2])
                }

            # Look at every output...
            for n_vout, (txout, psbtout) in py_enumerate(zip(c_txn.vout, tx.outputs)):
                num_signers = len(psbtout.hd_keypaths)

                if num_signers == 1 and signing_singlesigs:
                    # Single-sig output - since we signed singlesig inputs this could be our change
                    for pubkey, origin in psbtout.hd_keypaths.items():
                        # Considers 'our' outputs as potential change as far as Jade is concerned
                        # ie. can be verified and auto-confirmed.
                        # Is this ok, or should check path also, assuming bip44-like ?
                        if origin.fingerprint == master_fp and len(origin.path) > 0:
                            change_addr_type = None
                            if txout.is_p2pkh():
                                change_addr_type = AddressType.LEGACY
                            elif txout.is_witness()[0] and not txout.is_p2wsh():
                                change_addr_type = AddressType.WIT  # ie. p2wpkh
                            elif (
                                txout.is_p2sh() and is_witness(psbtout.redeem_script)[0]
                            ):
                                change_addr_type = AddressType.SH_WIT
                            else:
                                continue

                            script_variant = self._convertAddrType(
                                change_addr_type, multisig=False
                            )
                            change[n_vout] = {
                                "path": origin.path,
                                "variant": script_variant,
                            }

                elif num_signers > 1 and signing_multisigs:
                    # Multisig output - since we signed multisig inputs this could be our change
                    candidate_multisigs = {
                        k: v
                        for k, v in signing_multisigs.items()
                        if len(v[2]) == num_signers
                    }
                    if not candidate_multisigs:
                        continue

                    for pubkey, origin in psbtout.hd_keypaths.items():
                        if origin.fingerprint == master_fp and len(origin.path) > 0:
                            change_addr_type = None
                            if (
                                txout.is_p2sh()
                                and not is_witness(psbtout.redeem_script)[0]
                            ):
                                change_addr_type = AddressType.LEGACY
                                scriptcode = psbtout.redeem_script
                            elif txout.is_p2wsh() and not txout.is_p2sh():
                                change_addr_type = AddressType.WIT
                                scriptcode = psbtout.witness_script
                            elif (
                                txout.is_p2sh() and is_witness(psbtout.redeem_script)[0]
                            ):
                                change_addr_type = AddressType.SH_WIT
                                scriptcode = psbtout.witness_script
                            else:
                                continue

                            parsed = parse_multisig(scriptcode)
                            if parsed:
                                script_variant = self._convertAddrType(
                                    change_addr_type, multisig=True
                                )
                                threshold = parsed[0]

                                pubkeys = parsed[1]
                                hd_keypath_origins = [
                                    psbtout.hd_keypaths[pubkey] for pubkey in pubkeys
                                ]

                                signers, paths = _parse_signers(hd_keypath_origins)

                                multisig_name = self._get_multisig_name(
                                    script_variant, threshold, signers
                                )

                                matched_multisig = candidate_multisigs.get(
                                    multisig_name
                                ) == (script_variant, threshold, signers)
                                if matched_multisig:
                                    change[n_vout] = {
                                        "paths": paths,
                                        "multisig_name": multisig_name,
                                    }

            # The txn itself
            txn_bytes = c_txn.serialize_without_witness()

            # Request Jade generate the signatures for our inputs.
            # Change details are passed to be validated on the hw (user does not confirm)
            signatures = self.jade.sign_tx(
                self._network(), txn_bytes, jade_inputs, change, True
            )

            # Push sigs into PSBT structure as appropriate
            for psbtin, signer_pubkey, sigdata in zip(
                tx.inputs, signing_pubkeys, signatures
            ):
                signer_commitment, sig = sigdata
                if signer_pubkey and sig:
                    psbtin.partial_sigs[signer_pubkey] = sig

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
        self,
        addr_type: AddressType,
        multisig: MultisigDescriptor,
    ) -> str:
        signer_origins = []
        signers = []
        paths = []
        for pubkey in multisig.pubkeys:
            if pubkey.extkey is None:
                raise BadArgumentError(
                    "Blockstream Jade can only generate addresses for multisigs with full extended keys"
                )
            if pubkey.origin is None:
                raise BadArgumentError(
                    "Blockstream Jade can only generate addresses for multisigs with key origin information"
                )
            if pubkey.deriv_path is None:
                raise BadArgumentError(
                    "Blockstream Jade can only generate addresses for multisigs with key origin derivation path information"
                )

            # Tuple to derive deterministic name for the registrtion
            signer_origins.append((pubkey.origin.fingerprint, pubkey.origin.path))

            #  We won't include the additional path in the multisig registration
            signers.append(
                {
                    "fingerprint": pubkey.origin.fingerprint,
                    "derivation": pubkey.origin.path,
                    "xpub": pubkey.pubkey,
                    "path": [],
                }
            )

            # Instead hold it as the address path
            path = (
                pubkey.deriv_path[1:]
                if pubkey.deriv_path[0] == "/"
                else pubkey.deriv_path
            )
            paths.append(parse_path(path))

        # sort origins, signers and paths according to origins (like in _get_multisig_name)
        signer_origins, signers, paths = [
            list(a) for a in zip(*sorted(zip(signer_origins, signers, paths)))
        ]

        # Get a deterministic name for this multisig wallet
        script_variant = self._convertAddrType(addr_type, multisig=True)
        multisig_name = self._get_multisig_name(
            script_variant, multisig.thresh, signer_origins
        )

        # Need to ensure this multisig wallet is registered first
        # (Note: 're-registering' is a no-op)
        self.jade.register_multisig(
            self._network(),
            multisig_name,
            script_variant,
            True,  # always use sorted
            multisig.thresh,
            signers,
        )
        address = self.jade.get_receive_address(
            self._network(), paths, multisig_name=multisig_name
        )

        return str(address)

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
        vals = []
        abfs = []
        vbfs = []
        for sc in pset.inputs + blinding_outs:
            value = sc.value if sc.value is not None else sc.utxo.value
            asset = sc.asset or sc.utxo.asset
            if not (isinstance(value, int) and len(asset) == 32):
                continue
            vals.append(value)
            abfs.append(sc.asset_blinding_factor or b"\x00" * 32)
            vbfs.append(sc.value_blinding_factor or b"\x00" * 32)
        last_vbf = secp256k1.pedersen_blind_generator_blind_sum(
            vals, abfs, vbfs, len(vals) - len(blinding_outs)
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
        in_tags = []
        in_gens = []
        for inp in pset.inputs:
            if inp.asset:
                in_tags.append(inp.asset)
                in_gens.append(secp256k1.generator_parse(inp.utxo.asset))
            # if we have unconfidential input
            elif len(inp.utxo.asset) == 32:
                in_tags.append(inp.utxo.asset)
                in_gens.append(secp256k1.generator_generate(inp.utxo.asset))

        for i, out in py_enumerate(pset.outputs):
            if None in [out.blinding_pubkey, out.value, out.asset_blinding_factor]:
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
                proof, in_idx, in_gens, gen, abfs[in_idx], out.asset_blinding_factor
            )
            out.surjection_proof = secp256k1.surjectionproof_serialize(proof)
            del proof

            # generate range proof
            rangeproof_nonce = hashes.tagged_hash(
                "liquid/range_proof", txseed + i.to_bytes(4, "little")
            )
            # reblind with extra message for unblinding of change outs
            extra_message = (
                out.unknown.get(b"\xfc\x07specter\x01", b"")
                if out.bip32_derivations
                else b""
            )
            out.reblind(
                rangeproof_nonce,
                extra_message=extra_message,
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
                "value_commitment": write_commitment(inp.utxo.value),
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


def enumerate(password: str = "") -> List[Dict[str, Any]]:
    results = []

    def _get_device_entry(device_model: str, device_path: str) -> Dict[str, Any]:
        d_data: Dict[str, Any] = {}
        d_data["type"] = "jade"
        d_data["model"] = device_model
        d_data["path"] = device_path
        d_data["needs_pin_sent"] = False
        d_data["needs_passphrase_sent"] = False

        client = None
        with handle_errors(common_err_msgs["enumerate"], d_data):
            client = JadeClient(device_path, password, timeout=1)
            d_data["fingerprint"] = client.get_master_fingerprint().hex()

        if client:
            client.close()

        return d_data

    # Jade is not really an HID device, it shows as a serial/com port device.
    # Scan com ports looking for the relevant vid and pid, and use 'path' to
    # hold the path to the serial port device, eg. /dev/ttyUSB0
    for devinfo in list_ports.comports():
        if (devinfo.vid, devinfo.pid) in JADE_DEVICE_IDS:
            results.append(_get_device_entry("jade", devinfo.device))

    # If we can connect to the simulator, add it too
    try:
        with JadeAPI.create_serial(SIMULATOR_PATH, timeout=1) as jade:
            verinfo = jade.get_version_info()

        if verinfo is not None:
            results.append(_get_device_entry("jade_simulator", SIMULATOR_PATH))

    except Exception as e:
        # If we get any sort of error do not add the simulator
        logger.debug(f"Failed to connect to Jade simulator at {SIMULATOR_PATH}")
        logger.debug(e)

    return results
