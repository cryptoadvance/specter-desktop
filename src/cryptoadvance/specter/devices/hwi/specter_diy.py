"""
Hardware Wallet Client Interface
********************************

The :class:`SpecterClient` is the class to communicate with Specter-DIY hardware wallet.
"""

import serial
import serial.tools.list_ports
import socket, time
from hwilib.hwwclient import *
from hwilib.errors import (
    ActionCanceledError,
    BadArgumentError,
    DeviceBusyError,
    DeviceFailureError,
    UnavailableActionError,
)
import hashlib
from binascii import a2b_base64, b2a_base64

py_enumerate = enumerate


class SpecterClient(HardwareWalletClient):
    """Create a client for a HID device that has already been opened.

    This abstract class defines the methods
    that hardware wallet subclasses should implement.
    """

    # timeout large enough to handle xpub derivations
    TIMEOUT = 3

    def __init__(self, path: str, password: str = "", expert: bool = False) -> None:
        """
        :param path: Path to the device as returned by :func:`~hwilib.commands.enumerate`
        :param password: A password/passphrase to use with the device.
            Typically a BIP 39 passphrase, but not always.
            See device specific documentation for further details.
        :param expert: Whether to return additional information intended for experts.
        """
        super().__init__(path, password, expert)
        self.simulator = ":" in path
        if self.simulator:
            self.dev = SpecterSimulator(path)
        else:
            self.dev = SpecterUSBDevice(path)

    def query(self, data: str, timeout: Optional[float] = None) -> str:
        """Send a text-based query to the device and get back the response"""
        res = self.dev.query(data, timeout)
        if res == "error: User cancelled":
            raise ActionCanceledError("User didn't confirm action")
        elif res.startswith("error: Unknown command"):
            raise UnavailableActionError(res[7:])
        elif res.startswith("error: "):
            raise BadArgumentError(res[7:])
        return res

    def get_master_fingerprint(self) -> bytes:
        """
        Get the master public key fingerprint as bytes.

        Retrieves the fingerprint of the master public key of a device.
        Typically implemented by fetching the extended public key at "m/0h"
        and extracting the parent fingerprint from it.

        :return: The fingerprint as bytes
        """
        return bytes.fromhex(self.query("fingerprint", timeout=self.TIMEOUT))

    def get_master_blinding_key(self) -> str:
        """
        Get the master blinding key as WIF string (according to SLIP77 format).

        :return: The master blinding key as WIF string
        """
        return self.query("slip77")

    def get_pubkey_at_path(self, bip32_path: str) -> ExtendedKey:
        """
        Get the public key at the BIP 32 derivation path.

        :param bip32_path: The BIP 32 derivation path
        :return: The extended public key
        """
        # this should be fast
        xpub = self.query("xpub %s" % bip32_path, timeout=self.TIMEOUT)
        hd = ExtendedKey.deserialize(xpub)
        # Specter returns xpub with a prefix
        # for a network currently selected on the device
        hd.version = (
            b"\x04\x88\xb2\x1e" if self.chain == Chain.MAIN else b"\x04\x35\x87\xcf"
        )
        return hd

    def sign_b64psbt(self, psbt: str) -> str:
        # works with both PSBT and PSET
        print("sign %s" % psbt)
        return self.query("sign %s" % psbt)

    def sign_tx(self, psbt: PSBT) -> PSBT:
        """
        Sign a partially signed bitcoin transaction (PSBT).

        :param psbt: The PSBT to sign
        :return: The PSBT after being processed by the hardware wallet
        """
        response = self.query("sign %s" % psbt.serialize())
        signed_psbt = PSBT()
        signed_psbt.deserialize(response)
        # adding partial sigs to initial tx
        for i in range(len(psbt.inputs)):
            for k in signed_psbt.inputs[i].partial_sigs:
                psbt.inputs[i].partial_sigs[k] = signed_psbt.inputs[i].partial_sigs[k]
        return psbt

    def sign_message(self, message: Union[str, bytes], bip32_path: str) -> str:
        """
        Sign a message (bitcoin message signing).

        Signs a message using the legacy Bitcoin Core signed message format.
        The message is signed with the key at the given path.

        :param message: The message to be signed. First encoded as bytes if not already.
        :param bip32_path: The BIP 32 derivation for the key to sign the message with.
        :return: The signature
        """
        # convert message to bytes
        msg = message
        if isinstance(message, str):
            msg = message.encode("utf-8")
        # check if ascii - we only support ascii characters display
        try:
            msg.decode("ascii")
            fmt = "ascii"
        except:
            fmt = "base64"
        # check if there is \r or \n in the message
        # in this case we need to encode to base64
        if b"\r" in msg or b"\n" in msg:
            fmt = "base64"
        # convert to base64 if necessary
        if fmt == "base64":
            msg = b2a_base64(msg).strip()
        sig = self.query(f"signmessage {bip32_path} {fmt}:{msg.decode()}")
        return sig

    def display_singlesig_address(
        self,
        bip32_path: str,
        addr_type: AddressType,
    ) -> str:
        """
        Display and return the single sig address of specified type
        at the given derivation path.

        :param bip32_path: The BIP 32 derivation path to get the address for
        :param addr_type: The address type
        :return: The retrieved address also being shown by the device
        """
        if addr_type == AddressType.LEGACY:
            script_type = "pkh"
        elif addr_type == AddressType.SH_WIT:
            script_type = "sh-wpkh"
        elif addr_type == AddressType.WIT:
            script_type = "wpkh"
        else:
            raise BadArgumentError("Invalid address type")
        # prepare a request of the form like
        # `showaddr sh-wsh m/1h/2h/3 descriptor`
        request = f"showaddr {script_type} {bip32_path}"
        address = self.query(request)
        return address

    def display_multisig_address(
        self,
        addr_type: AddressType,
        multisig: MultisigDescriptor,
    ) -> str:
        """
        Display and return the multisig address of specified type given the descriptor.

        :param addr_type: The address type
        :param multisig: A :class:`~hwilib.descriptor.MultisigDescriptor` that describes the multisig to display.
        :return: The retrieved address also being shown by the device
        """
        # prepare a request of the form like
        # `showaddr sh-wsh m/1h/2h/3 descriptor`
        if addr_type == AddressType.LEGACY:
            script_type = "sh"
        elif addr_type == AddressType.SH_WIT:
            script_type = "sh-wsh"
        elif addr_type == AddressType.WIT:
            script_type = "wsh"
        else:
            raise BadArgumentError("Invalid address type")

        script, *_ = multisig.expand(0)
        bip32_path = (
            multisig.pubkeys[0].origin.to_string() + multisig.pubkeys[0].deriv_path
        )
        request = f"showaddr {script_type} {bip32_path} {script.hex()}"
        address = self.query(request)
        return address

    def close(self) -> None:
        # nothing to do for DIY
        pass

    ############ extra functions Specter supports ############

    def get_random(self, num_bytes: int = 32):
        if num_bytes < 0 or num_bytes > 10000:
            raise BadArgumentError("We can only get up to 10k bytes of random data")
        res = self.query("getrandom %d" % num_bytes)
        return bytes.fromhex(res)

    def import_wallet(self, name: str, descriptor: str):
        self.query("addwallet {name} {descriptor}")


def enumerate(password=""):
    """
    Returns a list of detected Specter devices
    with their fingerprints and client's paths
    """
    results = []
    # find ports with micropython's VID
    ports = [
        port.device
        for port in serial.tools.list_ports.comports()
        if is_micropython(port)
    ]
    try:
        # check if there is a simulator on port 8789
        # and we can connect to it
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 8789))
        s.close()
        ports.append("127.0.0.1:8789")
    except Exception as e:
        print(e)
        pass

    for port in ports:
        # for every port try to get a fingerprint
        try:
            path = port
            data: Dict[str, Any] = {}
            data["type"] = "specter"
            data["model"] = "specter-diy"
            data["path"] = path
            data["needs_pin_sent"] = False
            data["needs_passphrase_sent"] = False
            client = SpecterClient(path, "", False)
            data["fingerprint"] = client.get_master_fingerprint().hex()
            client.close()
            results.append(data)
        except Exception as e:
            print(e)
    return results


############# Helper functions and base classes ##############


def is_micropython(port):
    return "VID:PID=F055:" in port.hwid.upper()


class SpecterBase:
    """Class with common constants and command encoding"""

    EOL = b"\r\n"
    ACK = b"ACK"
    ACK_TIMOUT = 3

    def prepare_cmd(self, data):
        """
        Prepends command with 2*EOL and appends EOL at the end.
        Double EOL in the beginning makes sure all pending data
        will be cleaned up.
        """
        return self.EOL * 2 + data.encode("utf-8") + self.EOL


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
            if timeout is not None and time.time() > t0 + timeout:
                self.ser.close()
                raise DeviceBusyError("Timeout")
        return res

    def query(self, data, timeout=None):
        # non blocking
        self.ser.timeout = 0
        self.ser.open()
        self.ser.write(self.prepare_cmd(data))
        # first we should get ACK
        res = self.read_until(self.EOL, self.ACK_TIMOUT)[: -len(self.EOL)]
        # then we should get the data itself
        if res != self.ACK:
            self.ser.close()
            raise DeviceBusyError("Device didn't return ACK")
        res = self.read_until(self.EOL, timeout)[: -len(self.EOL)]
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
            if timeout is not None and time.time() > t0 + timeout:
                s.close()
                raise DeviceBusyError("Timeout")
        return res

    def query(self, data, timeout=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(self.sock_settings)
        s.send(self.prepare_cmd(data))
        s.setblocking(False)
        # we will get ACK right away
        res = self.read_until(s, self.EOL, self.ACK_TIMOUT)[: -len(self.EOL)]
        if res != self.ACK:
            raise DeviceBusyError("Device didn't return ACK")
        # fetch with required timeout
        res = self.read_until(s, self.EOL, timeout)[: -len(self.EOL)]
        s.close()
        return res.decode()


###### test for communication ######

if __name__ == "__main__":
    import sys

    devices = enumerate()
    if len(devices) == 0:
        print("No devices found")
        sys.exit()
    inp = 0
    if len(devices) > 1:
        print("Found %d devices." % len(devices))
        for i, dev in py_enumerate(devices):
            print(f"[{i}] {dev['path']} - {dev['fingerprint']}")
        inp = -1
        while True:
            inp = int(input("Enter the device number to use: "))
            if inp >= len(devices) or inp < 0:
                print("Meh... Try again.")
                continue
            break
    dev = SpecterClient(devices[inp]["path"])
    if len(sys.argv) == 1:
        mfp = dev.get_master_fingerprint().hex()
        derivation = "m/84h/0h/0h"
        xpub = dev.get_pubkey_at_path(derivation).to_string()
        print(f"Device fingerprint: {mfp}")
        print(f"Segwit xpub: {xpub}")
        print(f"Full key: [{mfp}{derivation[1:]}]{xpub}")
    else:
        if "-i" not in sys.argv:
            cmd = " ".join(sys.argv[1:])
            print("Running command:", cmd)
            print(dev.query(cmd))
        else:
            cmd = ""
            print("Interactive mode! Enter `quit` to exit.")
            while inp != "quit":
                cmd = input("Enter command to run: ")
                if cmd == "quit":
                    sys.exit(0)
                try:
                    print(dev.query(cmd))
                except Exception as e:
                    print("Error:", e)
