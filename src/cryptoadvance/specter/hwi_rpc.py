import logging
import threading
from contextlib import contextmanager
from typing import Callable

import hwilib.commands as hwi_commands
from embit import bip32
from embit.liquid import networks
from flask import current_app as app
from hwilib.common import Chain
from hwilib.errors import ActionCanceledError
from hwilib.devices.bitbox02 import Bitbox02Client
from hwilib.devices.bitbox02_lib.util import BitBoxAppNoiseConfig
from hwilib.devices.trezorlib.transport import get_transport
from hwilib.psbt import PSBT
from usb1 import USBError

from .devices import __all__ as device_classes
from .devices.hwi.jade import JadeClient
from .devices.hwi.specter_diy import SpecterClient
from .helpers import (
    deep_update,
    hwi_get_config,
    is_liquid,
    is_testnet,
    locked,
    save_hwi_bridge_config,
)

# deprecated, use embit.descriptor.checksum.add_checksum
from .util.descriptor import AddChecksum
from .util.json_rpc import JSONRPC
from .util.xpub import convert_xpub_prefix

logger = logging.getLogger(__name__)

hwi_classes = [cls for cls in device_classes if cls.hwi_support]

# use this lock for all hwi operations
hwilock = threading.Lock()


class BitBox02NoiseConfig(BitBoxAppNoiseConfig):
    def show_pairing(self, code: str, device_response: Callable[[], bool]) -> bool:
        config = hwi_get_config(app.specter)
        config["bitbox02_pairing_code"] = code
        save_hwi_bridge_config(app.specter, config)
        if not device_response():
            config["bitbox02_pairing_code"] = ""
            save_hwi_bridge_config(app.specter, config)
            return False
        config["bitbox02_pairing_code"] = ""
        save_hwi_bridge_config(app.specter, config)
        return True


def get_device_class(device_type):
    for cls in hwi_classes:
        if cls.device_type == device_type:
            return cls


class HWIBridge(JSONRPC):
    """
    A class that represents HWI JSON-RPC methods.

    All methods of this class are callable over JSON-RPC, except _underscored.
    """

    def __init__(self, skip_hwi_initialisation=False):
        self.exposed_rpc = {
            "enumerate": self.enumerate,
            "detect_device": self.detect_device,
            "toggle_passphrase": self.toggle_passphrase,
            "prompt_pin": self.prompt_pin,
            "send_pin": self.send_pin,
            "extract_xpub": self.extract_xpub,
            "extract_xpubs": self.extract_xpubs,
            "begin_xpub_authorization": self.begin_xpub_authorization,
            "end_xpub_authorization": self.end_xpub_authorization,
            "display_address": self.display_address,
            "sign_tx": self.sign_tx,
            "sign_message": self.sign_message,
            "extract_master_blinding_key": self.extract_master_blinding_key,
            "register_multisig": self.register_multisig,  # currently only Jade
            "bitbox02_pairing": self.bitbox02_pairing,
        }
        if skip_hwi_initialisation:
            self.is_startup = False
            self.devices = []
            return
        # Running enumerate after beginning an interaction with a specific device
        # crashes python or make HWI misbehave. For now we just get all connected
        # devices once per session and save them.
        logger.info("Initializing HWI...")
        self.is_startup = True  # to explain user why it takes so long
        self.enumerate()
        logger.info("Finished initializing HWI!")

    @locked(hwilock)
    def enumerate(self, passphrase="", chain=""):
        """
        Returns a list of all connected devices (dicts).
        Standard HWI enumerate() command + Specter.
        """
        devices = []
        # Call device-specific enumerate (can come from hwi lib or from the Specter code base) for each Specter device class
        for devcls in hwi_classes:
            try:
                # Special handling of the Jade to unsure it is not prompting to unlock the device on startup
                if devcls.__name__ == "Jade":
                    skip_unlocking = self.is_startup
                    client_chain = Chain.argparse(chain)  # This returns an enum member
                    devs = devcls.enumerate(
                        skip_unlocking=skip_unlocking, chain=client_chain
                    )
                else:
                    if passphrase:
                        devs = devcls.enumerate(passphrase)
                    else:
                        devs = devcls.enumerate()
                devices += devs
            except USBError as e:
                logger.warning(
                    f"an error {e} was thrown which might indicate that an USB device is connected, which is deferring the startup"
                )
                logger.warning(
                    f"Consider to unplug USB devices to speed up the boot process"
                )

        self.devices = devices
        self.is_startup = False
        return self.devices

    def detect_device(
        self, device_type=None, path=None, fingerprint=None, rescan_devices=False
    ):
        """
        Returns a hardware wallet details
        with specific fingerprint/ path/ type
        or None if not connected.
        If found multiple devices return only one.
        """
        if rescan_devices:
            self.enumerate()
        res = []

        if device_type is not None:
            res = [
                dev
                for dev in self.devices
                if dev["type"].lower() == device_type.lower()
            ]
        if fingerprint is not None:
            res = [
                dev
                for dev in self.devices
                if dev["fingerprint"].lower() == fingerprint.lower()
            ]
        if path is not None:
            res = [dev for dev in self.devices if dev["path"] == path]
        if len(res) > 0:
            return res[0]

    @locked(hwilock)
    def toggle_passphrase(self, device_type=None, path=None, passphrase="", chain=""):
        if device_type == "keepkey" or device_type == "trezor":
            with self._get_client(
                device_type=device_type, path=path, passphrase=passphrase, chain=chain
            ) as client:
                return hwi_commands.toggle_passphrase(client)
        else:
            raise Exception(
                "Invalid HWI device type %s, toggle_passphrase is only supported for Trezor and Keepkey devices"
                % device_type
            )

    @locked(hwilock)
    def prompt_pin(self, device_type=None, path=None, passphrase="", chain=""):
        if device_type == "keepkey" or device_type == "trezor":
            # The device will randomize its pin entry matrix on the device
            #   but the corresponding digits in the receiving UI always map
            #   to:
            #       7 8 9
            #       4 5 6
            #       1 2 3
            with self._get_client(
                device_type=device_type, path=path, passphrase=passphrase, chain=chain
            ) as client:
                return hwi_commands.prompt_pin(client)
        else:
            raise Exception(
                "Invalid HWI device type %s, prompt_pin is only supported for Trezor and Keepkey devices"
                % device_type
            )

    @locked(hwilock)
    def send_pin(self, pin="", device_type=None, path=None, passphrase="", chain=""):
        if device_type == "keepkey" or device_type == "trezor":
            if pin == "":
                raise Exception("Must enter a non-empty PIN")
            with self._get_client(
                device_type=device_type, path=path, passphrase=passphrase, chain=chain
            ) as client:
                logger.debug(f"client is : {client}")
                return hwi_commands.send_pin(client, pin)
        else:
            raise Exception(
                "Invalid HWI device type %s, send_pin is only supported for Trezor and Keepkey devices"
                % device_type
            )

    @locked(hwilock)
    def extract_xpubs(
        self,
        account=0,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            xpubs = self._extract_xpubs_from_client(client, account)
        return xpubs

    @locked(hwilock)
    def extract_xpub(
        self,
        derivation=None,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            # Client will be configured for testnet if our Specter instance is
            #   currently connected to testnet. This will prevent us from
            #   getting mainnet xpubs unless we set is_testnet here:
            der = bip32.parse_path(derivation)
            client.chain = (
                Chain.TEST if len(der) > 2 and der[1] == 0x80000001 else Chain.MAIN
            )

            network = networks.get_network(
                "main" if client.chain == Chain.MAIN else "test"
            )

            master_fpr = client.get_master_fingerprint().hex()

            try:
                xpub = client.get_pubkey_at_path(derivation).to_string()
                slip132_prefix = bip32.detect_version(
                    derivation, default="xpub", network=network
                )
                xpub = convert_xpub_prefix(xpub, slip132_prefix)
                if derivation == "m":
                    return "[{}]{}\n".format(master_fpr, xpub)
                return "[{}/{}]{}\n".format(master_fpr, derivation.split("m/")[1], xpub)
            except ActionCanceledError:
                # the user declined the export on the device - a None
                # return is the caller's "cancelled, stop quietly" signal
                logger.info("xpub export at %s cancelled on the device", derivation)
                return None
            except Exception:
                # the network-mismatch error and every real failure carry
                # something the user needs to see - propagate it so the
                # JSON-RPC error reaches the UI (handleHWIError() escapes
                # it before rendering) instead of vanishing into a log and
                # leaving the caller with an ambiguous None
                raise

    @locked(hwilock)
    def begin_xpub_authorization(
        self,
        paths=None,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        """
        Ask the device to authorize a whole set of xpub derivation ``paths``
        (all on the same network) with a single on-device confirmation,
        instead of one per subsequent extract_xpub() call. Currently only
        Specter-DIY supports this.

        Returns True if the device accepted the scope, False if this
        device/firmware doesn't support it or rejected it (e.g. wrong
        network) - callers should then just fall back to plain
        extract_xpub() calls, which work either way. A cancellation on the
        device propagates as an error, same as any other HWI call.

        Lifecycle note: begin_xpub_authorization / end_xpub_authorization
        are separate RPCs, and the HWI connection is reopened per call, so
        between them the authorization lives on the device on its own. It
        is deliberately narrow - RAM only, bound to the current network,
        limited to the exact confirmed paths, each consumable once, and
        dropped by the firmware on lock / re-init / network change. The
        residual exposure is: if the host process dies mid-batch, the
        still-unread authorized paths stay authorized until one of those
        events. Acceptable given the one-shot scope; a fully atomic
        server-side begin->reads->end (an extract_xpub_batch RPC) and/or a
        short firmware TTL for unused authorizations would close it and
        are worth a follow-up. The self-contained _extract_xpubs_from_
        client() path already wraps begin/end in try/finally within one
        RPC; only the new_device_keys.jinja "Get via USB" flow spans
        several.
        """
        if not paths:
            return False
        # Don't trust the caller (the browser builds this list from DOM
        # text, including user-entered custom derivations) to hand us
        # clean BIP32 paths. Parse and re-serialise each one canonically
        # here, at the RPC boundary, before it's joined into the firmware
        # scope string - a stray ";" or range expression must not be able
        # to ride in through a single list entry and widen the scope.
        ders = [bip32.parse_path(p) for p in paths]
        norm_paths = [bip32.path_to_str(d) for d in ders]
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            der = ders[0]
            client.chain = (
                Chain.TEST if len(der) > 2 and der[1] == 0x80000001 else Chain.MAIN
            )
            begin = getattr(client, "begin_xpub_authorization", None)
            if begin is None:
                return False
            return begin(norm_paths)

    @locked(hwilock)
    def end_xpub_authorization(
        self,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        """Release any xpub authorization left active on the device (best effort)."""
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            end = getattr(client, "end_xpub_authorization", None)
            if end is not None:
                end()
        return True

    @locked(hwilock)
    def display_address(
        self,
        descriptor="",
        xpubs_descriptor="",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        if descriptor == "" and xpubs_descriptor == "":
            raise Exception("Descriptor must not be empty")

        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            if xpubs_descriptor:
                status = hwi_commands.displayaddress(client, desc=xpubs_descriptor)
            else:
                status = hwi_commands.displayaddress(client, desc=descriptor)
            if "error" in status:
                raise Exception(status["error"])
            elif "address" in status:
                return status["address"]
            else:
                raise Exception("Failed to validate address on device: Unknown Error")

    @locked(hwilock)
    def register_multisig(
        self,
        device_type=None,
        path=None,
        passphrase="",
        fingerprint=None,
        descriptor="",
        chain="",
    ):
        if descriptor == "":
            raise Exception("Descriptor must not be empty")

        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            try:
                return client.register_multisig(descriptor)
            except Exception as e:
                logger.exception(e)
                raise Exception(
                    f"Failed to register multisig on the device. Error: {e}"
                )

    @locked(hwilock)
    def sign_tx(
        self,
        psbt="",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        if psbt == "":
            raise Exception("PSBT must not be empty")
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            if is_liquid(chain):
                if not hasattr(client, "sign_pset"):
                    raise Exception("Device can't sign liquid transaction")
                return client.sign_pset(psbt)
            status = hwi_commands.signtx(client, psbt)
            if "error" in status:
                raise Exception(status["error"])
            elif "psbt" in status:
                return status["psbt"]
            else:
                raise Exception("Failed to sign transaction with device: Unknown Error")

    @locked(hwilock)
    def sign_message(
        self,
        message="",
        derivation_path="m",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        if message == "":
            raise Exception("Message must not be empty")
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            status = hwi_commands.signmessage(client, message, derivation_path)
            if "error" in status:
                raise Exception(status["error"])
            elif "signature" in status:
                return status["signature"]
            else:
                raise Exception("Failed to sign message with device: Unknown Error")

    @locked(hwilock)
    def extract_master_blinding_key(
        self,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        with self._get_client(
            device_type=device_type,
            fingerprint=fingerprint,
            path=path,
            passphrase=passphrase,
            chain=chain,
        ) as client:
            try:
                return client.get_master_blinding_key()
            except Exception as e:
                logger.warning(
                    f"Failed to get the master blinding key from the device. Error: {e}"
                )
                logger.exception(e)

    def bitbox02_pairing(self, chain=""):
        config = hwi_get_config(app.specter)
        return {"code": config.get("bitbox02_pairing_code", "")}

    ######################## HWI Utils ########################
    @contextmanager
    def _get_client(
        self, device_type=None, path=None, fingerprint=None, passphrase="", chain=""
    ):
        """
        Returns a hardware wallet class instance
        with specific fingerprint or/and path
        or raises a not found error if not connected.
        If found multiple devices return only one.
        """
        # We do not use fingerprint in most cases since if the device is a trezor
        # or a keepkey and passphrase is enabled but empty (an empty string like '')
        # The device will not return the fingerprint properly.
        device = self.detect_device(
            device_type=device_type, fingerprint=fingerprint, path=path
        )
        if not device:
            raise Exception(
                "The device could not be found. Please check it is properly connected and try again"
            )
        devcls = get_device_class(device["type"])
        if devcls:
            # Jade needs the chain/network already here for the the auth_call
            if devcls.__name__ == "Jade":
                client_chain = Chain.argparse(chain)
                client = devcls.get_client(
                    path=device["path"],
                    password=passphrase,
                    expert=False,
                    chain=client_chain,
                )
            else:
                client = devcls.get_client(device["path"], passphrase)
        if not client:
            raise Exception(
                "The device was identified but could not be reached.  Please check it is properly connected and try again"
            )
        try:
            if type(client) is not JadeClient:
                client.chain = Chain.argparse(chain)
            yield client
        finally:
            client.close()

    def _extract_xpubs_from_client(self, client, account=0):
        try:
            xpubs = ""
            # Client will be configured for testnet if our Specter instance is
            #   currently connected to testnet. This will prevent us from
            #   getting mainnet xpubs unless we set is_testnet here:
            client.chain = Chain.MAIN

            master_fpr = client.get_master_fingerprint().hex()

            # HWI calls to client.get_pubkey_at_path() return "xpub"-prefixed xpubs
            # regardless of derivation path. Update to match SLIP-0132 prefixes.
            # See:
            #   https://github.com/satoshilabs/slips/blob/master/slip-0132.md

            mainnet_paths = [
                "m/49h/0h/{}h".format(account),
                "m/84h/0h/{}h".format(account),
                "m/48h/0h/{}h/1h".format(account),
                "m/48h/0h/{}h/2h".format(account),
            ]
            testnet_paths = [
                "m/49h/1h/{}h".format(account),
                "m/84h/1h/{}h".format(account),
                "m/48h/1h/{}h/1h".format(account),
                "m/48h/1h/{}h/2h".format(account),
            ]

            # Some devices (Specter-DIY) ask the user to confirm every single
            # xpub export on-device. Where the client supports it, authorize
            # the whole set of standard account paths with one scoped request:
            # the user confirms once instead of once per key, and - since the
            # device only authorizes a scope for the network it is currently
            # on - a rejection tells us the device is on the *other* network,
            # so we don't ask it (and prompt the user) for keys of a network
            # it isn't even set to. Clients without this run both groups with
            # the usual per-request flow, unchanged.
            begin_auth = getattr(client, "begin_xpub_authorization", None)
            fetch_mainnet = True
            fetch_testnet = True
            scoped = False
            if begin_auth is not None:
                client.chain = Chain.MAIN
                if begin_auth(mainnet_paths):
                    scoped = True
                    fetch_testnet = False
                else:
                    client.chain = Chain.TEST
                    if begin_auth(testnet_paths):
                        scoped = True
                        fetch_mainnet = False

            try:
                if fetch_mainnet:
                    client.chain = Chain.MAIN
                    # Nested Segwit
                    try:
                        xpub = client.get_pubkey_at_path(mainnet_paths[0]).to_string()
                        ypub = convert_xpub_prefix(xpub, b"\x04\x9d\x7c\xb2")
                        xpubs += "[{}/49'/0'/{}']{}\n".format(master_fpr, account, ypub)
                    except Exception as e:
                        logger.warning(
                            f"Failed to import Nested Segwit singlesig mainnet key. Error {e}"
                        )
                        logger.exception(e)

                    try:
                        # native Segwit
                        xpub = client.get_pubkey_at_path(mainnet_paths[1]).to_string()
                        zpub = convert_xpub_prefix(xpub, b"\x04\xb2\x47\x46")
                        xpubs += "[{}/84'/0'/{}']{}\n".format(master_fpr, account, zpub)
                    except Exception as e:
                        logger.warning(
                            f"Failed to import native Segwit singlesig mainnet key: {e}"
                        )
                        logger.exception(e)

                    try:
                        # Multisig nested Segwit
                        xpub = client.get_pubkey_at_path(mainnet_paths[2]).to_string()
                        Ypub = convert_xpub_prefix(xpub, b"\x02\x95\xb4\x3f")
                        xpubs += "[{}/48'/0'/{}'/1']{}\n".format(
                            master_fpr, account, Ypub
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to import Nested Segwit multisig mainnet key: {e}"
                        )
                        logger.exception(e)

                    try:
                        # Multisig native Segwit
                        xpub = client.get_pubkey_at_path(mainnet_paths[3]).to_string()
                        Zpub = convert_xpub_prefix(xpub, b"\x02\xaa\x7e\xd3")
                        xpubs += "[{}/48'/0'/{}'/2']{}\n".format(
                            master_fpr, account, Zpub
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to import native Segwit multisig mainnet key {e}"
                        )
                        logger.exception(e)

                if fetch_testnet:
                    client.chain = Chain.TEST
                    try:
                        # Testnet nested Segwit
                        xpub = client.get_pubkey_at_path(testnet_paths[0]).to_string()
                        upub = convert_xpub_prefix(xpub, b"\x04\x4a\x52\x62")
                        xpubs += "[{}/49'/1'/{}']{}\n".format(master_fpr, account, upub)
                    except Exception as e:
                        logger.warning(
                            f"Failed to import Nested Segwit singlesig testnet key: {e}"
                        )
                        logger.exception(e)

                    try:
                        # Testnet native Segwit
                        xpub = client.get_pubkey_at_path(testnet_paths[1]).to_string()
                        vpub = convert_xpub_prefix(xpub, b"\x04\x5f\x1c\xf6")
                        xpubs += "[{}/84'/1'/{}']{}\n".format(master_fpr, account, vpub)
                    except Exception as e:
                        logger.warning(
                            f"Failed to import native Segwit singlesig testnet key: {e}"
                        )
                        logger.exception(e)

                    try:
                        # Testnet multisig nested Segwit
                        xpub = client.get_pubkey_at_path(testnet_paths[2]).to_string()
                        Upub = convert_xpub_prefix(xpub, b"\x02\x42\x89\xef")
                        xpubs += "[{}/48'/1'/{}'/1']{}\n".format(
                            master_fpr, account, Upub
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to import Nested Segwit multisigsig testnet key: {e}"
                        )
                        logger.exception(e)

                    try:
                        # Testnet multisig native Segwit
                        xpub = client.get_pubkey_at_path(testnet_paths[3]).to_string()
                        Vpub = convert_xpub_prefix(xpub, b"\x02\x57\x54\x83")
                        xpubs += "[{}/48'/1'/{}'/2']{}\n".format(
                            master_fpr, account, Vpub
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to import native Segwit multisig testnet key: {e}"
                        )
                        logger.exception(e)
            finally:
                if scoped:
                    client.end_xpub_authorization()

            # Do proper cleanup otherwise have to reconnect device to access again
            client.close()
        except Exception as e:
            if client:
                client.close()
            raise e
        return xpubs
