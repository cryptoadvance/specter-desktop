"""
Trezor Devices
**************
"""

from functools import wraps
from typing import (
    Any,
    Callable,
    Dict,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Union,
)
from hwilib.descriptor import MultisigDescriptor
from hwilib.hwwclient import HardwareWalletClient
from hwilib.errors import (
    ActionCanceledError,
    BadArgumentError,
    DeviceAlreadyInitError,
    DeviceAlreadyUnlockedError,
    DeviceConnectionError,
    DEVICE_NOT_INITIALIZED,
    DeviceNotReadyError,
    UnavailableActionError,
    common_err_msgs,
    handle_errors,
)
from hwilib.devices.trezorlib.client import TrezorClient as Trezor, PASSPHRASE_ON_DEVICE
from hwilib.devices.trezorlib.debuglink import TrezorClientDebugLink
from hwilib.devices.trezorlib.exceptions import Cancelled, TrezorFailure
from hwilib.devices.trezorlib.transport import (
    DEV_TREZOR1,
    TREZORS,
    hid,
    udp,
    webusb,
)
from hwilib.devices.trezorlib import (
    btc,
    device,
)
from hwilib.devices.trezorlib import messages
from hwilib._base58 import (
    get_xpub_fingerprint,
    to_address,
)
from hwilib import _base58 as base58

from hwilib.key import (
    ExtendedKey,
    parse_path,
)
from hwilib._script import (
    is_p2pkh,
    is_p2sh,
    is_p2wsh,
    is_witness,
)
from hwilib.psbt import (
    PSBT,
    PartiallySignedInput,
    PartiallySignedOutput,
    KeyOriginInfo,
)
from hwilib.tx import (
    CTxOut,
)
from hwilib._serialize import (
    ser_uint256,
)
from hwilib.common import (
    AddressType,
    Chain,
    hash256,
)
from hwilib import _bech32 as bech32
from mnemonic import Mnemonic
from usb1 import USBErrorNoDevice
from types import MethodType

import base64
import getpass
import logging
import sys
import struct

py_enumerate = enumerate  # Need to use the enumerate built-in but there's another function already named that

PIN_MATRIX_DESCRIPTION = """
Use the numeric keypad to describe number positions. The layout is:
    7 8 9
    4 5 6
    1 2 3
""".strip()

Device = Union[hid.HidTransport, webusb.WebUsbTransport, udp.UdpTransport]


# Only handles up to 15 of 15
def parse_multisig(
    script: bytes,
    tx_xpubs: Dict[bytes, KeyOriginInfo],
    psbt_scope: Union[PartiallySignedInput, PartiallySignedOutput],
) -> Tuple[bool, Optional[messages.MultisigRedeemScriptType]]:
    # at least OP_M pub OP_N OP_CHECKMULTISIG
    if len(script) < 37:
        return (False, None)
    # Get m
    m = script[0] - 80
    if m < 1 or m > 15:
        return (False, None)

    # Get pubkeys and build HDNodePathType
    pubkeys = []
    offset = 1
    while True:
        pubkey_len = script[offset]
        if pubkey_len != 33:
            break
        offset += 1
        key = script[offset : offset + 33]
        offset += 33

        hd_node = messages.HDNodeType(
            depth=0,
            fingerprint=0,
            child_num=0,
            chain_code=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            public_key=key,
        )
        pubkeys.append(messages.HDNodePathType(node=hd_node, address_n=[]))

    # Check things at the end
    n = script[offset] - 80
    if n != len(pubkeys):
        return (False, None)
    offset += 1
    op_cms = script[offset]
    if op_cms != 174:
        return (False, None)

    # check if we know corresponding xpubs from global scope
    for pub in pubkeys:
        if pub.node.public_key in psbt_scope.hd_keypaths:
            derivation = psbt_scope.hd_keypaths[pub.node.public_key]
            for xpub in tx_xpubs:
                hd = ExtendedKey.deserialize(base58.encode(xpub + hash256(xpub)[:4]))
                origin = tx_xpubs[xpub]
                # check fingerprint and derivation
                if (origin.fingerprint == derivation.fingerprint) and (
                    origin.path == derivation.path[: len(origin.path)]
                ):
                    # all good - populate node and break
                    pub.address_n = list(derivation.path[len(origin.path) :])
                    pub.node = messages.HDNodeType(
                        depth=hd.depth,
                        fingerprint=int.from_bytes(hd.parent_fingerprint, "big"),
                        child_num=hd.child_num,
                        chain_code=hd.chaincode,
                        public_key=hd.pubkey,
                    )
                    break
    # Build MultisigRedeemScriptType and return it
    multisig = messages.MultisigRedeemScriptType(
        m=m, signatures=[b""] * n, pubkeys=pubkeys
    )
    return (True, multisig)


def trezor_exception(f: Callable[..., Any]) -> Any:
    @wraps(f)
    def func(*args: Any, **kwargs: Any) -> Any:
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            raise BadArgumentError(str(e))
        except Cancelled:
            raise ActionCanceledError("{} canceled".format(f.__name__))
        except USBErrorNoDevice:
            raise DeviceConnectionError("Device disconnected")

    return func


def interactive_get_pin(self: object, code: Optional[int] = None) -> str:
    if code == messages.PinMatrixRequestType.Currrent:
        desc = "current PIN"
    elif code == messages.PinMatrixRequestType.NewFirst:
        desc = "new PIN"
    elif code == messages.PinMatrixRequestType.NewSecond:
        desc = "new PIN again"
    else:
        desc = "PIN"

    print(PIN_MATRIX_DESCRIPTION, file=sys.stderr)

    while True:
        pin = getpass.getpass(f"Please entire {desc}:\n")
        if not pin.isdigit():
            print("Non-numerical PIN provided, please try again", file=sys.stderr)
        else:
            return pin


def mnemonic_words(
    expand: bool = False, language: str = "english"
) -> Callable[[Any], str]:
    wordlist: Sequence[str] = []
    if expand:
        wordlist = Mnemonic(language).wordlist

    def expand_word(word: str) -> str:
        if not expand:
            return word
        if word in wordlist:
            return word
        matches = [w for w in wordlist if w.startswith(word)]
        if len(matches) == 1:
            return matches[0]
        print("Choose one of: " + ", ".join(matches), file=sys.stderr)
        raise KeyError(word)

    def get_word(type: messages.WordRequestType) -> str:
        assert type == messages.WordRequestType.Plain
        while True:
            try:
                word = input("Enter one word of mnemonic:\n")
                return expand_word(word)
            except KeyError:
                pass
            except Exception:
                raise Cancelled from None

    return get_word


class PassphraseUI:
    def __init__(self, passphrase: str) -> None:
        self.passphrase = passphrase
        self.pinmatrix_shown = False
        self.prompt_shown = False
        self.always_prompt = False
        self.return_passphrase = True

    def button_request(self, code: Optional[int]) -> None:
        if not self.prompt_shown:
            print("Please confirm action on your Trezor device", file=sys.stderr)
        if not self.always_prompt:
            self.prompt_shown = True

    def get_pin(self, code: Optional[int] = None) -> NoReturn:
        raise NotImplementedError("get_pin is not needed")

    def disallow_passphrase(self) -> None:
        self.return_passphrase = False

    def get_passphrase(self, available_on_device: bool) -> object:
        if available_on_device:
            return PASSPHRASE_ON_DEVICE
        if self.return_passphrase:
            return self.passphrase
        raise ValueError("Passphrase from Host is not allowed for Trezor T")


HID_IDS = {DEV_TREZOR1}
WEBUSB_IDS = TREZORS.copy()


def get_path_transport(path: str) -> Device:
    devs = hid.HidTransport.enumerate(usb_ids=HID_IDS)
    devs.extend(webusb.WebUsbTransport.enumerate(usb_ids=WEBUSB_IDS))
    devs.extend(udp.UdpTransport.enumerate())
    for dev in devs:
        if path == dev.get_path():
            return dev
    raise BadArgumentError(f"Could not find device by path: {path}")


# This class extends the HardwareWalletClient for Trezor specific things
class TrezorClient(HardwareWalletClient):
    def __init__(self, path: str, password: str = "", expert: bool = False) -> None:
        super(TrezorClient, self).__init__(path, password, expert)
        self.simulator = False
        transport = get_path_transport(path)
        if path.startswith("udp"):
            logging.debug("Simulator found, using DebugLink")
            self.client = TrezorClientDebugLink(transport=transport)
            self.simulator = True
            self.client.use_passphrase(password)
        else:
            self.client = Trezor(transport=transport, ui=PassphraseUI(password))

        # if it wasn't able to find a client, throw an error
        if not self.client:
            raise IOError("no Device")

        self.password = password
        self.type = "Trezor"

    def _prepare_device(self) -> None:
        self.coin_name = "Bitcoin" if self.chain == Chain.MAIN else "Testnet"
        resp = self.client.refresh_features()
        # If this is a Trezor One or Keepkey, do Initialize
        if resp.model == "1" or resp.model == "K1-14AM":
            self.client.init_device()
        # For the T, we need to check if a passphrase needs to be entered
        elif resp.model == "T":
            try:
                self.client.ensure_unlocked()
            except TrezorFailure:
                self.client.init_device()

    def _check_unlocked(self) -> None:
        self._prepare_device()
        if self.client.features.model == "T" and isinstance(
            self.client.ui, PassphraseUI
        ):
            self.client.ui.disallow_passphrase()
        if self.client.features.pin_protection and not self.client.features.unlocked:
            raise DeviceNotReadyError(
                "{} is locked. Unlock by using 'promptpin' and then 'sendpin'.".format(
                    self.type
                )
            )

    @trezor_exception
    def get_pubkey_at_path(self, path: str) -> ExtendedKey:
        self._check_unlocked()
        try:
            expanded_path = parse_path(path)
        except ValueError as e:
            raise BadArgumentError(str(e))
        output = btc.get_public_node(
            self.client, expanded_path, coin_name=self.coin_name
        )
        xpub = ExtendedKey.deserialize(output.xpub)
        if self.chain != Chain.MAIN:
            xpub.version = ExtendedKey.TESTNET_PUBLIC
        return xpub

    @trezor_exception
    def sign_tx(self, tx: PSBT) -> PSBT:
        """
        Sign a transaction with the Trezor. There are some limitations to what transactions can be signed.

        - Multisig inputs are limited to at most n-of-15 multisigs. This is a firmware limitation.
        - Transactions with arbitrary input scripts (scriptPubKey, redeemScript, or witnessScript) and arbitrary output scripts cannot be signed. This is a firmware limitation.
        - Send-to-self transactions will result in no prompt for outputs as all outputs will be detected as change.
        """
        self._check_unlocked()

        # Get this devices master key fingerprint
        master_key = btc.get_public_node(self.client, [0x80000000], coin_name="Bitcoin")
        master_fp = get_xpub_fingerprint(master_key.xpub)

        # Do multiple passes for multisig
        passes = 1
        p = 0

        while p < passes:
            # Prepare inputs
            inputs = []
            to_ignore = (
                []
            )  # Note down which inputs whose signatures we're going to ignore
            for input_num, (psbt_in, txin) in py_enumerate(
                list(zip(tx.inputs, tx.tx.vin))
            ):
                txinputtype = messages.TxInputType(
                    prev_hash=ser_uint256(txin.prevout.hash)[::-1],
                    prev_index=txin.prevout.n,
                    sequence=txin.nSequence,
                )

                # Detrermine spend type
                scriptcode = b""
                utxo = None
                if psbt_in.witness_utxo:
                    utxo = psbt_in.witness_utxo
                if psbt_in.non_witness_utxo:
                    if txin.prevout.hash != psbt_in.non_witness_utxo.sha256:
                        raise BadArgumentError(
                            "Input {} has a non_witness_utxo with the wrong hash".format(
                                input_num
                            )
                        )
                    utxo = psbt_in.non_witness_utxo.vout[txin.prevout.n]
                if utxo is None:
                    continue
                scriptcode = utxo.scriptPubKey

                # Check if P2SH
                p2sh = False
                if is_p2sh(scriptcode):
                    # Look up redeemscript
                    if len(psbt_in.redeem_script) == 0:
                        continue
                    scriptcode = psbt_in.redeem_script
                    p2sh = True

                # Check segwit
                is_wit, _, _ = is_witness(scriptcode)

                if is_wit:
                    if p2sh:
                        txinputtype.script_type = (
                            messages.InputScriptType.SPENDP2SHWITNESS
                        )
                    else:
                        txinputtype.script_type = messages.InputScriptType.SPENDWITNESS
                else:
                    txinputtype.script_type = messages.InputScriptType.SPENDADDRESS
                txinputtype.amount = utxo.nValue

                # Check if P2WSH
                p2wsh = False
                if is_p2wsh(scriptcode):
                    # Look up witnessscript
                    if len(psbt_in.witness_script) == 0:
                        continue
                    scriptcode = psbt_in.witness_script
                    p2wsh = True

                def ignore_input() -> None:
                    txinputtype.address_n = [
                        0x80000000 | 84,
                        0x80000000 | (0 if self.chain == Chain.MAIN else 1),
                        0x80000000,
                        0,
                        0,
                    ]
                    txinputtype.multisig = None
                    txinputtype.script_type = messages.InputScriptType.SPENDWITNESS
                    inputs.append(txinputtype)
                    to_ignore.append(input_num)

                # Check for multisig
                is_ms, multisig = parse_multisig(scriptcode, tx.xpub, psbt_in)
                if is_ms:
                    # Add to txinputtype
                    txinputtype.multisig = multisig
                    if not is_wit:
                        if utxo.is_p2sh:
                            txinputtype.script_type = (
                                messages.InputScriptType.SPENDMULTISIG
                            )
                        else:
                            # Cannot sign bare multisig, ignore it
                            ignore_input()
                            continue
                elif not is_ms and not is_wit and not is_p2pkh(scriptcode):
                    # Cannot sign unknown spk, ignore it
                    ignore_input()
                    continue
                elif not is_ms and is_wit and p2wsh:
                    # Cannot sign unknown witness script, ignore it
                    ignore_input()
                    continue

                # Find key to sign with
                found = False  # Whether we have found a key to sign with
                found_in_sigs = (
                    False  # Whether we have found one of our keys in the signatures
                )
                our_keys = 0
                for key in psbt_in.hd_keypaths.keys():
                    keypath = psbt_in.hd_keypaths[key]
                    if keypath.fingerprint == master_fp:
                        if (
                            key in psbt_in.partial_sigs
                        ):  # This key already has a signature
                            found_in_sigs = True
                            continue
                        if (
                            not found
                        ):  # This key does not have a signature and we don't have a key to sign with yet
                            txinputtype.address_n = keypath.path
                            found = True
                        our_keys += 1

                # Determine if we need to do more passes to sign everything
                if our_keys > passes:
                    passes = our_keys

                if (
                    not found and not found_in_sigs
                ):  # None of our keys were in hd_keypaths or in partial_sigs
                    # This input is not one of ours
                    ignore_input()
                    continue
                elif (
                    not found and found_in_sigs
                ):  # All of our keys are in partial_sigs, ignore whatever signature is produced for this input
                    ignore_input()
                    continue

                # append to inputs
                inputs.append(txinputtype)

            # address version byte
            if self.chain != Chain.MAIN:
                p2pkh_version = b"\x6f"
                p2sh_version = b"\xc4"
                bech32_hrp = "tb"
            else:
                p2pkh_version = b"\x00"
                p2sh_version = b"\x05"
                bech32_hrp = "bc"

            # prepare outputs
            outputs = []
            for i, out in py_enumerate(tx.tx.vout):
                txoutput = messages.TxOutputType(amount=out.nValue)
                txoutput.script_type = messages.OutputScriptType.PAYTOADDRESS
                if out.is_p2pkh():
                    txoutput.address = to_address(out.scriptPubKey[3:23], p2pkh_version)
                elif out.is_p2sh():
                    txoutput.address = to_address(out.scriptPubKey[2:22], p2sh_version)
                elif out.is_opreturn():
                    txoutput.script_type = messages.OutputScriptType.PAYTOOPRETURN
                    txoutput.op_return_data = out.scriptPubKey[2:]
                else:
                    wit, ver, prog = out.is_witness()
                    if wit:
                        txoutput.address = bech32.encode(bech32_hrp, ver, prog)
                    else:
                        raise BadArgumentError("Output is not an address")

                # Add the derivation path for change
                psbt_out = tx.outputs[i]
                for _, keypath in psbt_out.hd_keypaths.items():
                    if keypath.fingerprint != master_fp:
                        continue
                    wit, ver, prog = out.is_witness()
                    if out.is_p2pkh():
                        txoutput.address_n = keypath.path
                        txoutput.address = None
                    elif wit:
                        txoutput.script_type = messages.OutputScriptType.PAYTOWITNESS
                        txoutput.address_n = keypath.path
                        txoutput.address = None
                    elif out.is_p2sh() and psbt_out.redeem_script:
                        wit, ver, prog = CTxOut(0, psbt_out.redeem_script).is_witness()
                        if wit and len(prog) in [20, 32]:
                            txoutput.script_type = (
                                messages.OutputScriptType.PAYTOP2SHWITNESS
                            )
                            txoutput.address_n = keypath.path
                            txoutput.address = None

                # add multisig info
                is_ms, multisig = parse_multisig(
                    psbt_out.witness_script or psbt_out.redeem_script, tx.xpub, psbt_out
                )
                if is_ms:
                    txoutput.multisig = multisig

                # append to outputs
                outputs.append(txoutput)

            # Prepare prev txs
            prevtxs = {}
            for psbt_in in tx.inputs:
                if psbt_in.non_witness_utxo:
                    prev = psbt_in.non_witness_utxo

                    t = messages.TransactionType()
                    t.version = prev.nVersion
                    t.lock_time = prev.nLockTime

                    for vin in prev.vin:
                        i = messages.TxInputType(
                            prev_hash=ser_uint256(vin.prevout.hash)[::-1],
                            prev_index=vin.prevout.n,
                            script_sig=vin.scriptSig,
                            sequence=vin.nSequence,
                        )
                        t.inputs.append(i)

                    for vout in prev.vout:
                        o = messages.TxOutputBinType(
                            amount=vout.nValue,
                            script_pubkey=vout.scriptPubKey,
                        )
                        t.bin_outputs.append(o)
                    logging.debug(psbt_in.non_witness_utxo.hash)
                    assert psbt_in.non_witness_utxo.sha256 is not None
                    prevtxs[ser_uint256(psbt_in.non_witness_utxo.sha256)[::-1]] = t

            # Sign the transaction
            signed_tx = btc.sign_tx(
                client=self.client,
                coin_name=self.coin_name,
                inputs=inputs,
                outputs=outputs,
                prev_txes=prevtxs,
                version=tx.tx.nVersion,
                lock_time=tx.tx.nLockTime,
            )

            # Each input has one signature
            for input_num, (psbt_in, sig) in py_enumerate(
                list(zip(tx.inputs, signed_tx[0]))
            ):
                if input_num in to_ignore:
                    continue
                for pubkey in psbt_in.hd_keypaths.keys():
                    fp = psbt_in.hd_keypaths[pubkey].fingerprint
                    if fp == master_fp and pubkey not in psbt_in.partial_sigs:
                        psbt_in.partial_sigs[pubkey] = sig + b"\x01"
                        break

            p += 1

        return tx

    @trezor_exception
    def sign_message(self, message: Union[str, bytes], keypath: str) -> str:
        self._check_unlocked()
        path = parse_path(keypath)
        result = btc.sign_message(self.client, self.coin_name, path, message)
        return base64.b64encode(result.signature).decode("utf-8")

    @trezor_exception
    def display_singlesig_address(
        self,
        keypath: str,
        addr_type: AddressType,
    ) -> str:
        self._check_unlocked()

        # Script type
        if addr_type == AddressType.SH_WIT:
            script_type = messages.InputScriptType.SPENDP2SHWITNESS
        elif addr_type == AddressType.WIT:
            script_type = messages.InputScriptType.SPENDWITNESS
        elif addr_type == AddressType.LEGACY:
            script_type = messages.InputScriptType.SPENDADDRESS
        else:
            raise BadArgumentError("Unknown address type")

        expanded_path = parse_path(keypath)

        try:
            address = btc.get_address(
                self.client,
                self.coin_name,
                expanded_path,
                show_display=True,
                script_type=script_type,
                multisig=None,
            )
            assert isinstance(address, str)
            return address
        except Exception:
            pass

        raise BadArgumentError("No path supplied matched device keys")

    @trezor_exception
    def display_multisig_address(
        self,
        addr_type: AddressType,
        multisig: MultisigDescriptor,
    ) -> str:
        self._check_unlocked()

        der_pks = list(
            zip([p.get_pubkey_bytes(0) for p in multisig.pubkeys], multisig.pubkeys)
        )
        if multisig.is_sorted:
            der_pks = sorted(der_pks)

        pubkey_objs = []
        for pk, p in der_pks:
            if p.extkey is not None:
                xpub = p.extkey
                hd_node = messages.HDNodeType(
                    depth=xpub.depth,
                    fingerprint=int.from_bytes(xpub.parent_fingerprint, "big"),
                    child_num=xpub.child_num,
                    chain_code=xpub.chaincode,
                    public_key=xpub.pubkey,
                )
                pubkey_objs.append(
                    messages.HDNodePathType(
                        node=hd_node,
                        address_n=parse_path(
                            "m" + p.deriv_path if p.deriv_path is not None else ""
                        ),
                    )
                )
            else:
                hd_node = messages.HDNodeType(
                    depth=0,
                    fingerprint=0,
                    child_num=0,
                    chain_code=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
                    public_key=pk,
                )
                pubkey_objs.append(messages.HDNodePathType(node=hd_node, address_n=[]))

        trezor_ms = messages.MultisigRedeemScriptType(
            m=multisig.thresh, signatures=[b""] * len(pubkey_objs), pubkeys=pubkey_objs
        )

        # Script type
        if addr_type == AddressType.SH_WIT:
            script_type = messages.InputScriptType.SPENDP2SHWITNESS
        elif addr_type == AddressType.WIT:
            script_type = messages.InputScriptType.SPENDWITNESS
        elif addr_type == AddressType.LEGACY:
            script_type = messages.InputScriptType.SPENDMULTISIG
        else:
            raise BadArgumentError("Unknown address type")

        for p in multisig.pubkeys:
            keypath = p.origin.get_derivation_path() if p.origin is not None else "m/"
            keypath += p.deriv_path if p.deriv_path is not None else ""
            path = parse_path(keypath)
            try:
                address = btc.get_address(
                    self.client,
                    self.coin_name,
                    path,
                    show_display=True,
                    script_type=script_type,
                    multisig=trezor_ms,
                )
                assert isinstance(address, str)
                return address
            except Exception:
                pass

        raise BadArgumentError("No path supplied matched device keys")

    @trezor_exception
    def setup_device(self, label: str = "", passphrase: str = "") -> bool:
        self._prepare_device()
        if not self.simulator:
            # Use interactive_get_pin
            self.client.ui.get_pin = MethodType(interactive_get_pin, self.client.ui)

        if self.client.features.initialized:
            raise DeviceAlreadyInitError(
                "Device is already initialized. Use wipe first and try again"
            )
        device.reset(self.client, passphrase_protection=bool(self.password))
        return True

    @trezor_exception
    def wipe_device(self) -> bool:
        self._check_unlocked()
        device.wipe(self.client)
        return True

    @trezor_exception
    def restore_device(self, label: str = "", word_count: int = 24) -> bool:
        self._prepare_device()
        if not self.simulator:
            # Use interactive_get_pin
            self.client.ui.get_pin = MethodType(interactive_get_pin, self.client.ui)

        device.recover(
            self.client,
            word_count=word_count,
            label=label,
            input_callback=mnemonic_words(),
            passphrase_protection=bool(self.password),
        )
        return True

    def backup_device(self, label: str = "", passphrase: str = "") -> bool:
        """
        Trezor devices do not support backing up via software.

        :raises UnavailableActionError: Always, this function is unavailable
        """
        raise UnavailableActionError(
            "The {} does not support creating a backup via software".format(self.type)
        )

    @trezor_exception
    def close(self) -> None:
        self.client.close()

    @trezor_exception
    def prompt_pin(self) -> bool:
        self.coin_name = "Bitcoin" if self.chain == Chain.MAIN else "Testnet"
        self.client.open()
        self._prepare_device()
        if not self.client.features.pin_protection:
            raise DeviceAlreadyUnlockedError("This device does not need a PIN")
        if self.client.features.unlocked:
            raise DeviceAlreadyUnlockedError(
                "The PIN has already been sent to this device"
            )
        print(
            "Use 'sendpin' to provide the number positions for the PIN as displayed on your device's screen",
            file=sys.stderr,
        )
        print(PIN_MATRIX_DESCRIPTION, file=sys.stderr)
        self.client.call_raw(
            messages.GetPublicKey(
                address_n=[0x8000002C, 0x80000001, 0x80000000],
                ecdsa_curve_name=None,
                show_display=False,
                coin_name=self.coin_name,
                script_type=messages.InputScriptType.SPENDADDRESS,
            )
        )
        return True

    @trezor_exception
    def send_pin(self, pin: str) -> bool:
        self.client.open()
        if not pin.isdigit():
            raise BadArgumentError("Non-numeric PIN provided")
        resp = self.client.call_raw(messages.PinMatrixAck(pin=pin))
        if isinstance(resp, messages.Failure):
            self.client.features = self.client.call_raw(messages.GetFeatures())
            if isinstance(self.client.features, messages.Features):
                if not self.client.features.pin_protection:
                    raise DeviceAlreadyUnlockedError("This device does not need a PIN")
                if self.client.features.unlocked:
                    raise DeviceAlreadyUnlockedError(
                        "The PIN has already been sent to this device"
                    )
            return False
        elif isinstance(resp, messages.PassphraseRequest):
            pass_resp = self.client.call_raw(
                messages.PassphraseAck(
                    passphrase=self.client.ui.get_passphrase(available_on_device=False),
                    on_device=False,
                )
            )
            if isinstance(pass_resp, messages.Deprecated_PassphraseStateRequest):
                self.client.call_raw(messages.Deprecated_PassphraseStateAck())
        return True

    @trezor_exception
    def toggle_passphrase(self) -> bool:
        self._check_unlocked()
        try:
            device.apply_settings(
                self.client,
                use_passphrase=not self.client.features.passphrase_protection,
            )
        except Exception:
            if self.type == "Keepkey":
                print("Confirm the action by entering your PIN", file=sys.stderr)
                print(
                    "Use 'sendpin' to provide the number positions for the PIN as displayed on your device's screen",
                    file=sys.stderr,
                )
                print(PIN_MATRIX_DESCRIPTION, file=sys.stderr)
        return True


def enumerate(password: str = "") -> List[Dict[str, Any]]:
    results = []
    devs = hid.HidTransport.enumerate()
    devs.extend(webusb.WebUsbTransport.enumerate())
    devs.extend(udp.UdpTransport.enumerate())
    for dev in devs:
        d_data: Dict[str, Any] = {}

        d_data["type"] = "trezor"
        d_data["path"] = dev.get_path()

        client = None
        with handle_errors(common_err_msgs["enumerate"], d_data):
            client = TrezorClient(d_data["path"], password)
            try:
                client._prepare_device()
            except TypeError:
                continue
            if "trezor" not in client.client.features.vendor:
                continue

            d_data["model"] = "trezor_" + client.client.features.model.lower()
            if d_data["path"] == "udp:127.0.0.1:21324":
                d_data["model"] += "_simulator"

            d_data["needs_pin_sent"] = (
                client.client.features.pin_protection
                and not client.client.features.unlocked
            )
            if client.client.features.model == "1":
                d_data[
                    "needs_passphrase_sent"
                ] = (
                    client.client.features.passphrase_protection
                )  # always need the passphrase sent for Trezor One if it has passphrase protection enabled
            else:
                d_data["needs_passphrase_sent"] = False
            if d_data["needs_pin_sent"]:
                raise DeviceNotReadyError(
                    "Trezor is locked. Unlock by using 'promptpin' and then 'sendpin'."
                )
            if d_data["needs_passphrase_sent"] and not password:
                raise DeviceNotReadyError(
                    "Passphrase needs to be specified before the fingerprint information can be retrieved"
                )
            if client.client.features.initialized:
                d_data["fingerprint"] = client.get_master_fingerprint().hex()
                d_data[
                    "needs_passphrase_sent"
                ] = False  # Passphrase is always needed for the above to have worked, so it's already sent
            else:
                d_data["error"] = "Not initialized"
                d_data["code"] = DEVICE_NOT_INITIALIZED

        if client:
            client.close()

        results.append(d_data)
    return results
