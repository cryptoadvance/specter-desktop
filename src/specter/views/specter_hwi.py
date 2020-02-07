# Specter interaction script

from hwilib.hwwclient import HardwareWalletClient
from hwilib.errors import ActionCanceledError, BadArgumentError, DeviceBusyError, DeviceFailureError, UnavailableActionError, common_err_msgs, handle_errors
from hwilib.base58 import get_xpub_fingerprint, xpub_main_2_test
from hwilib import base58

import serial
import serial.tools.list_ports
import socket, time

def xpub_test_2_main(xpub: str) -> str:
    data = base58.decode(xpub)
    main_data = b'\x04\x88\xb2\x1e' + data[4:-4]
    checksum = base58.hash256(main_data)[0:4]
    return base58.encode(main_data + checksum)

def is_micropython(port):
    return "VID:PID=F055:" in port.hwid.upper()

# This class extends the HardwareWalletClient for Specter-specific things
class SpecterClient(HardwareWalletClient):

    def __init__(self, path, password=''):
        super().__init__(path, password)
        self.simulator = (":" in path)
        if self.simulator:
            arr = path.split(":")
            self.sock_settings = (arr[0], int(arr[1]))
        else:
            self.ser = serial.Serial(baudrate=115200, timeout=30)
            self.ser.port = path

    def query(self, data, timeout=None):
        if self.simulator:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.sock_settings)
            s.send((data+'\r\n').encode('utf-8'))
            s.setblocking(False)
            res = ""
            t0 = time.time()
            while not ("\r\n" in res):
                try:
                    raw = s.recv(10)
                    res += raw.decode("utf-8")
                except Exception as e:
                    time.sleep(0.1)
                if timeout is not None and time.time() > t0+timeout:
                    s.close()
                    raise DeviceBusyError("Timeout")
            s.close()
            res = res[:-2]
        else:
            self.ser.timeout=timeout
            self.ser.open()
            self.ser.write((data+'\r').encode('utf-8'))
            res = self.ser.read_until(b'\r').decode('utf-8')[:-1]
            self.ser.close()
        if res == 'user cancel':
            raise ActionCanceledError("User didn't confirm action")
        if "error" in res:
            raise BadArgumentError(res)
        return res

    def get_fingerprint(self):
        return self.query("fingerprint")

    # Must return a dict with the xpub
    # Retrieves the public key at the specified BIP 32 derivation path
    def get_pubkey_at_path(self, path):
        path = path.replace('\'', 'h')
        path = path.replace('H', 'h')
        xpub = self.query("xpub %s" % path)
        if self.is_testnet:
            return {'xpub': xpub_main_2_test(xpub)}
        else:
            return {'xpub': xpub_test_2_main(xpub)}

    # Must return a hex string with the signed transaction
    # The tx must be in the combined unsigned transaction format
    def sign_tx(self, tx):
        signed_tx = self.query("sign %s" % tx.serialize())
        return {'psbt': signed_tx}

    # Must return a base64 encoded string with the signed message
    # The message can be any string. keypath is the bip 32 derivation path for the key to sign with
    def sign_message(self, message, keypath):
        keypath = keypath.replace('\'', 'h')
        keypath = keypath.replace('H', 'h')

        sig = self.query('signmessage %s %s' % (keypath, message))
        return {"signature": sig}

    # Display address of specified type on the device. Only supports single-key based addresses.
    def display_address(self, keypath, p2sh_p2wpkh, bech32):
        keypath = keypath.replace('\'', 'h')
        keypath = keypath.replace('H', 'h')

        if p2sh_p2wpkh:
            fmt = "sh-wpkh %s"
        elif bech32:
            fmt = "wpkh %s"
        else:
            fmt = "pkh %s"
        address = self.query("showaddr %s" % (fmt % keypath))
        return {'address': address}

    # Setup a new device
    def setup_device(self, label='', passphrase=''):
        raise UnavailableActionError('Specter does not support software setup')

    # Wipe this device
    def wipe_device(self):
        raise UnavailableActionError('Specter does not support wiping via software')

    # Restore device from mnemonic or xprv
    def restore_device(self, label=''):
        raise UnavailableActionError('Specter does not support restoring via software')

    # Begin backup process
    def backup_device(self, label='', passphrase=''):
        raise UnavailableActionError('Specter does not support backups')

    # Close the device
    def close(self):
        # nothing to do here - we close on every query
        pass

    # Prompt pin
    def prompt_pin(self):
        raise UnavailableActionError('Specter does not need a PIN sent from the host')

    # Send pin
    def send_pin(self, pin):
        raise UnavailableActionError('Specter does not need a PIN sent from the host')

def enumerate(password=''):
    results = []
    ports = [port.device for port in serial.tools.list_ports.comports() if is_micropython(port)]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 8789))
        s.close()
        ports.append("127.0.0.1:8789")
    except:
        pass

    for port in ports:
        try:
            path = port
            data = {
                'type': 'specter',
                'model': 'specter-diy',
                'path': path,
                'needs_passphrase': False
            }
            client = SpecterClient(path)
            data['fingerprint'] = client.get_fingerprint()
            client.close()
            results.append(data)
        except:
            pass
    return results
