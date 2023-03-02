import json
import logging
import os
import time
from unittest.mock import MagicMock, patch

import pytest
from cryptoadvance.specter.devices.bitcoin_core import BitcoinCore
from cryptoadvance.specter.devices.generic import GenericDevice
from cryptoadvance.specter.helpers import is_testnet
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.util.mnemonic import generate_mnemonic
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.descriptor import AddChecksum, Descriptor
from cryptoadvance.specter.util.wallet_importer import WalletImporter

logger = logging.getLogger(__name__)


@patch("cryptoadvance.specter.util.wallet_importer.flash", print)
@pytest.mark.slow
def test_WalletManager(
    request,
    devices_filled_data_folder,
    device_manager,
    bitcoin_regtest,
    node,
    node_with_empty_datadir,
):
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
    )
    assert wm.rpc_path == "specter"
    # A wallet-creation needs a device
    device = device_manager.get_by_alias("trezor")
    assert device != None
    # Lets's create a wallet with the WalletManager
    wm.create_wallet(
        "wallet_for_wallet_manager_test", 1, "wpkh", [device.keys[5]], [device]
    )
    # The wallet-name gets its filename and therefore its alias
    wallet = wm.wallets["wallet_for_wallet_manager_test"]
    assert wallet != None
    assert wallet.balance["trusted"] == 0
    assert wallet.balance["untrusted_pending"] == 0
    # this is a sum of both
    assert wallet.amount_total == 0
    address = wallet.getnewaddress()
    bitcoin_regtest.testcoin_faucet(address, amount=3)
    # update the balance
    wallet.update_balance()
    assert wallet.amount_total == 3
    assert wallet.amount_immature == 0

    # You can create a multisig wallet with the wallet manager like this
    second_device = device_manager.get_by_alias("specter")
    multisig_wallet = wm.create_wallet(
        "a_multisig_test_wallet",
        1,
        "wsh",
        [device.keys[7], second_device.keys[0]],
        [device, second_device],
    )

    assert len(wm.wallets) == 2
    assert multisig_wallet != None
    assert multisig_wallet.amount_total == 0
    multisig_address = multisig_wallet.getnewaddress()
    bitcoin_regtest.testcoin_faucet(multisig_address, amount=4)
    # update balance
    multisig_wallet.update_balance()
    assert multisig_wallet.amount_total == 4
    # The WalletManager also has a `wallets_names` property, returning a sorted list of the names of all wallets
    assert wm.wallets_names == [
        "a_multisig_test_wallet",
        "wallet_for_wallet_manager_test",
    ]

    # You can rename a wallet using the wallet manager using `rename_wallet`, passing the wallet object and the new name to assign to it
    wm.rename_wallet(multisig_wallet, "new_name_test_wallet")
    assert multisig_wallet.name == "new_name_test_wallet"
    assert wm.wallets_names == [
        "new_name_test_wallet",
        "wallet_for_wallet_manager_test",
    ]

    # You can also delete a wallet by passing it to the wallet manager's `delete_wallet` method
    # It will delete the json and attempt to remove it from Bitcoin Core
    wallet_fullpath = multisig_wallet.fullpath
    assert os.path.exists(wallet_fullpath)
    # This deletion should also remove the wallet file on the node
    assert wm.delete_wallet(multisig_wallet, node) == (True, True)
    assert len(wm.wallets) == 1
    assert not os.path.exists(wallet_fullpath)
    # Let's artificially unload the wallet in Core before trying to delete it via the Wallet Manager, should raise a SpecterError
    wallet_rpc_path = os.path.join(wm.rpc_path, wallet.alias)
    wm.rpc.unloadwallet(wallet_rpc_path)
    with pytest.raises(
        SpecterError,
        match="Unable to unload the wallet on the node. Aborting the deletion of the wallet ...",
    ):
        wm.delete_wallet(wallet, node)
    # Check that the wallet wasn't deleted in Specter because of the RpcError
    assert wm.wallets_names == ["wallet_for_wallet_manager_test"]
    # The following deletion should not remove the wallet file on the node
    assert node_with_empty_datadir.datadir == ""
    wm.rpc.loadwallet(wallet_rpc_path)  # we need to load the wallet again
    assert wm.delete_wallet(wallet, node_with_empty_datadir) == (True, False)
    assert len(wm.wallets) == 0
    # The wallet in Specter was already deleted, so trying to delete it again should raise a SpecterError
    wm.rpc.loadwallet(wallet_rpc_path)  # we need to load the wallet again
    with pytest.raises(
        SpecterError,
        match="The wallet wallet_for_wallet_manager_test has already been deleted.",
    ):
        assert wm.delete_wallet(wallet)


@pytest.mark.slow
@pytest.mark.bottleneck
@pytest.mark.threading
def test_WalletManager_2_nodes(
    request,
    devices_filled_data_folder,
    device_manager,
    bitcoin_regtest,
    bitcoin_regtest2: BitcoindPlainController,
    caplog,
):
    caplog.set_level(logging.INFO)
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
        allow_threading_for_testing=True,
    )
    # Wallet creation needs a device
    device = device_manager.get_by_alias("trezor")
    assert device != None
    first_wallet = wm.create_wallet(
        "wallet_for_test_with_two_nodes", 1, "wpkh", [device.keys[5]], [device]
    )
    assert wm.wallets_names == ["wallet_for_test_with_two_nodes"]
    assert wm.chain == "regtest"
    assert wm.working_folder.endswith("regtest")
    assert wm.rpc.port == 18543
    # Change the rpc - this works differently with a different chain!
    # If we use something different that regtest, unfortunately a liquid address gets
    # generated.
    # So we don't test that scanrio here of different chains. We test the scenario with the same chain.
    # but different node
    wm.update(rpc=bitcoin_regtest2.get_rpc(), chain="regtest")
    # A WalletManager uses the chain as an index
    assert list(wm.rpcs.keys()) == [
        "regtest",
    ]  # wm.rpcs looks like this: {'regtest': <BitcoinRpc http://localhost:18543>, 'regtest2': <BitcoinRpc http://localhost:18544>}
    assert wm.rpc.port == 18544
    assert wm.wallets_names == ["wallet_for_test_with_two_nodes"]
    assert wm.chain == "regtest"
    assert wm.working_folder.endswith("test")
    second_wallet = wm.create_wallet(
        "a_regtest2_test_wallet", 1, "wpkh", [device.keys[5]], [device]
    )
    # Note: "regtest2" is recognised by the get_network() from embit as Liquid, that is why there is an error in the logs saying the Bitcoin address is not valid since a Liquid address is derived.
    assert len(wm.wallets_names) == 2
    assert wm.wallets_names == [
        "a_regtest2_test_wallet",
        "wallet_for_test_with_two_nodes",
    ]


def test_WalletManager_check_duplicate_keys(empty_data_folder):
    wm = WalletManager(
        empty_data_folder,
        MagicMock(),  # needs rpc
        "regtest",
        None,
    )
    key1 = Key(
        "[f3e6eaff/84h/0h/0h]xpub6C5cCQfycZrPJnNg6cDdUU5efJrab8thRQDBxSSB4gP2J3xGdWu8cqiLvPZkejtuaY9LursCn6Es9PqHgLhBktW8217BomGDVBAJjUms8iG",
        "f3e6eaff",
        "84h/0h/0h",
        "",
        None,
        "xpub6C5cCQfycZrPJnNg6cDdUU5efJrab8thRQDBxSSB4gP2J3xGdWu8cqiLvPZkejtuaY9LursCn6Es9PqHgLhBktW8217BomGDVBAJjUms8iG",
    )
    key2 = Key(
        "[1ef4e492/49h/0h/0h]xpub6CRWp2zfwRYsVTuT2p96hKE2UT4vjq9gwvW732KWQjwoG7v6NCXyaTdz7NE5yDxsd72rAGK7qrjF4YVrfZervsJBjsXxvTL98Yhc7poBk7K",
        "1ef4e492",
        "m/49h/0h/0h",
        "sh-wpkh",
        None,
        "xpub6CRWp2zfwRYsVTuT2p96hKE2UT4vjq9gwvW732KWQjwoG7v6NCXyaTdz7NE5yDxsd72rAGK7qrjF4YVrfZervsJBjsXxvTL98Yhc7poBk7K",
    )
    key3 = Key(
        "[1ef4e492/49h/0h/0h]zpub6qk8ok1ouvwM1NkumKnsteGf1F9UUNshFdFdXEDwph8nQFaj8qEFry2cxoUveZCkPpNxQp4KhQwxuy4R7jXDMMsKkgW2yauC2dHbWYnr2Ee",
        "1ef4e492",
        "m/49h/0h/0h",
        "sh-wpkh",
        None,
        "zpub6qk8ok1ouvwM1NkumKnsteGf1F9UUNshFdFdXEDwph8nQFaj8qEFry2cxoUveZCkPpNxQp4KhQwxuy4R7jXDMMsKkgW2yauC2dHbWYnr2Ee",
    )

    key4 = Key(
        "[6ea15da6/49h/0h/0h]xpub6BtcNhqbaFaoC3oEfKky3Sm22pF48U2jmAf78cB3wdAkkGyAgmsVrgyt1ooSt3bHWgzsdUQh2pTJ867yTeUAMmFDKNSBp8J7WPmp7Df7zjv",
        "6ea15da6",
        "m/49h/0h/0h",
        "sh-wpkh",
        None,
        "xpub6BtcNhqbaFaoC3oEfKky3Sm22pF48U2jmAf78cB3wdAkkGyAgmsVrgyt1ooSt3bHWgzsdUQh2pTJ867yTeUAMmFDKNSBp8J7WPmp7Df7zjv",
    )

    key5 = Key(
        "[6ea15da6/49h/0h/0h]xpub6BtcNhqbaFaoG3xcuncx9xzL3X38FuWXdcdvsdG5Q99Cb4EgeVYPEYaVpX28he6472gEsCokg8v9oMVRTrZNe5LHtGSPcC5ofehYkhD1Kxy",
        "6ea15da6",
        "m/49h/0h/1h",
        "sh-wpkh",
        None,  # slightly different ypub than key4
        "xpub6BtcNhqbaFaoG3xcuncx9xzL3X38FuWXdcdvsdG5Q99Cb4EgeVYPEYaVpX28he6472gEsCokg8v9oMVRTrZNe5LHtGSPcC5ofehYkhD1Kxy",
    )

    # Case 1: Identical keys
    keys = [key1, key1]
    with pytest.raises(SpecterError):
        wm._check_duplicate_keys(keys)
    # Case 2: different keys
    # key2 and 3 are different as they don't have the same xpub. See #1500 for discussion
    keys = [key1, key2, key3]  # key2 xpub is the same than key3 zpub
    with pytest.raises(SpecterError):
        wm._check_duplicate_keys(keys)

    keys = [key4, key5]
    wm._check_duplicate_keys(keys)


def test_wallet_sortedmulti(
    bitcoin_regtest, devices_filled_data_folder, device_manager
):
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
    )
    device = device_manager.get_by_alias("trezor")
    second_device = device_manager.get_by_alias("specter")
    for i in range(2):
        if i == 0:
            multisig_wallet = wm.create_wallet(
                "multisig_wallet_for_sortedmulti_test",
                1,
                "wsh",
                [device.keys[7], second_device.keys[0]],
                [device, second_device],
            )
        else:
            multisig_wallet = wm.create_wallet(
                "another_multisig_wallet_for_sortedmulti_test",
                1,
                "wsh",
                [second_device.keys[0], device.keys[7]],
                [second_device, device],
            )

        address = multisig_wallet.address
        address_info = multisig_wallet.rpc.getaddressinfo(address)
        assert address_info["pubkeys"][0] < address_info["pubkeys"][1]

        another_address = multisig_wallet.getnewaddress()
        another_address_info = multisig_wallet.rpc.getaddressinfo(another_address)
        assert another_address_info["pubkeys"][0] < another_address_info["pubkeys"][1]

        third_address = multisig_wallet.get_address(30)
        third_address_info = multisig_wallet.rpc.getaddressinfo(third_address)
        assert third_address_info["pubkeys"][0] < third_address_info["pubkeys"][1]

        change_address = multisig_wallet.change_address
        change_address_info = multisig_wallet.rpc.getaddressinfo(change_address)
        assert change_address_info["pubkeys"][0] < change_address_info["pubkeys"][1]

        another_change_address = multisig_wallet.get_address(30, change=True)
        another_change_address_info = multisig_wallet.rpc.getaddressinfo(
            another_change_address
        )
        assert (
            another_change_address_info["pubkeys"][0]
            < another_change_address_info["pubkeys"][1]
        )


def test_wallet_labeling(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
    )
    # A wallet-creation needs a device
    device = device_manager.get_by_alias("specter")
    key = Key.from_json(
        {
            "derivation": "m/48h/1h/0h/2h",
            "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
            "fingerprint": "08686ac6",
            "type": "wsh",
            "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL",
        }
    )
    wallet = wm.create_wallet("a_second_test_wallet", 1, "wpkh", [key], [device])

    first_address = wallet.address
    assert wallet.getlabel(first_address) == "Address #0"
    wallet.setlabel(first_address, "Random label")
    assert wallet.getlabel(first_address) == "Random label"

    second_address = wallet.getnewaddress()
    wallet.setlabel(second_address, "")
    bitcoin_regtest.testcoin_faucet(second_address, amount=0.6)

    third_address = wallet.getnewaddress()
    wallet.setlabel(third_address, "")
    bitcoin_regtest.testcoin_faucet(third_address, amount=0.4)

    assert sorted(wallet.addresses) == sorted(
        [first_address, second_address, third_address]
    )

    # Make 20 UTXO
    for i in range(0, 20):
        _address = wallet.getnewaddress()
        bitcoin_regtest.testcoin_faucet(_address, amount=0.1)

    # update utxo
    wallet.getdata()
    assert len(wallet.full_utxo) == 22

    # An entry in full_utxo looks something like this:
    # { 'txid': 'fab823558781745179916b4bfdfd65b382bfc0e70e85188f1b9538604202f537',
    #   'vout': 0, 'address': 'bcrt1qmlrraffw0evkjy2yrxmt263ksgfgv2gqhcddrt',
    #   'label': 'Random label', 'scriptPubKey': '0014dfc63ea52e7e5969114419b6b56a368212862900',
    #   'amount': 50.0, 'confirmations': 101, 'spendable': False, 'solvable': True,
    #   'desc': "wpkh([08686ac6/48'/1'/0'/2'/0/0]02fa445808af849209038f422a22e335754fa07a2ece42fc483660606dcda3e0e9)#8q60z40m",
    #   'safe': True, 'time': 1637091575, 'category': 'generate', 'locked': False
    # }


def test_wallet_change_addresses(
    bitcoin_regtest, devices_filled_data_folder, device_manager
):
    wm = WalletManager(
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
    )
    # A wallet-creation needs a device
    device = device_manager.get_by_alias("specter")
    key = Key.from_json(
        {
            "derivation": "m/84h/1h/0h",
            "original": "vpub5ZSem3mLXiSJzgDX6pJb2N9L6sJ8m6ejaksLPLSuB53LBzCi2mMsBg19eEUSDkHtyYp75GATjLgt5p3S43WjaVCXAWU9q9H5GhkwJBrMiAb",
            "fingerprint": "08686ac6",
            "type": "wpkh",
            "xpub": "tpubDDUotcvrYMUiy4ncDirveTfhmvggdj8nxcW5JgHpGzYz3UVscJY5aEzFvgUPk4YyajadBnsTBmE2YZmAtJC14Q21xncJgVaHQ7UdqMRVRbU",
        }
    )
    wallet: wallet = wm.create_wallet("a_third_test_wallet", 1, "wpkh", [key], [device])

    address = wallet.address
    change_address = wallet.change_address
    assert wallet.addresses == [address]
    assert wallet.change_addresses == [change_address]
    bitcoin_regtest.testcoin_faucet(change_address, amount=0.1)
    wallet.update_balance()
    assert wallet.amount_total == 0.1

    # new change address should be genrated automatically after receiving
    # assert wallet.change_addresses == [change_address, wallet.change_address]
    # This will not work here since Bitcoin Core doesn't count mining rewards in `getreceivedbyaddress`
    # See: https://github.com/bitcoin/bitcoin/issues/14654


def test_singlesig_wallet_backup_and_restore(caplog, specter_regtest_configured, node):
    """
    Single-sig wallets should be able to be backed up and re-imported with or without
    the "devices" attr in the json backup.
    """
    caplog.set_level(logging.INFO)

    device_manager = specter_regtest_configured.device_manager
    wallet_manager = specter_regtest_configured.wallet_manager

    device = device_manager.get_by_alias("trezor")
    device_type = device.device_type

    # Get the 'wkph' testnet key
    for key in device.keys:
        if key.key_type == "wpkh" and key.xpub.startswith("tpub"):
            break

    # create a wallet
    wallet = wallet_manager.create_wallet(
        name="my_singlesig_test_wallet",
        sigs_required=1,
        key_type=key.key_type,
        keys=[key],
        devices=[device],
    )

    # Wallet was prefunded in specter_regtest_configured fixture, not sure, though, why the amount is 23 and not 20 ...
    amount = wallet.amount_total

    # Save the json backup
    wallet_backup = json.loads(wallet.account_map)
    assert "devices" in wallet_backup

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet, node)
    device_manager.remove_device(device, wallet_manager=wallet_manager)
    assert wallet.name not in wallet_manager.wallets_names
    assert device.name not in device_manager.devices_names

    # Parse the backed up wallet (code adapted from the new_wallet endpoint)
    (
        wallet_name,
        recv_descriptor,
        cosigners_types,
    ) = WalletImporter.parse_wallet_data_import(wallet_backup)

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

    device_name = cosigners_types[0]["label"]
    assert device_name == "Trezor"
    assert unknown_cosigners_types[0] == device_type

    # Re-create the device
    new_device = device_manager.add_device(
        name=device_name,
        device_type=unknown_cosigners_types[0],
        keys=[unknown_cosigners[0][0]],
    )

    keys.append(unknown_cosigners[0][0])
    cosigners.append(new_device)

    wallet = wallet_manager.create_wallet(
        name=wallet_name,
        sigs_required=descriptor.multisig_M,
        key_type=descriptor.address_type,
        keys=keys,
        devices=cosigners,
    )

    # Sync the new wallet in bitcoincore to its existing utxos.
    wallet.rpc.rescanblockchain(0)

    # We restored the wallet's utxos
    wallet.update_balance()
    assert wallet.amount_total == amount

    # Now do it again, but without the newer "devices" attr
    del wallet_backup["devices"]

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet, node)
    device_manager.remove_device(device, wallet_manager=wallet_manager)
    assert wallet.name not in wallet_manager.wallets_names
    assert device.name not in device_manager.devices_names

    # Parse the backed up wallet (code adapted from the new_wallet endpoint)
    (
        wallet_name,
        recv_descriptor,
        cosigners_types,
    ) = WalletImporter.parse_wallet_data_import(wallet_backup)

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

    assert len(cosigners_types) == 0
    assert unknown_cosigners_types[0] == GenericDevice.device_type

    # Re-create the device
    new_device = device_manager.add_device(
        name=device_name,
        device_type=unknown_cosigners_types[0],
        keys=[unknown_cosigners[0][0]],
    )

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
    wallet.rpc.rescanblockchain(0)

    # We restored the wallet's utxos
    wallet.update_balance()
    assert wallet.amount_total == amount


def test_multisig_wallet_backup_and_restore(
    bitcoin_regtest, caplog, specter_regtest_configured, node
):
    """
    Multisig wallets should be able to be backed up and re-imported
    with or without the "devices" attr in the json backup.
    """
    caplog.set_level(logging.INFO)

    device_manager = specter_regtest_configured.device_manager
    wallet_manager = specter_regtest_configured.wallet_manager

    device = device_manager.get_by_alias("trezor")
    device_type = device.device_type

    # Get the multisig 'wsh' testnet key
    for key in device.keys:
        if key.key_type == "wsh" and key.xpub.startswith("tpub"):
            break

    # Create a pair of hot wallet signers
    hot_wallet_1_device = device_manager.add_device(
        name="hot_key_1", device_type=BitcoinCore.device_type, keys=[]
    )
    hot_wallet_1_device.setup_device(file_password=None, wallet_manager=wallet_manager)
    hot_wallet_1_device.add_hot_wallet_keys(
        mnemonic=generate_mnemonic(strength=128),
        passphrase="",
        paths=["m/48h/1h/0h/2h"],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )
    hot_wallet_2_device = device_manager.add_device(
        name="hot_key_2", device_type=BitcoinCore.device_type, keys=[]
    )
    hot_wallet_2_device.setup_device(file_password=None, wallet_manager=wallet_manager)
    hot_wallet_2_device.add_hot_wallet_keys(
        mnemonic=generate_mnemonic(strength=128),
        passphrase="",
        paths=["m/48h/1h/0h/2h"],
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    # create the multisig wallet
    wallet = wallet_manager.create_wallet(
        name="my_multisig_test_wallet",
        sigs_required=2,
        key_type=key.key_type,
        keys=[key, hot_wallet_1_device.keys[0], hot_wallet_2_device.keys[0]],
        devices=[device, hot_wallet_1_device, hot_wallet_2_device],
    )

    # Wallet is unfunded
    address = wallet.getnewaddress()
    bitcoin_regtest.testcoin_faucet(address, amount=3.3)
    wallet.update_balance()
    assert wallet.amount_total == 3.3

    # Save the json backup
    wallet_backup = json.loads(wallet.account_map.replace("\\\\", "").replace("'", "h"))
    assert "devices" in wallet_backup

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet, node)
    device_manager.remove_device(device, wallet_manager=wallet_manager)
    assert wallet.name not in wallet_manager.wallets_names
    assert device.name not in device_manager.devices_names

    # Parse the backed up wallet (code adapted from the new_wallet endpoint)
    (
        wallet_name,
        recv_descriptor,
        cosigners_types,
    ) = WalletImporter.parse_wallet_data_import(wallet_backup)

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

    assert cosigners_types[0]["label"] == "Trezor"
    assert cosigners_types[0]["type"] == device_type

    assert cosigners_types[1]["label"] == "hot_key_1"
    assert cosigners_types[1]["type"] == BitcoinCore.device_type

    assert cosigners_types[2]["label"] == "hot_key_2"
    assert cosigners_types[2]["type"] == BitcoinCore.device_type

    # Re-create the Trezor device
    new_device = device_manager.add_device(
        name=unknown_cosigners[0][1],
        device_type=unknown_cosigners_types[0],
        keys=[unknown_cosigners[0][0]],
    )
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
    wallet.rpc.rescanblockchain(0)

    # We restored the wallet's utxos
    assert wallet.amount_total == 3.3

    # Now do it again, but without the newer "devices" attr
    del wallet_backup["devices"]

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet, node)
    for device_names in device_manager.devices:
        device = device_manager.devices[device_names]
        device_manager.remove_device(device, wallet_manager=wallet_manager)
    assert wallet.name not in wallet_manager.wallets_names
    assert device.name not in device_manager.devices_names

    # Parse the backed up wallet (code adapted from the new_wallet endpoint)
    (
        wallet_name,
        recv_descriptor,
        cosigners_types,
    ) = WalletImporter.parse_wallet_data_import(wallet_backup)

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

    # Now we don't know any of the cosigners' types
    assert len(cosigners_types) == 0
    assert unknown_cosigners_types[0] == GenericDevice.device_type

    # Re-create all three devices
    for i, (unknown_cosigner_key, label) in enumerate(unknown_cosigners):
        # 'label' will be unknown
        assert label is None
        new_device = device_manager.add_device(
            name=f"{wallet_name} signer {i + 1}",
            device_type=unknown_cosigners_types[i],
            keys=[unknown_cosigner_key],
        )
        keys.append(unknown_cosigner_key)
        cosigners.append(new_device)

    wallet = wallet_manager.create_wallet(
        name=wallet_name,
        sigs_required=descriptor.multisig_M,
        key_type=descriptor.address_type,
        keys=keys,
        devices=cosigners,
    )

    # Sync the new wallet in bitcoincore to its existing utxos
    wallet.rpc.rescanblockchain(0)

    # We restored the wallet's utxos
    assert wallet.amount_total == 3.3


def test_threading(specter_regtest_configured_with_threading):
    assert (
        specter_regtest_configured_with_threading.config["testing"][
            "allow_threading_for_testing"
        ]
        == True
    )
    device = specter_regtest_configured_with_threading.device_manager.get_by_alias(
        "trezor"
    )
    wm = specter_regtest_configured_with_threading.wallet_manager
    wallet = wm.create_wallet("test_wallet", 1, "wpkh", [device.keys[5]], [device])
    assert wm.wallets_names == ["test_wallet"]
    assert wm.data_folder.endswith("wallets")
