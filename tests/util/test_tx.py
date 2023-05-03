import logging, pytest
from cryptoadvance.specter.helpers import alias
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
    wallet_manager = specter_regtest_configured.wallet_manager

    def sign_tx_with_device(raw_tx: str, devices=devices) -> str:
        signed = hot_wallet_device_1.sign_raw_tx(raw_tx, wallet)
        assert signed["complete"]
        return signed["hex"]

    def sign_psbt_with_devices(psbt: dict, devices=devices) -> str:
        signed = psbt
        for device in devices:
            signed = device.sign_psbt(signed["psbt"], wallet)
            if signed["complete"]:
                break
        assert signed["complete"]
        return signed["psbt"]

    # Let's test that with all the relevant key-types
    for key_type in [
        "wpkh",  # Single (Segwit)
        "sh-wpkh",  #  Single (Nested)
        "wsh",  # Multisig (Segwit)
        "sh-wsh",  # Multisig (Nested)
        "tr",  # Taproot
    ]:

        logging.info(f"begin of loop key_type '{key_type}'")
        # choose the devices
        if key_type in ["wsh", "sh-wsh"]:  # multisig
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

        logging.info(
            f"created wallet key_type '{key_type}' keys {[key.json for key in keys]}  wallet.account_map {wallet.account_map}"
        )

        if key_type == "wpkh":
            # Deriving the signed tx without RPC calls used in convert_rawtransaction_to_psbt()
            # fund it
            bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=3)
            # Check import of signed raw tx
            outputs = {wallet.getnewaddress(): 1}
            tx = wallet.rpc.createrawtransaction([], outputs)
            txF = wallet.rpc.fundrawtransaction(
                tx, {"changeAddress": wallet.getnewaddress()}
            )
            raw_tx = txF["hex"]
            signed_tx = sign_tx_with_device(raw_tx)
            b64_psbt = convert_rawtransaction_to_psbt(wallet.rpc, signed_tx)
            assert signed_tx == wallet.rpc.finalizepsbt(b64_psbt)["hex"]
            # Check import of unsigned raw tx
            b64_psbt_from_unsigned = convert_rawtransaction_to_psbt(wallet.rpc, raw_tx)
            psbt_dict = {"psbt": b64_psbt_from_unsigned, "complete": ""}
            signed_psbt = sign_psbt_with_devices(psbt_dict)
            assert signed_tx == wallet.rpc.finalizepsbt(signed_psbt)["hex"]
        else:
            # fund it
            bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=3)
            # Check import of signed raw tx
            outputs = {wallet.getnewaddress(): 1}
            tx = wallet.rpc.createrawtransaction([], outputs)
            txF = wallet.rpc.fundrawtransaction(
                tx, {"changeAddress": wallet.getnewaddress()}
            )
            raw_tx = txF["hex"]
            psbt = wallet.rpc.converttopsbt(raw_tx)
            psbt_dict = wallet.rpc.walletprocesspsbt(psbt)
            signed_psbt = sign_psbt_with_devices(psbt_dict)
            signed_tx = wallet.rpc.finalizepsbt(signed_psbt)["hex"]
            b64_psbt = convert_rawtransaction_to_psbt(wallet.rpc, signed_tx)
            assert signed_tx == wallet.rpc.finalizepsbt(b64_psbt)["hex"]
            # Check import of unsigned raw tx
            b64_psbt_from_unsigned = convert_rawtransaction_to_psbt(wallet.rpc, raw_tx)
            psbt_dict = {"psbt": b64_psbt_from_unsigned, "complete": ""}
            signed_psbt = sign_psbt_with_devices(psbt_dict)
            assert signed_tx == wallet.rpc.finalizepsbt(signed_psbt)["hex"]
