import os
from embit import bip39
from embit.liquid.slip77 import master_blinding_from_seed

from ..helpers import is_liquid
from . import DeviceTypes
from .bitcoin_core import BitcoinCore


class ElementsCore(BitcoinCore):
    device_type = DeviceTypes.ELEMENTSCORE
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

    def has_key_types(self, wallet_type, network="main"):
        if not is_liquid(network):
            return False
        return super().has_key_types(wallet_type, network)

    def no_key_found_reason(self, wallet_type, network="main"):
        if self.has_key_types(wallet_type, network=network):
            return ""
        if not is_liquid(network):
            return "This wallet can only sign on Liquid"
