import hmac
import logging
import os
import shutil
from io import BytesIO

from embit import bip32, bip39, networks

from ..device import Device
from ..helpers import alias
from ..key import Key
from ..rpc import get_default_datadir
from ..specter_error import SpecterError
from ..util.base58 import decode_base58, encode_base58_checksum
from ..util.descriptor import AddChecksum
from ..util.xpub import convert_xpub_prefix, get_xpub_fingerprint
from ..util.mnemonic import mnemonic_to_root
from . import DeviceTypes

logger = logging.getLogger(__name__)


class BitcoinCore(Device):
    device_type = DeviceTypes.BITCOINCORE
    name = "Bitcoin Core (hot wallet)"
    icon = "bitcoincore_icon.svg"

    hot_wallet = True
    taproot_support = True

    # default sighash to use
    SIGHASH = "ALL"

    def __init__(self, *args, **kwargs):
        self._use_descriptors = None
        super().__init__(*args, **kwargs)

    def setup_device(self, file_password, wallet_manager):
        wallet_name = os.path.join(wallet_manager.rpc_path + "_hotstorage", self.alias)
        core_version = wallet_manager.rpc.getnetworkinfo().get("version", 0)
        use_descriptors = core_version >= 210000
        if use_descriptors:
            # it could fail if Core is compiled without sqlite
            try:
                wallet_manager.rpc.createwallet(
                    wallet_name, False, True, file_password or "", False, True
                )
                self._use_descriptors = True
            except:
                wallet_manager.rpc.createwallet(
                    wallet_name, False, True, file_password or "", False, True
                )
                self.taproot_support = False
        else:
            wallet_manager.rpc.createwallet(
                wallet_name, False, True, file_password or ""
            )
        rpc = wallet_manager.rpc.wallet(wallet_name)

    def use_descriptors(self, rpc):
        if self._use_descriptors is None:
            self._use_descriptors = rpc.getwalletinfo().get("descriptors", False)
            if not self._use_descriptors:
                self.taproot_support = False
        return self._use_descriptors

    def taproot_available(self, rpc):
        try:
            # currently only master branch supports tr() descriptors
            # TODO: replace to 220000
            core_version = rpc.getnetworkinfo().get("version", 0)
            info = rpc.getblockchaininfo()
            taproot_active = (core_version >= 219900) and (
                info.get("softforks", {}).get("taproot", {}).get("active", False)
            )
            taproot_support = self.use_descriptors(rpc) and taproot_active
            self.taproot_support = taproot_support
            return taproot_support
        except Exception as e:
            self.taproot_support = False
            logger.exception(e)
            return False

    def add_hot_wallet_keys(
        self,
        mnemonic,
        passphrase,
        paths,
        file_password,
        wallet_manager,
        testnet,
        keys_range=[0, 1000],
        keys_purposes=[],
    ):
        if type(keys_range[0]) == str:
            keys_range[0] = int(keys_range[0])
        if type(keys_range[1]) == str:
            keys_range[1] = int(keys_range[1])
        root = mnemonic_to_root(mnemonic, passphrase)
        network = networks.NETWORKS["test" if testnet else "main"]
        root.version = network["xprv"]
        xprv = root.to_base58()
        # Load the wallet if not loaded
        self._load_wallet(wallet_manager)
        rpc = wallet_manager.rpc.wallet(
            os.path.join(wallet_manager.rpc_path + "_hotstorage", self.alias)
        )
        if file_password:
            rpc.walletpassphrase(file_password, 60)

        # check if we can use descriptors and taproot
        use_descriptors = self.use_descriptors(rpc)
        taproot_available = self.taproot_available(rpc)

        args = [
            {
                "desc": AddChecksum(
                    "{}({}{}/0/*)".format(
                        "tr"
                        if path.startswith("m/86h") and taproot_available
                        else "wpkh",
                        xprv,
                        path.rstrip("/").replace("m", ""),
                    )
                ),
                "range": keys_range,
                "timestamp": "now",
            }
            for path in paths
        ] + [
            {
                "desc": AddChecksum(
                    "{}({}{}/1/*)".format(
                        "tr"
                        if path.startswith("m/86h") and taproot_available
                        else "wpkh",
                        xprv,
                        path.rstrip("/").replace("m", ""),
                    )
                ),
                "range": keys_range,
                "timestamp": "now",
            }
            for path in paths
        ]

        if use_descriptors:
            rpc.importdescriptors(args, timeout=15)
        else:
            rpc.importmulti(args, {"rescan": False})

        xpubs = [root.derive(path).to_public().to_base58() for path in paths]
        # root fingerprint is fingerprint field of the first child
        master_fpr = root.child(0).fingerprint.hex()
        keys = []
        for i in range(len(paths)):
            try:
                path = paths[i]
                xpub = xpubs[i]
                # detect slip132 version for xpubs
                slip132_prefix = bip32.detect_version(
                    path, default="xpub", network=network
                )
                xpub = "[{}{}]{}\n".format(
                    master_fpr,
                    path.replace("m", ""),
                    convert_xpub_prefix(xpub, slip132_prefix),
                )
                keys.append(
                    Key.parse_xpub(
                        xpub, keys_purposes[i] if len(keys_purposes) > i else ""
                    )
                )
            except Exception:
                # TODO: This should never occur, but just in case,
                # we must make sure to catch it properly so it
                # doesn't crash the app no matter what.
                raise Exception("Failed to parse this xpub:\n" + "\n".join(xpub))
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

    def sign_psbt(self, base64_psbt, wallet, file_password=None):
        # Load the wallet if not loaded
        self._load_wallet(wallet.manager)
        rpc = wallet.manager.rpc.wallet(
            os.path.join(wallet.manager.rpc_path + "_hotstorage", self.alias)
        )
        if file_password:
            rpc.walletpassphrase(file_password, 60)
        signed_psbt = rpc.walletprocesspsbt(base64_psbt, True, self.SIGHASH)
        if base64_psbt == signed_psbt["psbt"]:
            raise Exception(
                "Make sure you have entered the wallet file password correctly. (If your wallet is not encrypted submit empty password)"
            )
        if file_password:
            rpc.walletlock()
        return signed_psbt

    def sign_raw_tx(self, raw_tx, wallet, file_password=None):
        # Load the wallet if not loaded
        self._load_wallet(wallet.manager)
        rpc = wallet.manager.rpc.wallet(
            os.path.join(wallet.manager.rpc_path + "_hotstorage", self.alias)
        )
        if file_password:
            rpc.walletpassphrase(file_password, 60)
        signed_tx = rpc.signrawtransactionwithwallet(raw_tx)
        if file_password:
            rpc.walletlock()
        return signed_tx

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


class BitcoinCoreWatchOnly(BitcoinCore):
    """If a BitcoinCore Hotwallet get exported, it'll have the type:"bitcoincore_watchonly" .
    if such a device.json get imported, it's instantiate as a BitcoinCoreWatchOnly.
    It can be converted back to a device of Type BitcoinCore by providing the 12 words again.
    """

    device_type = DeviceTypes.BITCOINCORE_WATCHONLY
    name = "Bitcoin Core (watch only)"
    hot_wallet = False

    def sign_psbt(self, base64_psbt, wallet, file_password=None):
        raise SpecterError("Cannot sign with a watch-only wallet. Convert")

    def sign_raw_tx(self, raw_tx, wallet, file_password=None):
        raise SpecterError("Cannot sign with a watch-only wallet")

    def add_hot_wallet_keys(
        self,
        mnemonic,
        passphrase,
        paths,
        file_password,
        wallet_manager,
        testnet,
        keys_range=[0, 1000],
        keys_purposes=[],
    ):
        # Convert the watch-only wallet to a hot wallet then fix up its internal attrs to
        # match.
        super().add_hot_wallet_keys(
            mnemonic,
            passphrase,
            paths,
            file_password,
            wallet_manager,
            testnet,
            keys_range,
            keys_purposes,
        )

        # Change type (also triggers write to file)
        self.set_type(DeviceTypes.BITCOINCORE)
        # After update this device will be available as a BitcoinCore (hot) instance
        self.manager.update()
