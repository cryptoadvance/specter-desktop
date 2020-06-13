import os
from cryptoadvance.specter.rpc import RpcError
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.wallets.wallet import Wallet
from cryptoadvance.specter.wallet_manager import WalletManager


def test_WalletManager(bitcoin_regtest, devices_filled_data_folder, device_manager):
    wm = WalletManager(devices_filled_data_folder,bitcoin_regtest.get_cli(), "regtest", device_manager)
    # A wallet-creation needs a device
    device = device_manager.get_by_alias('trezor')
    assert device != None
    # Lets's create a wallet with the WalletManager
    wm.create_simple('a_test_wallet', 'wpkh', device['keys'][5], device)
    # The wallet-name gets its filename and therefore its alias
    wallet = wm.wallets['a_test_wallet']
    assert wallet != None
    assert wallet.getbalances()['trusted'] == 0
    assert wallet.getbalances()['untrusted_pending'] == 0
    # this is a sum of both
    assert wallet.fullbalance == 0
    address = wallet.getnewaddress()
    # newly minted coins need 100 blocks to get spendable
    wallet.cli.generatetoaddress(1, address)
    # let's mine another 100 blocks to get these coins spendable
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    wallet.cli.generatetoaddress(100, random_address)
    # a balance has properties which are caching the result from last call
    assert wallet.fullbalance == 50
   
    # You can create a multisig wallet with the wallet manager like this
    second_device = device_manager.get_by_alias('specter')
    multisig_wallet = wm.create_multi('a_multisig_test_wallet', 1, 'wsh', [device['keys'][7], second_device['keys'][0]], [device, second_device])

    assert len(wm.wallets) == 2
    assert multisig_wallet != None
    assert multisig_wallet.fullbalance == 0
    multisig_address = multisig_wallet.getnewaddress()
    multisig_wallet.cli.generatetoaddress(1, multisig_address)
    multisig_wallet.cli.generatetoaddress(100, random_address)
    # a balance has properties which are caching the result from last call
    assert multisig_wallet.fullbalance == 25
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
    key = {
        "derivation": "m/48h/1h/0h/2h",
        "original": "Vpub5n9kKePTPPGtw3RddeJWJe29epEyBBcoHbbPi5HhpoG2kTVsSCUzsad33RJUt3LktEUUPPofcZczuudnwR7ZgkAkT6N2K2Z7wdyjYrVAkXM",
        "fingerprint": "08686ac6",
        "type": "wsh",
        "xpub": "tpubDFHpKypXq4kwUrqLotPs6fCic5bFqTRGMBaTi9s5YwwGymE8FLGwB2kDXALxqvNwFxB1dLWYBmmeFVjmUSdt2AsaQuPmkyPLBKRZW8BGCiL"
    }
    wallet = wm.create_simple('a_second_test_wallet','wpkh',key,device)
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
    # Now let's spend more coins then we have selected. This should result in an exception:
    try:
        psbt = wallet.createpsbt(random_address, number_of_coins_to_spend +1, True, 10, selected_coins=selected_coins)
        assert False, "should throw an exception!"
    except SpecterError as e:
        pass

# TODO: Add more tests of the Wallet object
