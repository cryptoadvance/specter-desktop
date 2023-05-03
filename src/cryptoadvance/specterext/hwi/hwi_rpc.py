import logging
import threading
from contextlib import contextmanager
from typing import Callable

import bitbox02
import hwilib.commands as hwi_commands
from embit import bip32
from embit.liquid import networks
from flask import current_app as app
from usb1 import USBError

from cryptoadvance.specter.devices import __all__ as device_classes
from cryptoadvance.specter.helpers import deep_update, is_liquid, is_testnet, locked

# deprecated, use embit.descriptor.checksum.add_checksum
from cryptoadvance.specter.util.descriptor import AddChecksum
from cryptoadvance.specter.util.json_rpc import JSONRPC
from cryptoadvance.specter.util.xpub import convert_xpub_prefix

from .helpers import hwi_get_config, save_hwi_bridge_config

logger = logging.getLogger(__name__)

hwi_classes = [cls for cls in device_classes if cls.hwi_support]

# use this lock for all hwi operations
hwilock = threading.Lock()


class AbstractHWIBridge(JSONRPC):
    def __init__(self):
        self.exposed_rpc = {
            "enumerate": self.enumerate,
            "detect_device": self.detect_device,
            "toggle_passphrase": self.toggle_passphrase,
            "prompt_pin": self.prompt_pin,
            "send_pin": self.send_pin,
            "extract_xpub": self.extract_xpub,
            "extract_xpubs": self.extract_xpubs,
            "display_address": self.display_address,
            "sign_tx": self.sign_tx,
            "sign_message": self.sign_message,
            "extract_master_blinding_key": self.extract_master_blinding_key,
            "bitbox02_pairing": self.bitbox02_pairing,
        }
        # Running enumerate after beginning an interaction with a specific device
        # crashes python or make HWI misbehave. For now we just get all connected
        # devices once per session and save them.
        logger.info(
            f"Initializing {self.__class__.__name__}..."
        )  # to explain user why it takes so long
        try:
            self.enumerate()
        except Exception as e:
            # We won't fail because of this
            logger.exception(e)

    def toggle_passphrase(self, device_type=None, path=None, passphrase="", chain=""):
        if device_type != "keepkey" and device_type != "trezor":
            raise Exception(
                "Invalid HWI device type %s, toggle_passphrase is only supported for Trezor and Keepkey devices"
                % device_type
            )

    def prompt_pin(self, device_type=None, path=None, passphrase="", chain=""):
        if device_type != "keepkey" and device_type != "trezor":
            raise Exception(
                "Invalid HWI device type %s, prompt_pin is only supported for Trezor and Keepkey devices"
                % device_type
            )

    def send_pin(self, pin="", device_type=None, path=None, passphrase="", chain=""):
        if device_type != "keepkey" and device_type != "trezor":
            raise Exception(
                "Invalid HWI device type %s, send_pin is only supported for Trezor and Keepkey devices"
                % device_type
            )
        else:
            if pin == "":
                raise Exception("Must enter a non-empty PIN")

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

    def bitbox02_pairing(self, chain=""):
        config = hwi_get_config(app.specter)
        return {"code": config.get("bitbox02_pairing_code", "")}

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
            self._enumerate()
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
