import json
import logging
import os
import time

import pytest
from cryptoadvance.specter.helpers import (
    is_testnet,
    generate_mnemonic,
)
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.devices import DeviceTypes
from cryptoadvance.specter.managers.wallet_manager import WalletManager
from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.descriptor import AddChecksum, Descriptor
from cryptoadvance.specter.util.wallet_importer import WalletImporter
from cryptoadvance.specter.wallet import Wallet
from conftest import instantiate_bitcoind_controller


@pytest.mark.slow
def test_WalletManager(docker, request, devices_filled_data_folder, device_manager):
    # Instantiate a fresh bitcoind instance to isolate this test.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker, request, rpcport=18998
    )
    try:
        wm = WalletManager(
            200100,
            devices_filled_data_folder,
            bitcoind_controller.get_rpc(),
            "regtest",
            device_manager,
            allow_threading=False,
        )
        # A wallet-creation needs a device
        device = device_manager.get_by_alias("trezor")
        assert device != None
        # Lets's create a wallet with the WalletManager
        wm.create_wallet("a_test_wallet", 1, "wpkh", [device.keys[5]], [device])
        # The wallet-name gets its filename and therefore its alias
        wallet = wm.wallets["a_test_wallet"]
        assert wallet != None
        assert wallet.balance["trusted"] == 0
        assert wallet.balance["untrusted_pending"] == 0
        # this is a sum of both
        assert wallet.fullbalance == 0
        address = wallet.getnewaddress()
        # newly minted coins need 100 blocks to get spendable
        wallet.rpc.generatetoaddress(1, address)
        # let's mine another 100 blocks to get these coins spendable
        random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
        wallet.rpc.generatetoaddress(100, random_address)
        # update the balance
        wallet.update_balance()
        assert wallet.fullbalance >= 25

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
        assert multisig_wallet.fullbalance == 0
        multisig_address = multisig_wallet.getnewaddress()
        multisig_wallet.rpc.generatetoaddress(1, multisig_address)
        multisig_wallet.rpc.generatetoaddress(100, random_address)
        # update balance
        multisig_wallet.update_balance()
        assert multisig_wallet.fullbalance >= 12.5
        # The WalletManager also has a `wallets_names` property, returning a sorted list of the names of all wallets
        assert wm.wallets_names == ["a_multisig_test_wallet", "a_test_wallet"]

        # You can rename a wallet using the wallet manager using `rename_wallet`, passing the wallet object and the new name to assign to it
        wm.rename_wallet(multisig_wallet, "new_name_test_wallet")
        assert multisig_wallet.name == "new_name_test_wallet"
        assert wm.wallets_names == ["a_test_wallet", "new_name_test_wallet"]

        # you can also delete a wallet by passing it to the wallet manager's `delete_wallet` method
        # it will delete the json and attempt to remove it from Bitcoin Core
        wallet_fullpath = multisig_wallet.fullpath
        assert os.path.exists(wallet_fullpath)
        wm.delete_wallet(multisig_wallet)
        assert not os.path.exists(wallet_fullpath)
        assert len(wm.wallets) == 1
    finally:
        # cleanup
        bitcoind_controller.stop_bitcoind()


@pytest.mark.slow
def test_wallet_createpsbt(docker, request, devices_filled_data_folder, device_manager):
    # Instantiate a fresh bitcoind instance to isolate this test.
    bitcoind_controller = instantiate_bitcoind_controller(
        docker, request, rpcport=18978
    )
    try:
        wm = WalletManager(
            200100,
            devices_filled_data_folder,
            bitcoind_controller.rpcconn.get_rpc(),
            "regtest",
            device_manager,
            allow_threading=False,
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
        # Let's fund the wallet with ... let's say 40 blocks a 50 coins each --> 200 coins
        address = wallet.getnewaddress()
        assert address == "bcrt1qtnrv2jpygx2ef3zqfjhqplnycxak2m6ljnhq6z"
        wallet.rpc.generatetoaddress(20, address)
        # in two addresses
        address = wallet.getnewaddress()
        wallet.rpc.generatetoaddress(20, address)
        # newly minted coins need 100 blocks to get spendable
        # let's mine another 100 blocks to get these coins spendable
        random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
        wallet.rpc.generatetoaddress(110, random_address)
        # update the wallet data
        wallet.update_balance()
        # Now we have loads of potential inputs
        # Let's spend 500 coins
        assert wallet.fullbalance >= 250
        # From this print-statement, let's grab some txids which we'll use for coinselect
        unspents = wallet.rpc.listunspent(0)
        # Lets take 3 more or less random txs from the unspents:
        selected_coins = [
            {"txid": u["txid"], "vout": u["vout"]}
            for u in [unspents[5], unspents[9], unspents[12]]
        ]
        selected_coins_amount_sum = (
            unspents[5]["amount"] + unspents[9]["amount"] + unspents[12]["amount"]
        )
        number_of_coins_to_spend = (
            selected_coins_amount_sum - 0.1
        )  # Let's spend almost all of them
        psbt = wallet.createpsbt(
            [random_address],
            [number_of_coins_to_spend],
            True,
            0,
            10,
            selected_coins=selected_coins,
        )
        assert len(psbt["tx"]["vin"]) == 3
        psbt_txs = [tx["txid"] for tx in psbt["tx"]["vin"]]
        for coin in selected_coins:
            assert coin["txid"] in psbt_txs

        # Now let's spend more coins than we have selected. This should result in an exception:
        try:
            psbt = wallet.createpsbt(
                [random_address],
                [number_of_coins_to_spend + 1],
                True,
                0,
                10,
                selected_coins=selected_coins,
            )
            assert False, "should throw an exception!"
        except SpecterError as e:
            pass

        assert wallet.locked_amount == selected_coins_amount_sum
        assert len(wallet.rpc.listlockunspent()) == 3
        assert (
            wallet.full_available_balance
            == wallet.fullbalance - selected_coins_amount_sum
        )

        wallet.delete_pending_psbt(psbt["tx"]["txid"])
        assert wallet.locked_amount == 0
        assert len(wallet.rpc.listlockunspent()) == 0
        assert wallet.full_available_balance == wallet.fullbalance
    finally:
        # cleanup
        bitcoind_controller.stop_bitcoind()


def test_WalletManager_check_duplicate_keys(empty_data_folder):
    wm = WalletManager(
        200100,
        empty_data_folder,
        None,
        "regtest",
        None,
        allow_threading=False,
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
        200100,
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
        allow_threading=False,
    )
    device = device_manager.get_by_alias("trezor")
    second_device = device_manager.get_by_alias("specter")
    for i in range(2):
        if i == 0:
            multisig_wallet = wm.create_wallet(
                "a_multisig_test_wallet",
                1,
                "wsh",
                [device.keys[7], second_device.keys[0]],
                [device, second_device],
            )
        else:
            multisig_wallet = wm.create_wallet(
                "a_multisig_test_wallet",
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
        200100,
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
        allow_threading=False,
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

    address = wallet.address
    assert wallet.getlabel(address) == "Address #0"
    wallet.setlabel(address, "Random label")
    assert wallet.getlabel(address) == "Random label"

    wallet.rpc.generatetoaddress(20, address)

    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.rpc.generatetoaddress(100, random_address)

    # update utxo
    wallet.getdata()
    # update balance
    wallet.update_balance()

    address_balance = wallet.fullbalance
    assert len(wallet.full_utxo) == 20

    print(wallet.full_utxo[4])
    # Something like:
    # { 'txid': 'fab823558781745179916b4bfdfd65b382bfc0e70e85188f1b9538604202f537',
    #   'vout': 0, 'address': 'bcrt1qmlrraffw0evkjy2yrxmt263ksgfgv2gqhcddrt',
    #   'label': 'Random label', 'scriptPubKey': '0014dfc63ea52e7e5969114419b6b56a368212862900',
    #   'amount': 50.0, 'confirmations': 101, 'spendable': False, 'solvable': True,
    #   'desc': "wpkh([08686ac6/48'/1'/0'/2'/0/0]02fa445808af849209038f422a22e335754fa07a2ece42fc483660606dcda3e0e9)#8q60z40m",
    #   'safe': True, 'time': 1637091575, 'category': 'generate', 'locked': False
    # }

    new_address = wallet.getnewaddress()
    wallet.setlabel(new_address, "")
    wallet.rpc.generatetoaddress(20, new_address)

    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.rpc.generatetoaddress(100, random_address)

    wallet.getdata()
    wallet.update_balance()

    assert len(wallet.full_utxo) == 40

    wallet.setlabel(new_address, "")
    third_address = wallet.getnewaddress()

    wallet.getdata()
    assert sorted(wallet.addresses) == sorted([address, new_address, third_address])


def test_wallet_change_addresses(
    bitcoin_regtest, devices_filled_data_folder, device_manager
):
    wm = WalletManager(
        200100,
        devices_filled_data_folder,
        bitcoin_regtest.get_rpc(),
        "regtest",
        device_manager,
        allow_threading=False,
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

    address = wallet.address
    change_address = wallet.change_address
    assert wallet.addresses == [address]
    assert wallet.change_addresses == [change_address]

    wallet.rpc.generatetoaddress(20, change_address)
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.rpc.generatetoaddress(110, random_address)
    wallet.getdata()

    # new change address should be genrated automatically after receiving
    # assert wallet.change_addresses == [change_address, wallet.change_address]
    # This will not work here since Bitcoin Core doesn't count mining rewards in `getreceivedbyaddress`
    # See: https://github.com/bitcoin/bitcoin/issues/14654


def test_singlesig_wallet_backup_and_restore(caplog, specter_regtest_configured):
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
        name="my_test_wallet",
        sigs_required=1,
        key_type=key.key_type,
        keys=[key],
        devices=[device],
    )

    # Fund the wallet
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    balance = wallet.update_balance()
    assert balance["trusted"] > 0.0

    # Save the json backup
    wallet_backup = json.loads(wallet.account_map)
    assert "devices" in wallet_backup

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet)
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
    assert wallet.update_balance()["trusted"] > 0.0

    # Now do it again, but without the newer "devices" attr
    del wallet_backup["devices"]

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet)
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
    assert unknown_cosigners_types[0] == DeviceTypes.GENERICDEVICE

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
    assert wallet.update_balance()["trusted"] > 0.0


def test_multisig_wallet_backup_and_restore(caplog, specter_regtest_configured):
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
        name="hot_key_1", device_type=DeviceTypes.BITCOINCORE, keys=[]
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
        name="hot_key_2", device_type=DeviceTypes.BITCOINCORE, keys=[]
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
        name="my_test_wallet",
        sigs_required=2,
        key_type=key.key_type,
        keys=[key, hot_wallet_1_device.keys[0], hot_wallet_2_device.keys[0]],
        devices=[device, hot_wallet_1_device, hot_wallet_2_device],
    )

    # Fund the wallet
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    balance = wallet.update_balance()
    assert balance["trusted"] > 0.0

    # Save the json backup
    wallet_backup = json.loads(wallet.account_map.replace("\\\\", "").replace("'", "h"))
    assert "devices" in wallet_backup

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet)
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
    assert cosigners_types[1]["type"] == DeviceTypes.BITCOINCORE

    assert cosigners_types[2]["label"] == "hot_key_2"
    assert cosigners_types[2]["type"] == DeviceTypes.BITCOINCORE

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
    assert wallet.update_balance()["trusted"] > 0.0

    # Now do it again, but without the newer "devices" attr
    del wallet_backup["devices"]

    # Clear everything out as if we've never seen this wallet or device before
    wallet_manager.delete_wallet(wallet)
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
    assert unknown_cosigners_types[0] == DeviceTypes.GENERICDEVICE

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
    assert wallet.update_balance()["trusted"] > 0.0


@pytest.mark.slow
def test_taproot_wallet(caplog, specter_regtest_configured):
    """
    Taproot m/86h/ derivation path xpubs should be able to create wallets and
    receive funds
    """
    caplog.set_level(logging.INFO)

    device_manager = specter_regtest_configured.device_manager
    wallet_manager = specter_regtest_configured.wallet_manager

    taproot_device = device_manager.add_device(
        name="hot_key", device_type=DeviceTypes.BITCOINCORE, keys=[]
    )
    taproot_device.setup_device(file_password=None, wallet_manager=wallet_manager)
    taproot_device.add_hot_wallet_keys(
        mnemonic=generate_mnemonic(strength=128),
        passphrase="",
        paths=["m/86h/1h/0h"],  # Taproot for testnet/regtest
        file_password=None,
        wallet_manager=wallet_manager,
        testnet=True,
        keys_range=[0, 1000],
        keys_purposes=[],
    )

    taproot_wallet = wallet_manager.create_wallet(
        name="my_test_wallet",
        sigs_required=1,
        key_type=taproot_device.keys[0].key_type,
        keys=[taproot_device.keys[0]],
        devices=[taproot_device],
    )

    # Fund the wallet
    address = taproot_wallet.getnewaddress()

    # Taproot test addrs are bcrt1p vs native segwit bcrt1q
    assert address.startswith("bcrt1p")

    taproot_wallet.rpc.generatetoaddress(101, address)

    # update the wallet data
    balance = taproot_wallet.update_balance()
    assert balance["trusted"] > 0.0
