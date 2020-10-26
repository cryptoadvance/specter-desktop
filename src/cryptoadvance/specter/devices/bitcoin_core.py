import os
import shutil
from mnemonic import Mnemonic
from ..device import Device
from ..helpers import alias
from ..util.descriptor import AddChecksum
from ..util.base58 import encode_base58_checksum, decode_base58
from ..util.xpub import get_xpub_fingerprint, convert_xpub_prefix
from ..key import Key
from ..rpc import get_default_datadir
from io import BytesIO
import hmac
import logging

logger = logging.getLogger(__name__)


class BitcoinCore(Device):
    device_type = "bitcoincore"
    name = "Bitcoin Core (hot wallet)"

    hot_wallet = True

    def __init__(self, name, alias, keys, fullpath, manager):
        Device.__init__(self, name, alias, keys, fullpath, manager)

    def setup_device(self, file_password, wallet_manager):
        wallet_name = os.path.join(wallet_manager.rpc_path + "_hotstorage", self.alias)
        wallet_manager.rpc.createwallet(wallet_name, False, True)
        rpc = wallet_manager.rpc.wallet(wallet_name)
        if file_password:
            rpc.encryptwallet(file_password)

    def add_hot_wallet_keys(
        self,
        mnemonic,
        passphrase,
        paths,
        file_password,
        wallet_manager,
        testnet,
        keys_range=[0, 1000],
    ):
        seed = Mnemonic.to_seed(mnemonic, passphrase)
        xprv = seed_to_hd_master_key(seed, testnet=testnet)
        # Load the wallet if not loaded
        self._load_wallet(wallet_manager)
        rpc = wallet_manager.rpc.wallet(
            os.path.join(wallet_manager.rpc_path + "_hotstorage", self.alias)
        )
        if file_password:
            rpc.walletpassphrase(file_password, 60)
        rpc.importmulti(
            [
                {
                    "desc": AddChecksum(
                        "sh(wpkh({}{}/0/*))".format(xprv, path.replace("m", ""))
                    ),
                    "range": keys_range,
                    "timestamp": "now",
                }
                for path in paths
            ]
            + [
                {
                    "desc": AddChecksum(
                        "sh(wpkh({}{}/1/*))".format(xprv, path.replace("m", ""))
                    ),
                    "range": keys_range,
                    "timestamp": "now",
                }
                for path in paths
            ],
            {"rescan": False},
        )

        xpubs_str = ""
        paths = ["m"] + paths
        xpubs = derive_xpubs_from_xprv(xprv, paths, wallet_manager.rpc)
        # it's not parent fingerprint, it's self fingerprint
        master_fpr = get_xpub_fingerprint(xpubs[0]).hex()

        slip132_paths = [
            "m/49'/0'/0'",
            "m/84'/0'/0'",
            "m/48'/0'/0'/1'",
            "m/48'/0'/0'/2'",
            "m/49'/1'/0'",
            "m/84'/1'/0'",
            "m/48'/1'/0'/1'",
            "m/48'/1'/0'/2'",
        ]
        slip132_prefixes = [
            b"\x04\x9d\x7c\xb2",
            b"\x04\xb2\x47\x46",
            b"\x02\x95\xb4\x3f",
            b"\x02\xaa\x7e\xd3",
            b"\x04\x4a\x52\x62",
            b"\x04\x5f\x1c\xf6",
            b"\x02\x42\x89\xef",
            b"\x02\x57\x54\x83",
        ]
        for i in range(1, len(paths)):
            path = paths[i]
            xpub = xpubs[i]
            slip132_prefix = None
            for j, slip132_path in enumerate(slip132_paths):
                if path.replace("h", "'").startswith(slip132_path):
                    slip132_prefix = slip132_prefixes[j]
                    break
            if slip132_prefix:
                xpub = convert_xpub_prefix(xpub, slip132_prefix)
            xpubs_str += "[{}{}]{}\n".format(master_fpr, path.replace("m", ""), xpub)

        keys, failed = Key.parse_xpubs(xpubs_str)
        if len(failed) > 0:
            # TODO: This should never occur, but just in case,
            # we must make sure to catch it properly so it
            # doesn't crash the app no matter what.
            raise Exception("Failed to parse these xpubs:\n" + "\n".join(failed))
        else:
            self.add_keys(keys)

    def _load_wallet(self, wallet_manager):
        try:
            existing_wallets = [
                w["name"] for w in wallet_manager.rpc.listwalletdir()["wallets"]
            ]
        except:
            existing_wallets = None
        loaded_wallets = wallet_manager.rpc.listwallets()

        hotstorage_path = wallet_manager.rpc_path + "_hotstorage"
        wallet_path = os.path.join(hotstorage_path, self.alias)
        if existing_wallets is None or wallet_path in existing_wallets:
            if wallet_path not in loaded_wallets:
                wallet_manager.rpc.loadwallet(wallet_path)

    def is_encrypted(self, wallet_manager):
        """Check if the wallet is encrypted"""
        self._load_wallet(wallet_manager)
        hotstorage_path = wallet_manager.rpc_path + "_hotstorage"
        wallet_path = os.path.join(hotstorage_path, self.alias)
        try:
            # check if password is enabled
            info = wallet_manager.rpc.getwalletinfo(wallet=wallet_path)
            return "unlocked_until" in info
        except Exception as e:
            logger.warning("Cannot fetch hot wallet info")
        # Assuming encrypted by default
        return True

    def create_psbts(self, base64_psbt, wallet):
        return {"core": base64_psbt}

    def sign_psbt(self, base64_psbt, wallet, file_password):
        # Load the wallet if not loaded
        self._load_wallet(wallet.manager)
        rpc = wallet.manager.rpc.wallet(
            os.path.join(wallet.manager.rpc_path + "_hotstorage", self.alias)
        )
        if file_password:
            rpc.walletpassphrase(file_password, 60)
        signed_psbt = rpc.walletprocesspsbt(base64_psbt)
        if base64_psbt == signed_psbt["psbt"]:
            raise Exception(
                "Make sure you have entered the wallet file password correctly. (If your wallet is not encrypted submit empty password)"
            )
        if file_password:
            rpc.walletlock()
        return signed_psbt

    def delete(
        self, wallet_manager, bitcoin_datadir=get_default_datadir(), chain="main"
    ):
        try:
            wallet_rpc_path = os.path.join(
                wallet_manager.rpc_path + "_hotstorage", self.alias
            )
            wallet_manager.rpc.unloadwallet(wallet_rpc_path)
            # Try deleting wallet file
            if bitcoin_datadir:
                if chain != "main":
                    bitcoin_datadir = os.path.join(bitcoin_datadir, chain)
                candidates = [
                    os.path.join(bitcoin_datadir, wallet_rpc_path),
                    os.path.join(bitcoin_datadir, "wallets", wallet_rpc_path),
                ]
                for path in candidates:
                    if os.path.exists(path):
                        shutil.rmtree(path)
                        break
        except:
            pass  # We tried...


# We need to copy it like this because HWI uses it as a dependency,
# but requires v0.18 which doesn't have this function.


def seed_to_hd_master_key(seed, testnet=False) -> str:
    """Converts bip32 seed to xprv"""
    if len(seed) < 16 or len(seed) > 64:
        raise ValueError("Provided seed should be between 16 and 64 bytes")

    # Compute HMAC-SHA512 of seed
    seed = hmac.new(b"Bitcoin seed", seed, digestmod="sha512").digest()

    # Serialization format can be found at:
    # https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki#Serialization_format
    xprv = b"\x04\x88\xad\xe4"  # Version for private mainnet
    if testnet:
        xprv = b"\x04\x35\x83\x94"  # Version for private testnet
    xprv += b"\x00" * 9  # Depth, parent fingerprint, and child number
    xprv += seed[32:]  # Chain code
    xprv += b"\x00" + seed[:32]  # Master key

    return encode_base58_checksum(xprv)


def derive_xpubs_from_xprv(xprv, paths: list, rpc):
    """
    Derives xpubs from root xprv and list of paths.
    Requires running BitcoinRPC instance to derive xpub from xprv
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
                parent = get_child(parent, idx, rpc)
            child = get_child(parent, derivation[-1], rpc)
            derived_xprvs.append((parent, child))
    xpubs = []
    for parent, child in derived_xprvs:
        res = rpc.getdescriptorinfo(f"wpkh({child})")
        xpub = res["descriptor"].split("(")[1].split(")")[0]
        if parent is not None:
            res = rpc.getdescriptorinfo(f"wpkh({parent})")
            parent_xpub = res["descriptor"].split("(")[1].split(")")[0]
            fingerprint = get_xpub_fingerprint(parent_xpub)
            xpub = swap_fingerprint(xpub, fingerprint)
        xpubs.append(xpub)
    return xpubs


def swap_fingerprint(xpub, fingerprint):
    """Replaces fingerprint in xpub"""
    raw = decode_base58(xpub)
    swapped = raw[:5] + fingerprint + raw[9:]
    return encode_base58_checksum(swapped)


# curve order
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141


def get_child(xprv, index, rpc=None):
    """Derives a child from xprv but without fingerprint information"""
    if index > 0xFFFFFFFF or index < 0:
        raise ValueError("Index should be between 0 and 2^32")

    stream = BytesIO(decode_base58(xprv))
    version = stream.read(4)
    depth = stream.read(1)[0]
    fingerprint = stream.read(4)
    child_number = int.from_bytes(stream.read(4), "big")
    chain_code = stream.read(32)
    stream.read(1)
    secret = stream.read(32)
    key = b"\x00" + secret

    if index < 0x80000000:
        if rpc is None:
            raise ValueError("Can't do non-hardened without rpc")
        # non hardened - we need pubkey
        else:
            # convert to public
            res = rpc.getdescriptorinfo(f"wpkh({xprv})")
            xpub = res["descriptor"].split("(")[1].split(")")[0]
            # decode pubkey
            key = decode_base58(xpub)[-33:]

    data = key + index.to_bytes(4, "big")
    raw = hmac.new(chain_code, data, digestmod="sha512").digest()
    tweak = raw[:32]
    chain_code = raw[32:]

    new_secret = (int.from_bytes(secret, "big") + int.from_bytes(tweak, "big")) % N
    res = version + bytes([depth + 1]) + fingerprint + index.to_bytes(4, "big")
    res += chain_code + b"\x00" + new_secret.to_bytes(32, "big")
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
            arr[i] = int(e[:-1]) + 0x80000000
        else:
            arr[i] = int(e)
    return arr
