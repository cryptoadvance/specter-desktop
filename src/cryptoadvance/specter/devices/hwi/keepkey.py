"""
Keepkey
*******
"""

from hwilib.errors import (
    DEVICE_NOT_INITIALIZED,
    DeviceNotReadyError,
    common_err_msgs,
    handle_errors,
)
from hwilib.devices.trezorlib import protobuf as p
from hwilib.devices.trezorlib.transport import (
    hid,
    udp,
    webusb,
)
from .trezor import TrezorClient, HID_IDS, WEBUSB_IDS
from hwilib.devices.trezorlib.messages import (
    DebugLinkState,
    Features,
    HDNodeType,
    ResetDevice,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
)

py_enumerate = enumerate  # Need to use the enumerate built-in but there's another function already named that

KEEPKEY_HID_IDS = {(0x2B24, 0x0001)}
KEEPKEY_WEBUSB_IDS = {(0x2B24, 0x0002)}

HID_IDS.update(KEEPKEY_HID_IDS)
WEBUSB_IDS.update(KEEPKEY_WEBUSB_IDS)


class KeepkeyFeatures(Features):  # type: ignore
    def __init__(
        self,
        *,
        firmware_variant: Optional[str] = None,
        firmware_hash: Optional[bytes] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.firmware_variant = firmware_variant
        self.firmware_hash = firmware_hash

    @classmethod
    def get_fields(cls) -> Dict[int, p.FieldInfo]:
        return {
            1: ("vendor", p.UnicodeType, None),
            2: ("major_version", p.UVarintType, None),
            3: ("minor_version", p.UVarintType, None),
            4: ("patch_version", p.UVarintType, None),
            5: ("bootloader_mode", p.BoolType, None),
            6: ("device_id", p.UnicodeType, None),
            7: ("pin_protection", p.BoolType, None),
            8: ("passphrase_protection", p.BoolType, None),
            9: ("language", p.UnicodeType, None),
            10: ("label", p.UnicodeType, None),
            12: ("initialized", p.BoolType, None),
            13: ("revision", p.BytesType, None),
            14: ("bootloader_hash", p.BytesType, None),
            15: ("imported", p.BoolType, None),
            16: ("unlocked", p.BoolType, None),
            21: ("model", p.UnicodeType, None),
            22: ("firmware_variant", p.UnicodeType, None),
            23: ("firmware_hash", p.BytesType, None),
            24: ("no_backup", p.BoolType, None),
            25: ("wipe_code_protection", p.BoolType, None),
        }


class KeepkeyResetDevice(ResetDevice):  # type: ignore
    def __init__(
        self,
        *,
        auto_lock_delay_ms: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.auto_lock_delay_ms = auto_lock_delay_ms

    @classmethod
    def get_fields(cls) -> Dict[int, p.FieldInfo]:
        return {
            1: ("display_random", p.BoolType, None),
            2: ("strength", p.UVarintType, 256),  # default=256
            3: ("passphrase_protection", p.BoolType, None),
            4: ("pin_protection", p.BoolType, None),
            5: ("language", p.UnicodeType, "en-US"),  # default=en-US
            6: ("label", p.UnicodeType, None),
            7: ("no_backup", p.BoolType, None),
            8: ("auto_lock_delay_ms", p.UVarintType, None),
            9: ("u2f_counter", p.UVarintType, None),
        }


class KeepkeyDebugLinkState(DebugLinkState):  # type: ignore
    def __init__(
        self,
        *,
        recovery_cipher: Optional[str] = None,
        recovery_auto_completed_word: Optional[str] = None,
        firmware_hash: Optional[bytes] = None,
        storage_hash: Optional[bytes] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.recovery_cipher = recovery_cipher
        self.recovery_auto_completed_word = recovery_auto_completed_word
        self.firmware_hash = firmware_hash
        self.storage_hash = storage_hash

    @classmethod
    def get_fields(cls) -> Dict[int, p.FieldType]:
        return {
            1: ("layout", p.BytesType, None),
            2: ("pin", p.UnicodeType, None),
            3: ("matrix", p.UnicodeType, None),
            4: ("mnemonic_secret", p.BytesType, None),
            5: ("node", HDNodeType, None),
            6: ("passphrase_protection", p.BoolType, None),
            7: ("reset_word", p.UnicodeType, None),
            8: ("reset_entropy", p.BytesType, None),
            9: ("recovery_fake_word", p.UnicodeType, None),
            10: ("recovery_word_pos", p.UVarintType, None),
            11: ("recovery_cipher", p.UnicodeType, None),
            12: ("recovery_auto_completed_word", p.UnicodeType, None),
            13: ("firmware_hash", p.BytesType, None),
            14: ("storage_hash", p.BytesType, None),
        }


class KeepkeyClient(TrezorClient):
    def __init__(self, path: str, password: str = "", expert: bool = False) -> None:
        """
        The `KeepkeyClient` is a `HardwareWalletClient` for interacting with the Keepkey.
        As Keepkeys are clones of the Trezor 1, please refer to `TrezorClient` for documentation.
        """
        super(KeepkeyClient, self).__init__(path, password, expert)
        self.type = "Keepkey"
        self.client.vendors = "keepkey.com"
        self.client.minimum_versions = {"K1-14AM": (0, 0, 0)}
        self.client.map_type_to_class_override[
            KeepkeyFeatures.MESSAGE_WIRE_TYPE
        ] = KeepkeyFeatures
        self.client.map_type_to_class_override[
            KeepkeyResetDevice.MESSAGE_WIRE_TYPE
        ] = KeepkeyResetDevice
        if self.simulator:
            self.client.debug.map_type_to_class_override[
                KeepkeyDebugLinkState.MESSAGE_WIRE_TYPE
            ] = KeepkeyDebugLinkState


def enumerate(password: str = "") -> List[Dict[str, Any]]:
    results = []
    devs = hid.HidTransport.enumerate(usb_ids=KEEPKEY_HID_IDS)
    devs.extend(webusb.WebUsbTransport.enumerate(usb_ids=KEEPKEY_WEBUSB_IDS))
    devs.extend(udp.UdpTransport.enumerate())
    for dev in devs:
        d_data: Dict[str, Any] = {}

        d_data["type"] = "keepkey"
        d_data["model"] = "keepkey"
        d_data["path"] = dev.get_path()

        client = None

        with handle_errors(common_err_msgs["enumerate"], d_data):
            client = KeepkeyClient(d_data["path"], password)
            try:
                client.client.refresh_features()
            except TypeError:
                continue
            if "keepkey" not in client.client.features.vendor:
                continue

            if d_data["path"] == "udp:127.0.0.1:21324":
                d_data["model"] += "_simulator"

            d_data["needs_pin_sent"] = (
                client.client.features.pin_protection
                and not client.client.features.unlocked
            )
            d_data[
                "needs_passphrase_sent"
            ] = (
                client.client.features.passphrase_protection
            )  # always need the passphrase sent for Keepkey if it has passphrase protection enabled
            if d_data["needs_pin_sent"]:
                raise DeviceNotReadyError(
                    "Keepkey is locked. Unlock by using 'promptpin' and then 'sendpin'."
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
