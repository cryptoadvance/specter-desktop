import os, shutil
from bip32 import BIP32
from mnemonic import Mnemonic
from ..descriptor import AddChecksum
from ..device import Device
from ..helpers import alias, convert_xpub_prefix, encode_base58_checksum, get_xpub_fingerprint, seed_to_hd_master_key
from ..key import Key

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

        bip32 = BIP32.from_seed(seed)
        xpubs = ""
        master_fpr = get_xpub_fingerprint(bip32.get_xpub_from_path('m/0h')).hex()

        if not testnet:
            # Nested Segwit
            xpub = bip32.get_xpub_from_path('m/49h/0h/0h')
            ypub = convert_xpub_prefix(xpub, b'\x04\x9d\x7c\xb2')
            xpubs += "[%s/49'/0'/0']%s\n" % (master_fpr, ypub)
            # native Segwit
            xpub = bip32.get_xpub_from_path('m/84h/0h/0h')
            zpub = convert_xpub_prefix(xpub, b'\x04\xb2\x47\x46')
            xpubs += "[%s/84'/0'/0']%s\n" % (master_fpr, zpub)
            # Multisig nested Segwit
            xpub = bip32.get_xpub_from_path('m/48h/0h/0h/1h')
            Ypub = convert_xpub_prefix(xpub, b'\x02\x95\xb4\x3f')
            xpubs += "[%s/48'/0'/0'/1']%s\n" % (master_fpr, Ypub)
            # Multisig native Segwit
            xpub = bip32.get_xpub_from_path('m/48h/0h/0h/2h')
            Zpub = convert_xpub_prefix(xpub, b'\x02\xaa\x7e\xd3')
            xpubs += "[%s/48'/0'/0'/2']%s\n" % (master_fpr, Zpub)
        else:
            # Testnet nested Segwit
            xpub = bip32.get_xpub_from_path('m/49h/1h/0h')
            upub = convert_xpub_prefix(xpub, b'\x04\x4a\x52\x62')
            xpubs += "[%s/49'/1'/0']%s\n" % (master_fpr, upub)
            # Testnet native Segwit
            xpub = bip32.get_xpub_from_path('m/84h/1h/0h')
            vpub = convert_xpub_prefix(xpub, b'\x04\x5f\x1c\xf6')
            xpubs += "[%s/84'/1'/0']%s\n" % (master_fpr, vpub)
            # Testnet multisig nested Segwit
            xpub = bip32.get_xpub_from_path('m/48h/1h/0h/1h')
            Upub = convert_xpub_prefix(xpub, b'\x02\x42\x89\xef')
            xpubs += "[%s/48'/1'/0'/1']%s\n" % (master_fpr, Upub)
            # Testnet multisig native Segwit
            xpub = bip32.get_xpub_from_path('m/48h/1h/0h/2h')
            Vpub = convert_xpub_prefix(xpub, b'\x02\x57\x54\x83')
            xpubs += "[%s/48'/1'/0'/2']%s\n" % (master_fpr, Vpub)

        keys, failed = Key.parse_xpubs(xpubs)
        if len(failed) > 0:
            # TODO: This should never occur, but just in case, we must make sure to catch it properly so it doesn't crash the app no matter what.
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

    def delete(self, wallet_manager):
        try:
            wallet_cli_path = os.path.join(wallet_manager.cli_path + "_hotstorage", self.alias)
            cli = wallet_manager.cli.wallet(wallet_cli_path)
            cli.unloadwallet(wallet_cli_path)
            # Try deleting wallet file
            if wallet_manager.get_default_datadir() and os.path.exists(wallet_cli_path):
                shutil.rmtree(os.path.join(wallet_manager.get_default_datadir(), wallet_cli_path))
        except:
            pass # We tried...
