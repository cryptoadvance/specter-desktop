"""
Blockstream Jade Devices
************************
"""

from .jadepy import jade
from .jadepy.jade import JadeAPI, JadeError
from serial.tools import list_ports

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
from hwilib.descriptor import MultisigDescriptor
from hwilib.hwwclient import HardwareWalletClient
from hwilib.errors import (
    ActionCanceledError,
    BadArgumentError,
    DeviceConnectionError,
    DeviceFailureError,
    DeviceNotReadyError,
    UnavailableActionError,
    common_err_msgs,
    handle_errors,
)
from hwilib.common import AddressType, Chain, sha256
from hwilib.key import ExtendedKey, KeyOriginInfo, is_hardened, parse_path
from hwilib.psbt import PSBT
from hwilib._script import is_p2sh, is_p2wpkh, is_p2wsh, is_witness, parse_multisig

import logging
import semver
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
from embit.descriptor import Descriptor

# The test emulator port
SIMULATOR_PATH = "tcp:127.0.0.1:30121"

JADE_DEVICE_IDS = [
    (0x10C4, 0xEA60),
    (0x1A86, 0x55D4),
    (0x0403, 0x6001),
    (0x1A86, 0x7523),
]
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
    MIN_SUPPORTED_FW_VERSION = semver.VersionInfo(0, 1, 32)

    NETWORKS = {
        Chain.MAIN: "mainnet",
        Chain.TEST: "testnet",
        Chain.SIGNET: "testnet",  # same as far as Jade is concerned
        Chain.REGTEST: "localtest",
    }

    def _network(self) -> str:
        if self.chain not in self.NETWORKS:
            raise BadArgumentError(f"Unhandled network: {self.chain}")
        return self.NETWORKS[self.chain]

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

    @classmethod
    def _convertAddrType(cls, addrType: AddressType, multisig: bool) -> str:
        return cls.MULTI_ADDRTYPES[addrType] if multisig else cls.ADDRTYPES[addrType]

    # Derive a deterministic name for a multisig registration record (ignoring bip67 key sorting)
    @staticmethod
    def _get_multisig_name(
        type: str, threshold: int, signers: List[Tuple[bytes, Sequence[int]]]
    ) -> str:
        # Concatenate script-type, threshold, and all signers fingerprints and derivation paths (sorted)
        summary = type + "|" + str(threshold) + "|"
        for fingerprint, path in sorted(signers):
            summary += fingerprint.hex() + "|" + str(path) + "|"

        # Hash it, get the first 6-bytes as hex, prepend with 'hwi'
        hash_summary = sha256(summary.encode()).hex()
        return "hwi" + hash_summary[:12]

    def __init__(
        self,
        path: str,
        password: Optional[str] = None,
        expert: bool = False,
        chain: Chain = Chain.MAIN,
        skip_unlocking: bool = False,
        timeout: Optional[int] = None,
    ) -> None:
        super(JadeClient, self).__init__(path, password, expert, chain)
        self.jade = JadeAPI.create_serial(path, timeout=timeout)
        self.jade.connect()

        verinfo = self.jade.get_version_info()
        uninitialized = verinfo["JADE_STATE"] not in ["READY", "TEMP"]

        # Check minimum supported firmware version (ignore candidate/build parts)
        fw_version = semver.parse_version_info(verinfo["JADE_VERSION"])
        if self.MIN_SUPPORTED_FW_VERSION > fw_version.finalize_version():
            raise DeviceNotReadyError(
                f"Jade fw version: {fw_version} - minimum required version: {self.MIN_SUPPORTED_FW_VERSION}. "
                "Please update using a Blockstream Green companion app"
            )
        if path == SIMULATOR_PATH:
            if uninitialized:
                # Connected to simulator but it appears to have no wallet set
                raise DeviceNotReadyError(
                    "Use JadeAPI.set_[seed|mnemonic] to set simulator wallet"
                )
        else:
            if uninitialized:
                if skip_unlocking:
                    # We don't want to prompt to unlock the device right now
                    return
                if not HAS_NETWORKING:
                    # Wallet not initialised/unlocked nor do we have networking dependencies
                    # User must use 'Recovery Phrase Login' or 'QR Unlock' feature to access wallet
                    raise DeviceNotReadyError(
                        'Use "Recovery Phrase Login" or "QR PIN Unlock" feature on Jade hw to access wallet'
                    )

            # Push some host entropy into jade
            self.jade.add_entropy(os.urandom(32))

            # Authenticate the user - this may require a PIN and pinserver interaction
            # (if we have required networking dependencies)
            authenticated = False
            while not authenticated:
                authenticated = self.jade.auth_user(self._network())

    # Retrieves the public key at the specified BIP 32 derivation path
    @jade_exception
    def get_pubkey_at_path(self, bip32_path: str) -> ExtendedKey:
        path = parse_path(bip32_path)
        xpub = self.jade.get_xpub(self._network(), path)
        ext_key = ExtendedKey.deserialize(xpub)
        return ext_key

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
            return signers, paths

        c_txn = tx.get_unsigned_tx()
        master_fp = self.get_master_fingerprint()
        signing_singlesigs = False
        signing_multisigs = {}
        need_to_sign = True

        while need_to_sign:
            signing_pubkeys: List[Optional[bytes]] = [None] * len(tx.inputs)
            need_to_sign = False

            # Signing input details
            jade_inputs = []
            for n_vin, psbtin in py_enumerate(tx.inputs):
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
                    if psbtin.prev_txid != psbtin.non_witness_utxo.hash:
                        raise BadArgumentError(
                            f"Input {n_vin} has a non_witness_utxo with the wrong hash"
                        )
                    assert psbtin.prev_out is not None
                    utxo = psbtin.non_witness_utxo.vout[psbtin.prev_out]
                    input_txn_bytes = (
                        psbtin.non_witness_utxo.serialize_without_witness()
                    )
                if utxo is None:
                    raise Exception(
                        "PSBT is missing input utxo information, cannot sign"
                    )
                sats_value = utxo.nValue
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
                        "satoshi": sats_value,
                        "script": scriptcode,
                        "path": path,
                        "input_tx": input_txn_bytes,
                        "ae_host_entropy": os.urandom(32),
                        "ae_host_commitment": os.urandom(32),
                    }
                )

            # Change output details
            # This is optional, in that if we send it Jade validates the change output script
            # and the user need not confirm that output.  If not passed the change output must
            # be confirmed by the user on the hwwallet screen, like any other spend output.
            change: List[Optional[Dict[str, Any]]] = [None] * len(tx.outputs)

            # Skip automatic change validation in expert mode - user checks *every* output on hw
            if not self.expert:
                # If signing multisig inputs, get registered multisigs details in case we
                # see any multisig outputs which may be change which we can auto-validate.
                # ie. filter speculative 'signing multisigs' to ones actually registered on the hw
                if signing_multisigs:
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
                for n_vout, (txout, psbtout) in py_enumerate(
                    zip(c_txn.vout, tx.outputs)
                ):
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
                                    txout.is_p2sh()
                                    and is_witness(psbtout.redeem_script)[0]
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
                                    txout.is_p2sh()
                                    and is_witness(psbtout.redeem_script)[0]
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
                                        psbtout.hd_keypaths[pubkey]
                                        for pubkey in pubkeys
                                    ]

                                    signers, paths = _parse_signers(hd_keypath_origins)
                                    multisig_name = self._get_multisig_name(
                                        script_variant, threshold, signers
                                    )
                                    matched_multisig = candidate_multisigs.get(
                                        multisig_name
                                    )

                                    if (
                                        matched_multisig
                                        and matched_multisig[0] == script_variant
                                        and matched_multisig[1] == threshold
                                        and sorted(matched_multisig[2])
                                        == sorted(signers)
                                    ):
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

        # NOTE: tests fail if we try to use AE signatures, so stick with default (rfc6979)
        signature = self.jade.sign_message(path, message)
        return str(signature)

    # Display address of specified type on the device.
    @jade_exception
    def display_singlesig_address(self, bip32_path: str, addr_type: AddressType) -> str:
        path = parse_path(bip32_path)
        script_variant = self._convertAddrType(addr_type, multisig=False)
        address = self.jade.get_receive_address(
            self._network(), path, variant=script_variant
        )
        return str(address)

    # Display multisig address of specified type on the device.
    @jade_exception
    def display_multisig_address(
        self, addr_type: AddressType, multisig: MultisigDescriptor
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
                    "Blockstream Jade can only generate addresses for multisigs with key derivation paths"
                )

            if pubkey.origin.path and not is_hardened(pubkey.origin.path[-1]):
                logging.warning(
                    f"Final element of origin path {pubkey.origin.path} unhardened"
                )
                logging.warning(
                    "Blockstream Jade may not be able to identify change sent back to this descriptor"
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

        if multisig.is_sorted and paths[:-1] != paths[1:]:
            logging.warning("Sorted multisig with different derivations per signer")
            logging.warning(
                "Blockstream Jade may not be able to validate change sent back to this descriptor"
            )

        # Get a deterministic name for this multisig wallet (ignoring bip67 key sorting)
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
            multisig.is_sorted,
            multisig.thresh,
            signers,
        )
        address = self.jade.get_receive_address(
            self._network(), paths, multisig_name=multisig_name
        )

        return str(address)

    # Custom Specter method - register multisig on the Jade
    @jade_exception
    def register_multisig(self, descriptor: str) -> None:

        descriptor = Descriptor.from_string(descriptor)
        signer_origins = []
        signers = []
        paths = []
        for key in descriptor.keys:
            # Tuple to derive deterministic name for the registration
            signer_origins.append((key.origin.fingerprint, key.origin.derivation))

            #  We won't include the additional path in the multisig registration
            signers.append(
                {
                    "fingerprint": key.fingerprint,
                    "derivation": key.derivation,
                    "xpub": key.key.to_string(),
                    "path": [],
                }
            )

        # Get a deterministic name for this multisig wallet (ignoring bip67 key sorting)
        if descriptor.wsh and not descriptor.sh:
            addr_type = AddressType.WIT
        elif descriptor.wsh and descriptor.sh:
            addr_type = AddressType.SH_WIT
        elif descriptor.wsh.is_legacy:
            addr_type = AddressType.LEGACY
        else:
            raise BadArgumentError(
                "The script type of the descriptor does not match any standard type."
            )

        script_variant = self._convertAddrType(addr_type, multisig=True)
        threshold = descriptor.miniscript.args[0].num  # hackish ...

        multisig_name = self._get_multisig_name(
            script_variant, threshold, signer_origins
        )

        # 're-registering' is a no-op
        self.jade.register_multisig(
            self._network(),
            multisig_name,
            script_variant,
            descriptor.is_sorted,
            threshold,
            signers,
        )

    # Setup a new device
    def setup_device(self, label: str = "", passphrase: str = "") -> bool:
        """
        Blockstream Jade does not support setup via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError("Blockstream Jade does not support software setup")

    # Wipe this device
    def wipe_device(self) -> bool:
        """
        Blockstream Jade does not support wiping via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not support wiping via software"
        )

    # Restore device from mnemonic or xprv
    def restore_device(self, label: str = "", word_count: int = 24) -> bool:
        """
        Blockstream Jade does not support restoring via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not support restoring via software"
        )

    # Begin backup process
    def backup_device(self, label: str = "", passphrase: str = "") -> bool:
        """
        Blockstream Jade does not support backing up via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not support creating a backup via software"
        )

    # Close the device
    def close(self) -> None:
        self.jade.disconnect()

    # Prompt pin
    def prompt_pin(self) -> bool:
        """
        Blockstream Jade does not need a PIN sent from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not need a PIN sent from the host"
        )

    # Send pin
    def send_pin(self, pin: str) -> bool:
        """
        Blockstream Jade does not need a PIN sent from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not need a PIN sent from the host"
        )

    # Toggle passphrase
    def toggle_passphrase(self) -> bool:
        """
        Blockstream Jade does not support toggling passphrase from the host.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "Blockstream Jade does not support toggling passphrase from the host"
        )

    @jade_exception
    def can_sign_taproot(self) -> bool:
        """
        Blockstream Jade does not currently support Taproot.

        :returns: False, always
        """
        return False


def enumerate(
    password: Optional[str] = None,
    expert: bool = False,
    chain: Chain = Chain.MAIN,
    skip_unlocking=True,
) -> List[Dict[str, Any]]:
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
            client = JadeClient(
                device_path, password, expert, chain, skip_unlocking, timeout=1
            )
            # The Jade could already be unlocked upon startup (this is the only instance where unlock_required is False right now).
            # But, we don't need the fingerpint then.
            if client and not skip_unlocking:
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
        logging.debug(f"Failed to connect to Jade simulator at {SIMULATOR_PATH}")
        logging.debug(e)

    return results
