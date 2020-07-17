from hwilib.serializations import PSBT
import hwilib.commands as hwi_commands
from hwilib import bech32
from .helpers import convert_xpub_prefix, locked
from .specter_hwi import SpecterClient, enumerate as specter_enumerate
from .json_rpc import JSONRPC
import threading

# use this lock for all hwi operations
hwilock = threading.Lock()

class HWIBridge(JSONRPC):
    """
    A class that represents HWI JSON-RPC methods.

    All methods of this class are callable over JSON-RPC, except _underscored.
    """
    def __init__(self):
        self.exposed_rpc = {
            "enumerate": self.enumerate,
            "detect_device": self.detect_device,
            "toggle_passphrase": self.toggle_passphrase,
            "prompt_pin": self.prompt_pin,
            "send_pin": self.send_pin,
            "extract_xpubs": self.extract_xpubs,
            "display_address": self.display_address,
            "sign_tx": self.sign_tx
        }
        # Running enumerate after beginning an interaction with a specific device
        # crashes python or make HWI misbehave. For now we just get all connected
        # devices once per session and save them.
        self.enumerate()

    @locked(hwilock)
    def enumerate(self, passphrase='', chain=''):
        """
        Returns a list of all connected devices (dicts).
        Standard HWI enumerate() command + Specter.
        """
        self.devices = hwi_commands.enumerate(passphrase)
        self.devices += specter_enumerate(passphrase)
        for device in self.devices:
            client = self._get_client(device_type=device['type'], path=device['path'], passphrase=passphrase, chain=chain)
            try:
                 device['fingerprint'] = client.get_master_fingerprint_hex()
            except:
                pass
            if client:
                client.close()
        return self.devices
    
    def detect_device(self, device_type=None, path=None, fingerprint=None, rescan_devices=False):
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
            res = [dev for dev in self.devices if dev["type"].lower() == device_type.lower()]
        if fingerprint is not None:
            res = [dev for dev in self.devices if dev["fingerprint"].lower() == fingerprint.lower()]
        if path is not None:
            res = [dev for dev in self.devices if dev["path"] == path]
        if len(res) > 0:
            return res[0]

    @locked(hwilock)
    def toggle_passphrase(self, device_type=None, path=None, passphrase='', chain=''):
        if device_type == "keepkey" or device_type == "trezor":
            client = self._get_client(device_type=device_type, path=path, passphrase=passphrase, chain=chain)
            return hwi_commands.toggle_passphrase(client)
        else:
            raise Exception("Invalid HWI device type %s, toggle_passphrase is only supported for Trezor and Keepkey devices" % device_type)

    @locked(hwilock)
    def prompt_pin(self, device_type=None, path=None, passphrase='', chain=''):
        if device_type == "keepkey" or device_type == "trezor":
            # The device will randomize its pin entry matrix on the device
            #   but the corresponding digits in the receiving UI always map
            #   to:
            #       7 8 9
            #       4 5 6
            #       1 2 3
            client = self._get_client(device_type=device_type, path=path, passphrase=passphrase, chain=chain)
            return hwi_commands.prompt_pin(client)
        else:
            raise Exception("Invalid HWI device type %s, prompt_pin is only supported for Trezor and Keepkey devices" % device_type)

    @locked(hwilock)
    def send_pin(self, pin='', device_type=None, path=None, passphrase='', chain=''):
        if device_type == "keepkey" or device_type == "trezor":
            if pin == '':
                raise Exception("Must enter a non-empty PIN")
            client = self._get_client(device_type=device_type, path=path, passphrase=passphrase, chain=chain)
            return hwi_commands.send_pin(client, pin)
        else:
            raise Exception("Invalid HWI device type %s, send_pin is only supported for Trezor and Keepkey devices" % device_type)

    @locked(hwilock)
    def extract_xpubs(self, device_type=None, path=None, fingerprint=None, passphrase='', chain=''):
        client = self._get_client(device_type=device_type, fingerprint=fingerprint, path=path, passphrase=passphrase, chain=chain)
        xpubs = self._extract_xpubs_from_client(client)
        return xpubs

    @locked(hwilock)
    def display_address(self, descriptor='', device_type=None, path=None, fingerprint=None, passphrase='', chain=''):
        if descriptor == '':
            raise Exception("Descriptor must not be empty")

        client = self._get_client(device_type=device_type, fingerprint=fingerprint, path=path, passphrase=passphrase, chain=chain)
        try:
            status = hwi_commands.displayaddress(client, desc=descriptor)
            client.close()
            if 'error' in status:
                raise Exception(status['error'])
            elif 'address' in status:
                return status['address']
            else:
                raise Exception("Failed to validate address on device: Unknown Error")
        except Exception as e:
            if client:
                client.close()
            raise e

    @locked(hwilock)
    def sign_tx(self, psbt='', device_type=None, path=None, fingerprint=None, passphrase='', chain=''):
        if psbt == '':
            raise Exception("PSBT must not be empty")
        client = self._get_client(device_type=device_type, fingerprint=fingerprint, path=path, passphrase=passphrase, chain=chain)
        try:
            status = hwi_commands.signtx(client, psbt)
            client.close()
            if 'error' in status:
                raise Exception(status['error'])
            elif 'psbt' in status:
                return status['psbt']
            else:
                raise Exception("Failed to sign transaction with device: Unknown Error")
        except Exception as e:
            if client:
                client.close()
            raise e

    ######################## HWI Utils ########################
    def _get_client(self, device_type=None, path=None, fingerprint=None, passphrase='', chain=''):
            """
            Returns a hardware wallet class instance 
            with specific fingerprint or/and path
            or raises a not found error if not connected.
            If found multiple devices return only one.
            """
            # We do not use fingerprint in most cases since if the device is a trezor 
            # or a keepkey and passphrase is enabled but empty (an empty string like '')
            # The device will not return the fingerprint properly.
            device = self.detect_device(device_type=device_type, fingerprint=fingerprint, path=path)
            if device:
                if device["type"] == "specter":
                    client = SpecterClient(device["path"])
                else:
                    client = hwi_commands.get_client(device_type, path, passphrase)
                if not client:
                    raise Exception('The device was identified but could not be reached.  Please check it is properly connected and try again')
                client.is_testnet = chain != 'main'
                return client
            else:
                raise Exception('The device could not be found. Please check it is properly connected and try again')

    def _extract_xpubs_from_client(self, client):
        try:
            xpubs = ""
            # Client will be configured for testnet if our Specter instance is
            #   currently connected to testnet. This will prevent us from
            #   getting mainnet xpubs unless we set is_testnet here:
            client.is_testnet = False

            master_fpr = client.get_master_fingerprint_hex()

            # HWI calls to client.get_pubkey_at_path() return "xpub"-prefixed xpubs
            # regardless of derivation path. Update to match SLIP-0132 prefixes.
            # See:
            #   https://github.com/satoshilabs/slips/blob/master/slip-0132.md

            # Extract nested Segwit
            xpub = client.get_pubkey_at_path('m/49h/0h/0h')['xpub']
            ypub = convert_xpub_prefix(xpub, b'\x04\x9d\x7c\xb2')
            xpubs += "[%s/49'/0'/0']%s\n" % (master_fpr, ypub)

            # native Segwit
            xpub = client.get_pubkey_at_path('m/84h/0h/0h')['xpub']
            zpub = convert_xpub_prefix(xpub, b'\x04\xb2\x47\x46')
            xpubs += "[%s/84'/0'/0']%s\n" % (master_fpr, zpub)

            # Multisig nested Segwit
            xpub = client.get_pubkey_at_path('m/48h/0h/0h/1h')['xpub']
            Ypub = convert_xpub_prefix(xpub, b'\x02\x95\xb4\x3f')
            xpubs += "[%s/48'/0'/0'/1']%s\n" % (master_fpr, Ypub)

            # Multisig native Segwit
            xpub = client.get_pubkey_at_path('m/48h/0h/0h/2h')['xpub']
            Zpub = convert_xpub_prefix(xpub, b'\x02\xaa\x7e\xd3')
            xpubs += "[%s/48'/0'/0'/2']%s\n" % (master_fpr, Zpub)

            # And testnet
            client.is_testnet = True

            # Testnet nested Segwit
            xpub = client.get_pubkey_at_path('m/49h/1h/0h')['xpub']
            upub = convert_xpub_prefix(xpub, b'\x04\x4a\x52\x62')
            xpubs += "[%s/49'/1'/0']%s\n" % (master_fpr, upub)

            # Testnet native Segwit
            xpub = client.get_pubkey_at_path('m/84h/1h/0h')['xpub']
            vpub = convert_xpub_prefix(xpub, b'\x04\x5f\x1c\xf6')
            xpubs += "[%s/84'/1'/0']%s\n" % (master_fpr, vpub)

            # Testnet multisig nested Segwit
            xpub = client.get_pubkey_at_path('m/48h/1h/0h/1h')['xpub']
            Upub = convert_xpub_prefix(xpub, b'\x02\x42\x89\xef')
            xpubs += "[%s/48'/1'/0'/1']%s\n" % (master_fpr, Upub)

            # Testnet multisig native Segwit
            xpub = client.get_pubkey_at_path('m/48h/1h/0h/2h')['xpub']
            Vpub = convert_xpub_prefix(xpub, b'\x02\x57\x54\x83')
            xpubs += "[%s/48'/1'/0'/2']%s\n" % (master_fpr, Vpub)

            # Do proper cleanup otherwise have to reconnect device to access again
            client.close()
        except Exception as e:
            if client:
                client.close()
            raise e
        return xpubs
