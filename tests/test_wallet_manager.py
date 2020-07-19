import json, os
from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.wallet_manager import WalletManager


def test_WalletManager(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder,bitcoin_regtest.get_cli(), "regtest", device_manager)
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('trezor')
    assert device != None
    # Lets's create a wallet with the WalletManager
    wm.create_wallet('a_test_wallet', 1, 'wpkh', [device.keys[5]], [device])
    # The wallet-name gets its filename and therefore its alias
    wallet = wm.wallets['a_test_wallet']
    assert wallet != None
    assert wallet.balance['trusted'] == 0
    assert wallet.balance['untrusted_pending'] == 0
    # this is a sum of both
    assert wallet.fullbalance == 0
    address = wallet.getnewaddress()
    # newly minted coins need 100 blocks to get spendable
    wallet.cli.generatetoaddress(1, address)
    # let's mine another 100 blocks to get these coins spendable
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(100, random_address)
    # update the balance
    wallet.get_balance()
    assert wallet.fullbalance >= 25
   
    # You can create a multisig wallet with the wallet manager like this
    second_device = device_manager.get_by_alias('specter')
    multisig_wallet = wm.create_wallet('a_multisig_test_wallet', 1, 'wsh', [device.keys[7], second_device.keys[0]], [device, second_device])

    assert len(wm.wallets) == 2
    assert multisig_wallet != None
    assert multisig_wallet.fullbalance == 0
    multisig_address = multisig_wallet.getnewaddress()
    multisig_wallet.cli.generatetoaddress(1, multisig_address)
    multisig_wallet.cli.generatetoaddress(100, random_address)
    # update balance
    multisig_wallet.get_balance()
    assert multisig_wallet.fullbalance >= 12.5
    # The WalletManager also has a `wallets_names` property, returning a sorted list of the names of all wallets
    assert wm.wallets_names == ['a_multisig_test_wallet', 'a_test_wallet']

    # You can rename a wallet using the wallet manager using `rename_wallet`, passing the wallet object and the new name to assign to it
    wm.rename_wallet(multisig_wallet, 'new_name_test_wallet')
    assert multisig_wallet.name == 'new_name_test_wallet'
    assert wm.wallets_names == ['a_test_wallet', 'new_name_test_wallet']
    
    # you can also delete a wallet by passing it to the wallet manager's `delete_wallet` method
    # it will delete the json and attempt to remove it from Bitcoin Core
    wallet_fullpath = multisig_wallet.fullpath
    assert os.path.exists(wallet_fullpath)
    wm.delete_wallet(multisig_wallet)
    assert not os.path.exists(wallet_fullpath)
    assert len(wm.wallets) == 1

def test_wallet_createpsbt(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder, bitcoin_regtest.get_cli(), "regtest", device_manager)
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('specter')
    key = Key.from_json({
        "derivation": "m/48h/1h/0h/2h",
        "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "fingerprint": "08686ac6",
        "type": "wsh",
        "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
    })
    wallet = wm.create_wallet('a_second_test_wallet', 1, 'wpkh', [key], [device])
    # Let's fund the wallet with ... let's say 40 blocks a 50 coins each --> 200 coins
    address = wallet.getnewaddress()
    assert address == 'bcrt1qtnrv2jpygx2ef3zqfjhqplnycxak2m6ljnhq6z'
    wallet.cli.generatetoaddress(20, address)
    # in two addresses
    address = wallet.getnewaddress()
    wallet.cli.generatetoaddress(20, address)
    # newly minted coins need 100 blocks to get spendable
    # let's mine another 100 blocks to get these coins spendable
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(110, random_address)
    # update the wallet data
    wallet.get_balance()
    # Now we have loads of potential inputs
    # Let's spend 500 coins
    assert wallet.fullbalance >= 250
    # From this print-statement, let's grab some txids which we'll use for coinselect
    unspents = wallet.cli.listunspent(0)
    # Lets take 3 more or less random txs from the unspents:
    selected_coins = [
        "{},{},{}".format(unspents[5]['txid'], unspents[5]['vout'], unspents[5]['amount']), 
        "{},{},{}".format(unspents[9]['txid'], unspents[9]['vout'], unspents[9]['amount']),
        "{},{},{}".format(unspents[12]['txid'], unspents[12]['vout'], unspents[12]['amount'])
    ]
    selected_coins_amount_sum = unspents[5]['amount'] + unspents[9]['amount'] + unspents[12]['amount']
    number_of_coins_to_spend = selected_coins_amount_sum - 0.1 # Let's spend almost all of them 
    psbt = wallet.createpsbt(random_address, number_of_coins_to_spend, True, 10, selected_coins=selected_coins)
    assert len(psbt['tx']['vin']) == 3
    psbt_txs = [ tx['txid'] for tx in psbt['tx']['vin'] ]
    for coin in selected_coins:
        assert coin.split(",")[0] in psbt_txs

    # Now let's spend more coins than we have selected. This should result in an exception:
    try:
        psbt = wallet.createpsbt(random_address, number_of_coins_to_spend +1, True, 10, selected_coins=selected_coins)
        assert False, "should throw an exception!"
    except SpecterError as e:
        pass

    assert wallet.locked_amount == selected_coins_amount_sum
    assert len(wallet.cli.listlockunspent()) == 3
    assert wallet.full_available_balance == wallet.fullbalance - selected_coins_amount_sum

    wallet.delete_pending_psbt(psbt['tx']['txid'])
    assert wallet.locked_amount == 0
    assert len(wallet.cli.listlockunspent()) == 0
    assert wallet.full_available_balance == wallet.fullbalance

def test_wallet_sortedmulti(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder, bitcoin_regtest.get_cli(), "regtest", device_manager)
    device = device_manager.get_by_alias('trezor')
    second_device = device_manager.get_by_alias('specter')
    for i in range(2):
        if i == 0:
            multisig_wallet = wm.create_wallet('a_multisig_test_wallet', 1, 'wsh', [device.keys[7], second_device.keys[0]], [device, second_device])
        else:
            multisig_wallet = wm.create_wallet('a_multisig_test_wallet', 1, 'wsh', [second_device.keys[0], device.keys[7]], [second_device, device])

        address = multisig_wallet.address
        address_info = multisig_wallet.cli.getaddressinfo(address)
        assert address_info['pubkeys'][0] < address_info['pubkeys'][1]
        
        another_address = multisig_wallet.getnewaddress()
        another_address_info = multisig_wallet.cli.getaddressinfo(another_address)
        assert another_address_info['pubkeys'][0] < another_address_info['pubkeys'][1]
        
        third_address = multisig_wallet.get_address(30)
        third_address_info = multisig_wallet.cli.getaddressinfo(third_address)
        assert third_address_info['pubkeys'][0] < third_address_info['pubkeys'][1]

        change_address = multisig_wallet.change_address
        change_address_info = multisig_wallet.cli.getaddressinfo(change_address)
        assert change_address_info['pubkeys'][0] < change_address_info['pubkeys'][1]

        another_change_address = multisig_wallet.get_address(30, change=True)
        another_change_address_info = multisig_wallet.cli.getaddressinfo(another_change_address)
        assert another_change_address_info['pubkeys'][0] < another_change_address_info['pubkeys'][1]

def test_wallet_labeling(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder, bitcoin_regtest.get_cli(), "regtest", device_manager)
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('specter')
    key = Key.from_json({
        "derivation": "m/48h/1h/0h/2h",
        "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "fingerprint": "08686ac6",
        "type": "wsh",
        "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
    })
    wallet = wm.create_wallet('a_second_test_wallet', 1, 'wpkh', [key], [device])

    address = wallet.address
    assert wallet.getlabel(address) == 'Address #0'
    wallet.setlabel(address, 'Random label')
    assert wallet.getlabel(address) == 'Random label'

    wallet.cli.generatetoaddress(20, address)

    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(100, random_address)
    
    # update utxo
    wallet.getdata()
    # update balance
    wallet.get_balance()

    address_balance = wallet.fullbalance
    assert len(wallet.utxo) == 20
    assert wallet.is_current_address_used
    assert wallet.balance_on_address(address) == address_balance
    assert wallet.balance_on_label('Random label') == address_balance
    assert wallet.addresses_on_label('Random label') == [address]
    assert wallet.utxo_addresses == [address]
    assert wallet.utxo_labels == ['Random label']
    assert wallet.utxo_addresses == [address]

    new_address = wallet.getnewaddress()
    wallet.setlabel(new_address, '')
    wallet.cli.generatetoaddress(20, new_address)

    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(100, random_address)

    wallet.getdata()
    wallet.get_balance()

    assert len(wallet.utxo) == 40
    assert wallet.is_current_address_used
    assert wallet.utxo_on_address(address) == 20
    assert wallet.balance_on_address(new_address) == wallet.fullbalance - address_balance
    assert sorted(wallet.utxo_addresses) == sorted([address, new_address])
    assert sorted(wallet.utxo_labels) == sorted(['Random label', new_address])
    assert sorted(wallet.utxo_addresses) == sorted([address, new_address])
    assert wallet.get_address_name(new_address, -1) == new_address
    assert wallet.get_address_name(new_address, 5) == 'Address #5'
    assert wallet.get_address_name(address, 5) == 'Random label'

    wallet.setlabel(new_address, '')
    third_address = wallet.getnewaddress()

    wallet.getdata()
    assert sorted(wallet.labels) == sorted(['Random label', new_address, 'Address #2'])
    assert sorted(wallet.utxo_labels) == sorted(['Random label', new_address])
    assert sorted(wallet.addresses) == sorted([address, new_address, third_address])
    assert sorted(wallet.utxo_addresses) == sorted([address, new_address])

    wallet.setlabel(third_address, 'Random label')
    wallet.getdata()
    assert sorted(wallet.addresses_on_label('Random label')) == sorted([address, third_address])

def test_wallet_change_addresses(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder, bitcoin_regtest.get_cli(), "regtest", device_manager)
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('specter')
    key = Key.from_json({
        "derivation": "m/48h/1h/0h/2h",
        "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "fingerprint": "08686ac6",
        "type": "wsh",
        "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
    })
    wallet = wm.create_wallet('a_second_test_wallet', 1, 'wpkh', [key], [device])

    address = wallet.address
    change_address = wallet.change_address
    assert wallet.addresses == [address]
    assert wallet.change_addresses == [change_address]
    assert wallet.active_addresses == [address]
    assert wallet.labels == ['Address #0']

    wallet.cli.generatetoaddress(20, change_address)
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(110, random_address)
    wallet.getdata()

    # new change address should be genrated automatically after receiving
    # assert wallet.change_addresses == [change_address, wallet.change_address]
    # This will not work here since Bitcoin Core doesn't count mining rewards in `getreceivedbyaddress`
    # See: https://github.com/bitcoin/bitcoin/issues/14654

    assert wallet.active_addresses == [address, change_address]
    # labels should return only active addresses
    assert wallet.labels == ['Address #0', 'Change #0']

# TODO: Add more tests of the Wallet object
