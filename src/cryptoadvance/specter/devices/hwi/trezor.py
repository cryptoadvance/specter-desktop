# Trezor interaction script

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
from hwilib.devices.trezorlib.client import TrezorClient as Trezor
from hwilib.devices.trezorlib.debuglink import TrezorClientDebugLink
from hwilib.devices.trezorlib.exceptions import Cancelled
from hwilib.devices.trezorlib.transport import (
    enumerate_devices,
    get_transport,
    TREZOR_VENDOR_IDS,
)
from hwilib.devices.trezorlib.ui import (
    echo,
    PassphraseUI,
    mnemonic_words,
    PIN_CURRENT,
    PIN_NEW,
    PIN_CONFIRM,
    PIN_MATRIX_DESCRIPTION,
    prompt,
)
from hwilib.devices.trezorlib import tools, btc, device
from hwilib.devices.trezorlib import messages as proto
from hwilib.base58 import (
    encode as base58_encode,
    get_xpub_fingerprint,
    hash256,
    to_address,
    xpub_main_2_test,
)
from hwilib.serializations import (
    CTxOut,
    ExtendedKey,
    is_p2pkh,
    is_p2sh,
    is_p2wsh,
    is_witness,
    ser_uint256,
)
from hwilib import bech32
from usb1 import USBErrorNoDevice
from types import MethodType

import base64
import logging
import sys
import struct

# Need to use the enumerate built-in
# but there's another function already named that
py_enumerate = enumerate

# Only handles up to 15 of 15
def parse_multisig(script):
    if len(script) == 0:
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

        hd_node = proto.HDNodeType(
            depth=0,
            fingerprint=0,
            child_num=0,
            chain_code=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00",
            public_key=key,
        )
        pubkeys.append(proto.HDNodePathType(node=hd_node, address_n=[]))

    # Check things at the end
    n = script[offset] - 80
    if n != len(pubkeys):
        return (False, None)
    offset += 1
    op_cms = script[offset]
    if op_cms != 174:
        return (False, None)

    # Build MultisigRedeemScriptType and return it
    multisig = proto.MultisigRedeemScriptType(
        m=m, signatures=[b""] * n, pubkeys=pubkeys
    )
    return (True, multisig)


# Parses the PSBT_GLOBAL_XPUB fields of a PSBT as multisig pubkeys
def parse_multisig_xpubs(tx, psbt_in_out, multisig):
    try:
        old_pubs = [k.node.public_key for k in multisig.pubkeys]
        xpubs = [xpub for xpub in tx.unknown.keys() if xpub.startswith(b"\x01")]
        derivations = [tx.unknown[xpub] for xpub in xpubs]
        # unpack
        derivations = [
            list(struct.unpack("<" + "I" * (len(value) // 4), value))
            for value in derivations
        ]
        new_pubs = []
        for pub in old_pubs:
            # derivation
            der = list(psbt_in_out.hd_keypaths[pub])
            for i, derivation in py_enumerate(derivations):
                if der[0] == derivation[0]:
                    idx = i
                    for i in range(len(derivation)):
                        if der[i] != derivation[i]:
                            # derivations mismatch
                            return multisig
                    break
            xpub = xpubs[idx][1:]
            address_n = der[len(derivations[idx]) :]
            xpub_obj = ExtendedKey()
            xpub_obj.deserialize(base58_encode(xpub + hash256(xpub)[:4]))
            hd_node = proto.HDNodeType(
                depth=xpub_obj.depth,
                fingerprint=der[0],
                child_num=xpub_obj.child_num,
                chain_code=xpub_obj.chaincode,
                public_key=xpub_obj.pubkey,
            )
            new_pub = proto.HDNodePathType(node=hd_node, address_n=address_n)
            new_pubs.append(new_pub)
        return proto.MultisigRedeemScriptType(
            m=multisig.m, signatures=multisig.signatures, pubkeys=new_pubs
        )
    except:
        # If not all necessary data is available or malformatted, return the original multisig
        return multisig


def trezor_exception(f):
    def func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            raise BadArgumentError(str(e))
        except Cancelled:
            raise ActionCanceledError("{} canceled".format(f.__name__))
        except USBErrorNoDevice:
            raise DeviceConnectionError("Device disconnected")

    return func


def interactive_get_pin(self, code=None):
    if code == PIN_CURRENT:
        desc = "current PIN"
    elif code == PIN_NEW:
        desc = "new PIN"
    elif code == PIN_CONFIRM:
        desc = "new PIN again"
    else:
        desc = "PIN"

    echo(PIN_MATRIX_DESCRIPTION)

    while True:
        pin = prompt("Please enter {}".format(desc), hide_input=True)
        if not pin.isdigit():
            echo("Non-numerical PIN provided, please try again")
        else:
            return pin


# This class extends the HardwareWalletClient for Trezor specific things
class TrezorClient(HardwareWalletClient):
    def __init__(self, path, password="", expert=False):
        super(TrezorClient, self).__init__(path, password, expert)
        self.simulator = False
        if path.startswith("udp"):
            logging.debug("Simulator found, using DebugLink")
            transport = get_transport(path)
            self.client = TrezorClientDebugLink(transport=transport)
            self.simulator = True
            self.client.set_passphrase(password)
        else:
            self.client = Trezor(
                transport=get_transport(path), ui=PassphraseUI(password)
            )

        # if it wasn't able to find a client, throw an error
        if not self.client:
            raise IOError("no Device")

        self.password = password
        self.type = "Trezor"

    def _check_unlocked(self):
        self.coin_name = "Testnet" if self.is_testnet else "Bitcoin"
        self.client.init_device()
        if self.client.features.model == "T":
            self.client.ui.disallow_passphrase()
        if self.client.features.pin_protection and not self.client.features.pin_cached:
            raise DeviceNotReadyError(
                "{} is locked. Unlock by using 'promptpin' and then 'sendpin'.".format(
                    self.type
                )
            )

    # Must return a dict with the xpub
    # Retrieves the public key at the specified BIP 32 derivation path
    @trezor_exception
    def get_pubkey_at_path(self, path):
        self._check_unlocked()
        try:
            expanded_path = tools.parse_path(path)
        except ValueError as e:
            raise BadArgumentError(str(e))
        output = btc.get_public_node(
            self.client, expanded_path, coin_name=self.coin_name
        )
        if self.is_testnet:
            result = {"xpub": xpub_main_2_test(output.xpub)}
        else:
            result = {"xpub": output.xpub}
        if self.expert:
            xpub_obj = ExtendedKey()
            xpub_obj.deserialize(output.xpub)
            result.update(xpub_obj.get_printable_dict())
        return result

    # Must return a hex string with the signed transaction
    # The tx must be in the psbt format
    @trezor_exception
    def sign_tx(self, tx):
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
                txinputtype = proto.TxInputType()

                # Set the input stuff
                txinputtype.prev_hash = ser_uint256(txin.prevout.hash)[::-1]
                txinputtype.prev_index = txin.prevout.n
                txinputtype.sequence = txin.nSequence

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
                        txinputtype.script_type = proto.InputScriptType.SPENDP2SHWITNESS
                    else:
                        txinputtype.script_type = proto.InputScriptType.SPENDWITNESS
                else:
                    txinputtype.script_type = proto.InputScriptType.SPENDADDRESS
                txinputtype.amount = utxo.nValue

                # Check if P2WSH
                p2wsh = False
                if is_p2wsh(scriptcode):
                    # Look up witnessscript
                    if len(psbt_in.witness_script) == 0:
                        continue
                    scriptcode = psbt_in.witness_script
                    p2wsh = True

                def ignore_input():
                    txinputtype.address_n = [
                        0x80000000 | 84,
                        0x80000000 | (1 if self.is_testnet else 0),
                    ]
                    txinputtype.multisig = None
                    txinputtype.script_type = proto.InputScriptType.SPENDWITNESS
                    inputs.append(txinputtype)
                    to_ignore.append(input_num)

                # Check for multisig
                is_ms, multisig = parse_multisig(scriptcode)
                if is_ms:
                    txinputtype.multisig = parse_multisig_xpubs(tx, psbt_in, multisig)
                    if not is_wit:
                        if utxo.is_p2sh:
                            txinputtype.script_type = (
                                proto.InputScriptType.SPENDMULTISIG
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
                    if keypath[0] == master_fp:
                        if (
                            key in psbt_in.partial_sigs
                        ):  # This key already has a signature
                            found_in_sigs = True
                            continue
                        if (
                            not found
                        ):  # This key does not have a signature and we don't have a key to sign with yet
                            txinputtype.address_n = keypath[1:]
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
            if self.is_testnet:
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
                txoutput = proto.TxOutputType()
                txoutput.amount = out.nValue
                txoutput.script_type = proto.OutputScriptType.PAYTOADDRESS
                if out.is_p2pkh():
                    txoutput.address = to_address(out.scriptPubKey[3:23], p2pkh_version)
                elif out.is_p2sh():
                    txoutput.address = to_address(out.scriptPubKey[2:22], p2sh_version)
                else:
                    wit, ver, prog = out.is_witness()
                    if wit:
                        txoutput.address = bech32.encode(bech32_hrp, ver, prog)
                    else:
                        raise BadArgumentError("Output is not an address")

                # Add the derivation path for change
                psbt_out = tx.outputs[i]
                for _, keypath in psbt_out.hd_keypaths.items():
                    if keypath[0] == master_fp:
                        wit, ver, prog = out.is_witness()
                        if out.is_p2pkh():
                            txoutput.address_n = keypath[1:]
                            txoutput.address = None
                        elif wit:
                            txoutput.script_type = proto.OutputScriptType.PAYTOWITNESS
                            txoutput.address_n = keypath[1:]
                            txoutput.address = None
                        elif out.is_p2sh() and psbt_out.redeem_script:
                            wit, ver, prog = CTxOut(
                                0, psbt_out.redeem_script
                            ).is_witness()
                            if wit and len(prog) == 20:
                                txoutput.script_type = (
                                    proto.OutputScriptType.PAYTOP2SHWITNESS
                                )
                                txoutput.address_n = keypath[1:]
                                txoutput.address = None
                        is_ms, multisig = parse_multisig(
                            psbt_out.witness_script if wit else psbt_out.redeem_script
                        )
                        if is_ms:
                            txoutput.multisig = parse_multisig_xpubs(
                                tx, psbt_out, multisig
                            )
                # append to outputs
                outputs.append(txoutput)

            # Prepare prev txs
            prevtxs = {}
            for psbt_in in tx.inputs:
                if psbt_in.non_witness_utxo:
                    prev = psbt_in.non_witness_utxo

                    t = proto.TransactionType()
                    t.version = prev.nVersion
                    t.lock_time = prev.nLockTime

                    for vin in prev.vin:
                        i = proto.TxInputType()
                        i.prev_hash = ser_uint256(vin.prevout.hash)[::-1]
                        i.prev_index = vin.prevout.n
                        i.script_sig = vin.scriptSig
                        i.sequence = vin.nSequence
                        t.inputs.append(i)

                    for vout in prev.vout:
                        o = proto.TxOutputBinType()
                        o.amount = vout.nValue
                        o.script_pubkey = vout.scriptPubKey
                        t.bin_outputs.append(o)
                    logging.debug(psbt_in.non_witness_utxo.hash)
                    prevtxs[ser_uint256(psbt_in.non_witness_utxo.sha256)[::-1]] = t

            # Sign the transaction
            tx_details = proto.SignTx()
            tx_details.version = tx.tx.nVersion
            tx_details.lock_time = tx.tx.nLockTime
            signed_tx = btc.sign_tx(
                self.client, self.coin_name, inputs, outputs, tx_details, prevtxs
            )

            # Each input has one signature
            for input_num, (psbt_in, sig) in py_enumerate(
                list(zip(tx.inputs, signed_tx[0]))
            ):
                if input_num in to_ignore:
                    continue
                for pubkey in psbt_in.hd_keypaths.keys():
                    fp = psbt_in.hd_keypaths[pubkey][0]
                    if fp == master_fp and pubkey not in psbt_in.partial_sigs:
                        psbt_in.partial_sigs[pubkey] = sig + b"\x01"
                        break

            p += 1

        return {"psbt": tx.serialize()}

    # Must return a base64 encoded string with the signed message
    # The message can be any string
    @trezor_exception
    def sign_message(self, message, keypath):
        self._check_unlocked()
        path = tools.parse_path(keypath)
        result = btc.sign_message(self.client, self.coin_name, path, message)
        return {"signature": base64.b64encode(result.signature).decode("utf-8")}

    # Display address of specified type on the device.
    @trezor_exception
    def display_address(
        self, keypath, p2sh_p2wpkh, bech32, redeem_script=None, descriptor=None
    ):
        self._check_unlocked()

        # descriptor means multisig with xpubs
        if descriptor:
            pubkeys = []
            xpub = ExtendedKey()
            for i in range(0, descriptor.multisig_N):
                xpub.deserialize(descriptor.base_key[i])
                hd_node = proto.HDNodeType(
                    depth=xpub.depth,
                    fingerprint=int.from_bytes(xpub.parent_fingerprint, "big"),
                    child_num=xpub.child_num,
                    chain_code=xpub.chaincode,
                    public_key=xpub.pubkey,
                )
                pubkeys.append(
                    proto.HDNodePathType(
                        node=hd_node,
                        address_n=tools.parse_path("m" + descriptor.path_suffix[i]),
                    )
                )
            multisig = proto.MultisigRedeemScriptType(
                m=int(descriptor.multisig_M),
                signatures=[b""] * int(descriptor.multisig_N),
                pubkeys=pubkeys,
            )  # redeem_script means p2sh/multisig
        elif redeem_script:
            # Get multisig object required by Trezor's get_address
            multisig = parse_multisig(bytes.fromhex(redeem_script))
            if not multisig[0]:
                raise BadArgumentError(
                    "The redeem script provided is not a multisig. Only multisig scripts can be displayed."
                )
            multisig = multisig[1]
        else:
            multisig = None

        # Script type
        if p2sh_p2wpkh:
            script_type = proto.InputScriptType.SPENDP2SHWITNESS
        elif bech32:
            script_type = proto.InputScriptType.SPENDWITNESS
        elif redeem_script:
            script_type = proto.InputScriptType.SPENDMULTISIG
        else:
            script_type = proto.InputScriptType.SPENDADDRESS

        # convert device fingerprint to 'm' if exists in path
        keypath = keypath.replace(self.get_master_fingerprint_hex(), "m")

        for path in keypath.split(","):
            if len(path.split("/")[0]) == 8:
                path = path.split("/", 1)[1]
            expanded_path = tools.parse_path(path)

            try:
                address = btc.get_address(
                    self.client,
                    self.coin_name,
                    expanded_path,
                    show_display=True,
                    script_type=script_type,
                    multisig=multisig,
                )
                return {"address": address}
            except:
                pass

        raise BadArgumentError("No path supplied matched device keys")

    # Setup a new device
    @trezor_exception
    def setup_device(self, label="", passphrase=""):
        self.client.init_device()
        if not self.simulator:
            # Use interactive_get_pin
            self.client.ui.get_pin = MethodType(interactive_get_pin, self.client.ui)

        if self.client.features.initialized:
            raise DeviceAlreadyInitError(
                "Device is already initialized. Use wipe first and try again"
            )
        device.reset(self.client, passphrase_protection=bool(self.password))
        return {"success": True}

    # Wipe this device
    @trezor_exception
    def wipe_device(self):
        self._check_unlocked()
        device.wipe(self.client)
        return {"success": True}

    # Restore device from mnemonic or xprv
    @trezor_exception
    def restore_device(self, label="", word_count=24):
        self.client.init_device()
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
        return {"success": True}

    # Begin backup process
    def backup_device(self, label="", passphrase=""):
        raise UnavailableActionError(
            "The {} does not support creating a backup via software".format(self.type)
        )

    # Close the device
    @trezor_exception
    def close(self):
        self.client.close()

    # Prompt for a pin on device
    @trezor_exception
    def prompt_pin(self):
        self.coin_name = "Testnet" if self.is_testnet else "Bitcoin"
        self.client.open()
        self.client.init_device()
        if not self.client.features.pin_protection:
            raise DeviceAlreadyUnlockedError("This device does not need a PIN")
        if self.client.features.pin_cached:
            raise DeviceAlreadyUnlockedError(
                "The PIN has already been sent to this device"
            )
        print(
            "Use 'sendpin' to provide the number positions for the PIN as displayed on your device's screen",
            file=sys.stderr,
        )
        print(PIN_MATRIX_DESCRIPTION, file=sys.stderr)
        self.client.call_raw(
            proto.GetPublicKey(
                address_n=[0x8000002C, 0x80000001, 0x80000000],
                ecdsa_curve_name=None,
                show_display=False,
                coin_name=self.coin_name,
                script_type=proto.InputScriptType.SPENDADDRESS,
            )
        )
        return {"success": True}

    # Send the pin
    @trezor_exception
    def send_pin(self, pin):
        self.client.open()
        if not pin.isdigit():
            raise BadArgumentError("Non-numeric PIN provided")
        resp = self.client.call_raw(proto.PinMatrixAck(pin=pin))
        if isinstance(resp, proto.Failure):
            self.client.features = self.client.call_raw(proto.GetFeatures())
            if isinstance(self.client.features, proto.Features):
                if not self.client.features.pin_protection:
                    raise DeviceAlreadyUnlockedError("This device does not need a PIN")
                if self.client.features.pin_cached:
                    raise DeviceAlreadyUnlockedError(
                        "The PIN has already been sent to this device"
                    )
            return {"success": False}
        return {"success": True}

    # Toggle passphrase
    @trezor_exception
    def toggle_passphrase(self):
        self._check_unlocked()
        try:
            device.apply_settings(
                self.client,
                use_passphrase=not self.client.features.passphrase_protection,
            )
        except:
            if self.type == "Keepkey":
                print("Confirm the action by entering your PIN", file=sys.stderr)
                print(
                    "Use 'sendpin' to provide the number positions for the PIN as displayed on your device's screen",
                    file=sys.stderr,
                )
                print(PIN_MATRIX_DESCRIPTION, file=sys.stderr)
        return {"success": True}


def enumerate(password=""):
    results = []
    for dev in enumerate_devices():
        # enumerate_devices filters to Trezors and Keepkeys.
        # Only allow Trezors and unknowns. Unknown devices will reach the check for vendor later
        if dev.get_usb_vendor_id() not in TREZOR_VENDOR_IDS | {-1}:
            continue
        d_data = {}

        d_data["type"] = "trezor"
        d_data["path"] = dev.get_path()

        client = None
        with handle_errors(common_err_msgs["enumerate"], d_data):
            client = TrezorClient(d_data["path"], password)
            client.client.init_device()
            if "trezor" not in client.client.features.vendor:
                continue

            d_data["model"] = "trezor_" + client.client.features.model.lower()
            if d_data["path"] == "udp:127.0.0.1:21324":
                d_data["model"] += "_simulator"

            d_data["needs_pin_sent"] = (
                client.client.features.pin_protection
                and not client.client.features.pin_cached
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
                d_data["fingerprint"] = client.get_master_fingerprint_hex()
                # Passphrase is always needed for the above to have worked,
                # so it's already sent
                d_data["needs_passphrase_sent"] = False
            else:
                d_data["error"] = "Not initialized"
                d_data["code"] = DEVICE_NOT_INITIALIZED

        if client:
            client.close()

        results.append(d_data)
    return results
