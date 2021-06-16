import os
from embit import bip39
from embit.liquid.slip77 import master_blinding_from_seed
from .bitcoin_core import BitcoinCore


class ElementsCore(BitcoinCore):
    device_type = "elementscore"
    name = "Elements Core (hot wallet)"
    icon = "elementscore_icon.svg"

    hot_wallet = True
    bitcoin_core_support = False
    liquid_support = True

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
        super().add_hot_wallet_keys(
            mnemonic,
            passphrase,
            paths,
            file_password,
            wallet_manager,
            testnet,
            keys_range=keys_range,
            keys_purposes=keys_purposes,
        )
        rpc = wallet_manager.rpc.wallet(
            os.path.join(wallet_manager.rpc_path + "_hotstorage", self.alias)
        )
        seed = bip39.mnemonic_to_seed(mnemonic, passphrase)
        master_blinding_key = master_blinding_from_seed(seed)
        rpc.importmasterblindingkey(master_blinding_key.secret.hex())
        self.set_blinding_key(master_blinding_key.wif())
