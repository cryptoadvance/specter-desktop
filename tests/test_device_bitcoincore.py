import json
import logging
import pytest
import time

from cryptoadvance.specter.devices import DeviceTypes
from cryptoadvance.specter.devices.bitcoin_core import BitcoinCore, BitcoinCoreWatchOnly
from cryptoadvance.specter.helpers import (
    generate_mnemonic,
    is_testnet,
    parse_wallet_data_import,
)
from cryptoadvance.specter.util.descriptor import AddChecksum, Descriptor
from cryptoadvance.specter.wallet_manager import WalletManager


def test_restore_hot_wallet(caplog, specter_regtest_configured):
    # A bitcoin core hot wallet will be restored from backups as a watch-only wallet.
    # Specter should be able to re-add the hot wallet keys.
    caplog.set_level(logging.DEBUG)

    device_manager = specter_regtest_configured.device_manager
    wallet_manager = specter_regtest_configured.wallet_manager

    # Create the bitcoin core hot wallet
    device = device_manager.add_device(
        name="bitcoin_core_hot_wallet", device_type=DeviceTypes.BITCOINCORE, keys=[]
    )
    device.setup_device(file_password=None, wallet_manager=wallet_manager)
    mnemonic = generate_mnemonic(strength=128)
    device.add_hot_wallet_keys(
        mnemonic=mnemonic,
        passphrase="",
        paths=["m/84h/0h/0h"],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    # Create the Specter notion of a wallet for it
    wallet = wallet_manager.create_wallet(
        "bitcoincore_test_wallet", 1, "wpkh", [device.keys[0]], [device]
    )

    # Fund the wallet
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(91, address)

    # newly minted coins need 100 blocks to get spendable
    # let's mine another 100 blocks to get these coins spendable
    wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    logging.debug(wallet.get_balance())
    assert wallet.get_balance()["trusted"] > 0.0

    # Should be able to sign a tx
    utxos = wallet.rpc.listunspent()

    def spend_utxo(device, wallet, utxos):
        us0 = utxos.pop()
        inputs = [{"txid": us0["txid"], "vout": us0["vout"]}]
        outputs = {wallet.getnewaddress(): 0.0001}
        tx = wallet.rpc.createrawtransaction(inputs, outputs)
        txF = wallet.rpc.fundrawtransaction(tx)
        txFS = device.sign_raw_tx(txF["hex"], wallet)
        txid = wallet.rpc.sendrawtransaction(txFS["hex"])

    spend_utxo(device, wallet, utxos)

    # Generate backup and start import process
    wallet_backup = wallet.account_map.replace("\\\\", "")

    # Delete everything thus far
    wallet_manager.delete_wallet(wallet)
    device_manager.remove_device(device, wallet_manager=wallet_manager)
    assert wallet.name not in wallet_manager.wallets_names
    assert device.name not in device_manager.devices_names

    # Parse the backed up wallet (code copied from the new_wallet endpoint)
    (
        wallet_name,
        recv_descriptor,
        cosigners_types,
    ) = parse_wallet_data_import(json.loads(wallet_backup.replace("'", "h")))

    descriptor = Descriptor.parse(
        AddChecksum(recv_descriptor.split("#")[0]),
        testnet=is_testnet(specter_regtest_configured.chain),
    )

    (
        keys,
        cosigners,
        unknown_cosigners,
        unknown_cosigners_types,
    ) = descriptor.parse_signers(device_manager.devices, cosigners_types)

    # Re-create the device, but as a watch-only wallet
    device_name = cosigners_types[0]["label"]
    new_device = device_manager.add_device(
        name=device_name,
        device_type=DeviceTypes.BITCOINCORE_WATCHONLY,
        keys=[unknown_cosigners[0][0]],
    )

    assert isinstance(new_device, BitcoinCoreWatchOnly)

    keys.append(unknown_cosigners[0][0])
    cosigners.append(new_device)

    wallet = wallet_manager.create_wallet(
        name=wallet_name,
        sigs_required=descriptor.multisig_M,
        key_type=descriptor.address_type,
        keys=keys,
        devices=cosigners,
    )

    # Sync the new wallet in bitcoincore to its existing utxos
    # Do we need to add a sleep() to ensure the rescan completes?
    wallet.rpc.rescanblockchain(0)

    # We restored the wallet's utxos but...
    logging.debug(wallet.get_balance())
    assert wallet.get_balance()["trusted"] > 0.0

    # ...we cannot spend them
    with pytest.raises(Exception) as e:
        spend_utxo(new_device, wallet, utxos)
    assert str(e.value) == "Cannot sign with a watch-only wallet"

    # Wallet is back but is now watch-only so add hot key
    new_device.add_hot_wallet_keys(
        mnemonic=mnemonic,
        passphrase="",
        paths=["m/84h/0h/0h"],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    # retrieve the updated device and verify its new type
    new_device = device_manager.get_by_name(device_name)
    assert isinstance(new_device, BitcoinCore)

    # Should now be able to spend from the original utxo list!
    spend_utxo(new_device, wallet, utxos)
