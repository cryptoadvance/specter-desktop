import json, logging, pytest
from decimal import Decimal
from cryptoadvance.specter.helpers import alias, generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.process_controller.node_controller import NodeController
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.device import Device
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.util.tx import convert_rawtransaction_to_psbt


def test_import_raw_transaction(
    caplog,
    bitcoin_regtest: NodeController,
    specter_regtest_configured: Specter,
    hot_wallet_device_1: Device,
    hot_wallet_device_2: Device,
):

    caplog.set_level(logging.INFO)
    devices = [hot_wallet_device_1, hot_wallet_device_2]
    # device = devices[0]
    wallet_manager = specter_regtest_configured.wallet_manager

    def sign_with_devices(psbtFF, devices=devices):
        signed = psbtFF
        for device in devices:
            signed = device.sign_psbt(signed["psbt"], wallet)
            if signed["complete"]:
                break
        logging.info(f"signed  {psbtFF}")
        assert signed["complete"]
        return signed

    # Let's test that with all the relevant key-types
    for key_type in [
        "sh-wsh",  # Single (Nested)
        "wpkh",  # Single (Segwit)
        # "pkh",    # Single (Legacy)
        "wsh",  # Multisig (Segwit)
        "sh-wpkh",  # Multisig (Nested)
        # "sh",     # Multisig (Legacy)
        "tr",  # Taproot
    ]:

        logging.info(f"begin of loop key_type '{key_type}'")

        # choose the devices
        if key_type in ["sh", "wsh", "sh-wsh"]:  # multisig
            keys = [
                key
                for device in devices
                for key in device.keys
                if key.key_type == key_type
            ]
            used_devices = devices
        else:
            keys = [key for key in devices[0].keys if key.key_type == key_type]
            used_devices = [devices[0]]

        assert keys

        # create the wallet for that key-type
        wallet = wallet_manager.create_wallet(
            f"bitcoincore_test_wallet_{key_type}",
            len(used_devices),
            key_type,
            keys,
            used_devices,
        )

        logging.debug(
            f"created wallet key_type '{key_type}' keys {[key.json for key in keys]}  wallet.account_map {wallet.account_map}"
        )

        # fund it
        bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=3)
        wallet.save_to_file()

        # Create a raw TX
        outputs = {wallet.getnewaddress(): 1}
        tx = wallet.rpc.createrawtransaction([], outputs)
        txF = wallet.rpc.fundrawtransaction(
            tx, {"changeAddress": wallet.getnewaddress()}
        )
        psbtF = wallet.rpc.converttopsbt(txF["hex"])
        psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
        signed = sign_with_devices(psbtFF)
        finalized_hex = wallet.rpc.finalizepsbt(signed["psbt"])["hex"]

        # convert the tx-hex to psbt
        psbt_base64 = convert_rawtransaction_to_psbt(wallet, finalized_hex)

        # Finally: check that the original TX == recreated raw_transaction
        assert finalized_hex == wallet.rpc.finalizepsbt(psbt_base64)["hex"]
