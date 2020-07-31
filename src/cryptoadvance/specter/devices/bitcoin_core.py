import os, shutil
from mnemonic import Mnemonic
from hwilib.descriptor import AddChecksum
from ..device import Device
from ..helpers import (alias, convert_xpub_prefix,
                       encode_base58_checksum, decode_base58,
                       get_xpub_fingerprint)
from ..key import Key
from ..rpc import get_default_datadir
from io import BytesIO
import hmac

class BitcoinCore(Device):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        Device.__init__(self, name, alias, device_type, keys, fullpath, manager)
        self.hwi_support = False
        self.exportable_to_wallet = False
        self.hot_wallet = True

    def setup_device(self, mnemonic, passphrase, wallet_manager, testnet):
        seed = Mnemonic.to_seed(mnemonic)
        xprv = seed_to_hd_master_key(seed, testnet=testnet)
        wallet_name = os.path.join(wallet_manager.cli_path + '_hotstorage', self.alias)
        wallet_manager.cli.createwallet(wallet_name, False, True)
        cli = wallet_manager.cli.wallet(wallet_name)
        # TODO: Maybe more than 1000? Maybe add mechanism to add more later.
        ## NOTE: This will work only on the network the device was added, so hot devices should be filtered out by network.
        coin = int(testnet)
        cli.importmulti([
            { 'desc': AddChecksum('sh(wpkh({}/49h/{}h/0h/0/*))'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('sh(wpkh({}/49h/{}h/0h/1/*))'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('wpkh({}/84h/{}h/0h/0/*)'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('wpkh({}/84h/{}h/0h/1/*)'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('sh(wpkh({}/48h/{}h/0h/1h/0/*))'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('sh(wpkh({}/48h/{}h/0h/1h/1/*))'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('wpkh({}/48h/{}h/0h/2h/0/*)'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
            { 'desc': AddChecksum('wpkh({}/48h/{}h/0h/2h/1/*)'.format(xprv, coin)), 'range': 1000, 'timestamp': 'now'},
        ])
        if passphrase:
            cli.encryptwallet(passphrase)

        xpubs_str = ""
        paths = [
            "m", # to get fingerprint
            f"m/49h/{coin}h/0h", # nested
            f"m/84h/{coin}h/0h", # native
            f"m/48h/{coin}h/0h/1h", # nested multisig
            f"m/48h/{coin}h/0h/2h", # native multisig
        ]
        xpubs = derive_xpubs_from_xprv(xprv, paths, wallet_manager.cli)
        # it's not parent fingerprint, it's self fingerprint
        master_fpr = get_xpub_fingerprint(xpubs[0]).hex()

        if not testnet:
            # Nested Segwit
            xpub = xpubs[1]
            ypub = convert_xpub_prefix(xpub, b'\x04\x9d\x7c\xb2')
            xpubs_str += "[%s/49'/0'/0']%s\n" % (master_fpr, ypub)
            # native Segwit
            xpub = xpubs[2]
            zpub = convert_xpub_prefix(xpub, b'\x04\xb2\x47\x46')
            xpubs_str += "[%s/84'/0'/0']%s\n" % (master_fpr, zpub)
            # Multisig nested Segwit
            xpub = xpubs[3]
            Ypub = convert_xpub_prefix(xpub, b'\x02\x95\xb4\x3f')
            xpubs_str += "[%s/48'/0'/0'/1']%s\n" % (master_fpr, Ypub)
            # Multisig native Segwit
            xpub = xpubs[4]
            Zpub = convert_xpub_prefix(xpub, b'\x02\xaa\x7e\xd3')
            xpubs_str += "[%s/48'/0'/0'/2']%s\n" % (master_fpr, Zpub)
        else:
            # Testnet nested Segwit
            xpub = xpubs[1]
            upub = convert_xpub_prefix(xpub, b'\x04\x4a\x52\x62')
            xpubs_str += "[%s/49'/1'/0']%s\n" % (master_fpr, upub)
            # Testnet native Segwit
            xpub = xpubs[2]
            vpub = convert_xpub_prefix(xpub, b'\x04\x5f\x1c\xf6')
            xpubs_str += "[%s/84'/1'/0']%s\n" % (master_fpr, vpub)
            # Testnet multisig nested Segwit
            xpub = xpubs[3]
            Upub = convert_xpub_prefix(xpub, b'\x02\x42\x89\xef')
            xpubs_str += "[%s/48'/1'/0'/1']%s\n" % (master_fpr, Upub)
            # Testnet multisig native Segwit
            xpub = xpubs[4]
            Vpub = convert_xpub_prefix(xpub, b'\x02\x57\x54\x83')
            xpubs_str += "[%s/48'/1'/0'/2']%s\n" % (master_fpr, Vpub)

        keys, failed = Key.parse_xpubs(xpubs_str)
        if len(failed) > 0:
            # TODO: This should never occur, but just in case, 
            # we must make sure to catch it properly so it 
            # doesn't crash the app no matter what.
            raise Exception("Failed to parse these xpubs:\n" + "\n".join(failed))
        else:
            self.add_keys(keys)

    def _load_wallet(self, wallet_manager):
        existing_wallets = [w["name"] for w in wallet_manager.cli.listwalletdir()["wallets"]]
        loaded_wallets = wallet_manager.cli.listwallets()
        not_loaded_wallets = [w for w in existing_wallets if w not in loaded_wallets]
        if os.path.join(wallet_manager.cli_path + "_hotstorage", self.alias) in existing_wallets:
            if os.path.join(wallet_manager.cli_path + "_hotstorage", self.alias) in not_loaded_wallets:
                wallet_manager.cli.loadwallet(os.path.join(wallet_manager.cli_path + "_hotstorage", self.alias))

    def create_psbts(self, base64_psbt, wallet):
        return { 'core': base64_psbt }

    def sign_psbt(self, base64_psbt, wallet, passphrase):
        # Load the wallet if not loaded
        self._load_wallet(wallet.manager)
        cli = wallet.manager.cli.wallet(os.path.join(wallet.manager.cli_path + "_hotstorage", self.alias))
        if passphrase:
            cli.walletpassphrase(passphrase, 60)
        signed_psbt = cli.walletprocesspsbt(base64_psbt)
        if base64_psbt == signed_psbt['psbt']:
            raise Exception('Make sure you have entered the passphrase correctly.')
        if passphrase:
            cli.walletlock()
        return signed_psbt

    def delete(
        self,
        wallet_manager,
        bitcoin_datadir=get_default_datadir()
    ):
        try:
            wallet_cli_path = os.path.join(
                wallet_manager.cli_path + "_hotstorage", self.alias
            )
            cli = wallet_manager.cli.wallet(wallet_cli_path)
            cli.unloadwallet(wallet_cli_path)
            # Try deleting wallet file
            if bitcoin_datadir and os.path.exists(wallet_cli_path):
                shutil.rmtree(os.path.join(bitcoin_datadir, wallet_cli_path))
        except:
            pass # We tried...

# We need to copy it like this because HWI uses it as a dependency, but requires v0.18 which doesn't have this function.
def seed_to_hd_master_key(seed, testnet=False) -> str:
    """Converts 64-byte seed to xprv"""
    if len(seed) != 64:
        raise ValueError("Provided seed should have length of 64")

    # Compute HMAC-SHA512 of seed
    seed = hmac.new(b"Bitcoin seed", seed, digestmod='sha512').digest()

    # Serialization format can be found at: https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki#Serialization_format
    xprv = b"\x04\x88\xad\xe4"  # Version for private mainnet
    if testnet:
        xprv = b"\x04\x35\x83\x94"  # Version for private testnet
    xprv += b"\x00" * 9  # Depth, parent fingerprint, and child number
    xprv += seed[32:]  # Chain code
    xprv += b"\x00" + seed[:32]  # Master key

    return encode_base58_checksum(xprv)

def derive_xpubs_from_xprv(xprv, paths:list, cli):
    """
    Derives xpubs from root xprv and list of paths.
    Requires running BitcoinCLI instance to derive xpub from xprv
    """
    derived_xprvs = []
    for path in paths:
        derivation = parse_path(path)
        if len(derivation) == 0:
            # tuple: (parent, derived)
            derived_xprvs.append((None, xprv))
        else:
            # we need parent for fingerprint
            parent = xprv
            for idx in derivation[:-1]:
                parent = get_child(parent, idx)
            child = get_child(parent, derivation[-1])
            derived_xprvs.append((parent, child))
    xpubs = []
    for parent, child in derived_xprvs:
        res = cli.getdescriptorinfo(f"wpkh({child})")
        xpub = res["descriptor"].split("(")[1].split(")")[0]
        if parent is not None:
            res = cli.getdescriptorinfo(f"wpkh({parent})")
            parent_xpub = res["descriptor"].split("(")[1].split(")")[0]
            fingerprint = get_xpub_fingerprint(parent_xpub)
            xpub = swap_fingerprint(xpub, fingerprint)
        xpubs.append(xpub)
    return xpubs

def swap_fingerprint(xpub, fingerprint):
    """Replaces fingerprint in xpub"""
    raw = decode_base58(xpub)
    swapped = raw[:5]+fingerprint+raw[9:]
    return encode_base58_checksum(swapped)

# curve order
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141

def get_child(xprv, index):
    """Derives a child from xprv but without fingerprint information"""
    if index > 0xFFFFFFFF or index < 0:
        raise ValueError("Index should be between 0 and 2^32")
    if index < 0x80000000:
        raise ValueError("Can't do non-hardened")

    stream = BytesIO(decode_base58(xprv))
    version = stream.read(4)
    depth = stream.read(1)[0]
    fingerprint = stream.read(4)
    child_number = int.from_bytes(stream.read(4), 'big')
    chain_code = stream.read(32)
    stream.read(1)
    secret = stream.read(32)

    data = b'\x00' + secret + index.to_bytes(4, 'big')
    raw = hmac.new(chain_code, data, digestmod='sha512').digest()
    tweak = raw[:32]
    chain_code = raw[32:]

    new_secret = (int.from_bytes(secret, 'big') + int.from_bytes(tweak, 'big')) % N
    res = version+bytes([depth+1])+fingerprint+index.to_bytes(4, 'big')
    res += chain_code+b"\x00"+new_secret.to_bytes(32,'big')
    return encode_base58_checksum(res)

def parse_path(path: str) -> list:
    """
    Converts derivation path of the form 
    m/44h/1'/0'/0/32 to int array
    """
    arr = path.split("/")
    if arr[0] == "m":
        arr = arr[1:]
    if len(arr) == 0:
        return []
    if arr[-1] == "":
        # trailing slash
        arr = arr[:-1]
    for i, e in enumerate(arr):
        if e[-1] == "h" or e[-1] == "'":
            arr[i] = int(e[:-1])+0x80000000
        else:
            arr[i] = int(e)
    return arr
