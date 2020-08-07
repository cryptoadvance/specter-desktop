# Specter interaction script
from typing import Dict, Optional, Union
from hwilib.serializations import PSBT

from hwilib.hwwclient import HardwareWalletClient
from hwilib.errors import (ActionCanceledError, BadArgumentError, 
                           DeviceBusyError, DeviceFailureError, 
                           UnavailableActionError)
from hwilib.base58 import xpub_main_2_test
from hwilib import base58

import serial
import serial.tools.list_ports
import socket, time

class SpecterClient(HardwareWalletClient):
    """Create a client for a HID device that has already been opened.

    This abstract class defines the methods
    that hardware wallet subclasses should implement.
    """
    # timeout large enough to handle xpub derivations
    TIMEOUT = 3
    def __init__(self, path: str, password:str="", expert:bool=False) -> None:
        super().__init__(path, password, expert)
        self.simulator = (":" in path)
        if self.simulator:
            self.dev = SpecterSimulator(path)
        else:
            self.dev = SpecterUSBDevice(path)

    def query(self, data: str, timeout:Optional[float] = None) -> str:
        """Send a text-based query to the device and get back the response"""
        res = self.dev.query(data, timeout)
        if res == "error: User cancelled":
            raise ActionCanceledError("User didn't confirm action")
        elif res.startswith("error: Unknown command"):
            raise UnavailableActionError(res[7:])
        elif res.startswith("error: "):
            raise BadArgumentError(res[7:])
        return res

    def get_master_fingerprint_hex(self) -> str:
        """Return the master public key fingerprint as hex-string."""
        return self.query("fingerprint", timeout=self.TIMEOUT)

    def get_pubkey_at_path(self, bip32_path: str) -> Dict[str, str]:
        """Return the public key at the BIP32 derivation path.

        Return {"xpub": <xpub string>}.
        """
        # this should be fast
        xpub = self.query("xpub %s" % bip32_path, timeout=self.TIMEOUT)
        # Specter returns xpub with a prefix 
        # for a network currently selected on the device
        if self.is_testnet:
            return {'xpub': xpub_main_2_test(xpub)}
        else:
            return {'xpub': xpub_test_2_main(xpub)}

    def sign_tx(self, psbt: PSBT) -> Dict[str, str]:
        """Sign a partially signed bitcoin transaction (PSBT).

        Return {"psbt": <base64 psbt string>}.
        """
        # this one can hang for quite some time
        signed_tx = self.query("sign %s" % psbt.serialize())
        return {'psbt': signed_tx}

    def sign_message(self, message: str, bip32_path: str) -> Dict[str, str]:
        """Sign a message (bitcoin message signing).

        Sign the message according to the bitcoin message signing standard.

        Retrieve the signing key at the specified BIP32 derivation path.

        Return {"signature": <base64 signature string>}.
        """
        sig = self.query('signmessage %s %s' % (bip32_path, message))
        return {"signature": sig}

    def display_address(
        self,
        bip32_path: str,
        p2sh_p2wpkh: bool,
        bech32: bool,
        redeem_script: Optional[str] = None,
    ) -> Dict[str, str]:
        """Display and return the address of specified type.

        redeem_script is a hex-string.

        Retrieve the public key at the specified BIP32 derivation path.

        Return {"address": <base58 or bech32 address string>}.
        """
        script_type = "pkh" if redeem_script is None else "sh"
        if p2sh_p2wpkh:
            script_type = f"sh-w{script_type}"
        elif bech32:
            script_type = f"w{script_type}"
        # prepare a request of the form like
        # `showaddr sh-wsh m/1h/2h/3 descriptor`
        request = f"showaddr {script_type} {bip32_path}"
        if redeem_script is not None:
            request += f" {redeem_script}"
        address = self.query(request)
        return {'address': address}

    def wipe_device(self) -> Dict[str, Union[bool, str, int]]:
        """Wipe the HID device.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def setup_device(
        self, label: str = "", passphrase: str = ""
    ) -> Dict[str, Union[bool, str, int]]:
        """Setup the HID device.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": str, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def restore_device(
        self, label: str = "", word_count: int = 24
    ) -> Dict[str, Union[bool, str, int]]:
        """Restore the HID device from mnemonic.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def backup_device(
        self, label: str = "", passphrase: str = ""
    ) -> Dict[str, Union[bool, str, int]]:
        """Backup the HID device.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def close(self) -> None:
        """Close the device."""
        # nothing to do here - we close on every query
        pass

    def prompt_pin(self) -> Dict[str, Union[bool, str, int]]:
        """Prompt for PIN.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def send_pin(self) -> Dict[str, Union[bool, str, int]]:
        """Send PIN.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    def toggle_passphrase(self) -> Dict[str, Union[bool, str, int]]:
        """Toggle passphrase.

        Must return a dictionary with the "success" key,
        possibly including also "error" and "code", e.g.:
        {"success": bool, "error": srt, "code": int}.

        Raise UnavailableActionError if appropriate for the device.
        """
        raise NotImplementedError("The SpecterClient class "
                                  "does not implement this method")

    ############ extra functions Specter supports ############

    def get_random(self, num_bytes:int=32):
        if num_bytes < 0 or num_bytes > 10000:
            raise BadArgumentError("We can only get up to 10k bytes of random data")
        res = self.query("getrandom %d" % num_bytes)
        return bytes.fromhex(res)

    def import_wallet(self, name:str, descriptor:str):
        # TODO: implement
        pass


def enumerate(password=''):
    """
    Returns a list of detected Specter devices 
    with their fingerprints and client's paths
    """
    results = []
    # find ports with micropython's VID
    ports = [port.device for port 
                         in serial.tools.list_ports.comports()
                         if is_micropython(port)]
    try:
        # check if there is a simulator on port 8789
        # and we can connect to it
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 8789))
        s.close()
        ports.append("127.0.0.1:8789")
    except:
        pass

    for port in ports:
        # for every port try to get a fingerprint
        try:
            path = port
            data = {
                'type': 'specter',
                'model': 'specter-diy',
                'path': path,
                'needs_passphrase': False
            }
            client = SpecterClient(path)
            data['fingerprint'] = client.get_master_fingerprint_hex()
            client.close()
            results.append(data)
        except:
            pass
    return results

############# Helper functions and base classes ##############

def xpub_test_2_main(xpub: str) -> str:
    data = base58.decode(xpub)
    main_data = b'\x04\x88\xb2\x1e' + data[4:-4]
    checksum = base58.hash256(main_data)[0:4]
    return base58.encode(main_data + checksum)

def is_micropython(port):
    return "VID:PID=F055:" in port.hwid.upper()

class SpecterBase:
    """Class with common constants and command encoding"""
    EOL = b"\r\n"
    ACK = b"ACK"
    ACK_TIMOUT = 1
    def prepare_cmd(self, data):
        """
        Prepends command with 2*EOL and appends EOL at the end.
        Double EOL in the beginning makes sure all pending data
        will be cleaned up.
        """
        return self.EOL*2 + data.encode('utf-8') + self.EOL

class SpecterUSBDevice(SpecterBase):
    """
    Base class for USB device.
    Implements a simple query command over serial
    """
    def __init__(self, path):
        self.ser = serial.Serial(baudrate=115200, timeout=30)
        self.ser.port = path

    def read_until(self, eol, timeout=None):
        t0 = time.time()
        res = b""
        while not (eol in res):
            try:
                raw = self.ser.read(1)
                res += raw
            except Exception as e:
                time.sleep(0.01)
            if timeout is not None and time.time() > t0+timeout:
                self.ser.close()
                raise DeviceBusyError("Timeout")
        return res

    def query(self, data, timeout=None):
        # non blocking
        self.ser.timeout = 0
        self.ser.open()
        self.ser.write(self.prepare_cmd(data))
        # first we should get ACK
        res = self.read_until(self.EOL, self.ACK_TIMOUT)[:-len(self.EOL)]
        # then we should get the data itself
        if res != self.ACK:
            self.ser.close()
            raise DeviceBusyError("Device didn't return ACK")
        res = self.read_until(self.EOL, timeout)[:-len(self.EOL)]
        self.ser.close()
        return res.decode()

class SpecterSimulator(SpecterBase):
    """
    Base class for the simulator.
    Implements a simple query command over tcp/ip socket
    """
    def __init__(self, path):
        arr = path.split(":")
        self.sock_settings = (arr[0], int(arr[1]))

    def read_until(self, s, eol, timeout=None):
        t0 = time.time()
        res = b""
        while not (eol in res):
            try:
                raw = s.recv(1)
                res += raw
            except Exception as e:
                time.sleep(0.01)
            if timeout is not None and time.time() > t0+timeout:
                s.close()
                raise DeviceBusyError("Timeout")
        return res

    def query(self, data, timeout=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.sock_settings)
        s.send(self.prepare_cmd(data))
        s.setblocking(False)
        # we will get ACK right away
        res = self.read_until(s, self.EOL, self.ACK_TIMOUT)[:-len(self.EOL)]
        if res != self.ACK:
            raise DeviceBusyError("Device didn't return ACK")
        # fetch with required timeout
        res = self.read_until(s, self.EOL, timeout)[:-len(self.EOL)]
        s.close()
        return res.decode()
