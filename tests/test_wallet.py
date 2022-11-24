import pytest, logging

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.specter_error import SpecterError

logger = logging.getLogger(__name__)


@pytest.mark.slow
def test_createpsbt(
    bitcoin_regtest: BitcoindPlainController,
    funded_ghost_machine_wallet: Wallet,
    funded_taproot_wallet: Wallet,
):
    wallet = funded_ghost_machine_wallet
    wallet.address_index = 0
    assert (
        wallet.getnewaddress() == "bcrt1qgzmq6e3tn67kveryf2je6nd3nv4txef4sl8wre"
    )  # Address #1
    assert wallet.amount_total == 20
    # Spending more coins than we have
    random_address = "bcrt1q7mlxxdna2e2ufzgalgp5zhtnndl7qddlxjy5eg"  # Does not belong to the ghost machine wallet
    with pytest.raises(
        SpecterError,
        match="Wallet ghost_machine does not have sufficient funds to make the transaction.",
    ):
        psbt = wallet.createpsbt(
            [random_address],
            [21],
            True,
            0,
            1,
        )
    unspents = wallet.rpc.listunspent()
    selected_coin = [{"txid": unspents[0]["txid"], "vout": unspents[0]["vout"]}]
    psbt = wallet.createpsbt(
        [random_address],
        [19],
        False,  # Important because otherwise there is no change output!
        0,
        1,
        selected_coins=selected_coin,  # Selecting only one UTXO since input ordering seems to also be random in Core.
    )
    assert len(psbt["tx"]["vin"]) == 1
    assert len(psbt["inputs"]) == 1

    # Input fields
    assert (
        psbt["inputs"][0]["bip32_derivs"][0]["pubkey"]
        == "0330955ab511845fb48fc5739da551875ed54fa1f2fdd4cf77f3473ce2cffb4c75"
    )
    assert psbt["inputs"][0]["bip32_derivs"][0]["path"] == "m/84h/1h/0h/0/1"
    assert psbt["inputs"][0]["bip32_derivs"][0]["master_fingerprint"] == "8c24a510"

    # Output fields
    for output in psbt["outputs"]:  # The ordering of the outputs is random
        if output["change"] == False:
            assert output["address"] == "bcrt1q7mlxxdna2e2ufzgalgp5zhtnndl7qddlxjy5eg"
        else:
            assert output["is_mine"] == True
            assert (
                output["bip32_derivs"][0]["pubkey"]
                == "02251fe2ee4bc43729b0903ffadbcf846d9e6acbb3aa593b09d60085645cbe3653"
            )
            assert output["bip32_derivs"][0]["path"] == "m/84h/1h/0h/1/0"

    # Taproot fields (could be moved to a dedicated test of taproot functionalites in the future)
    taproot_wallet = funded_taproot_wallet
    assert taproot_wallet.is_taproot == True
    address = taproot_wallet.getnewaddress()
    assert address.startswith("bcrt1p")
    assert taproot_wallet.amount_total == 20
    # Let's keep the random address so we have a "mixed" set of outputs: segwit and taproot
    psbt = taproot_wallet.createpsbt(
        [random_address],
        [3],
        False,
        0,
        1,
    )
    # Input fields
    assert psbt["inputs"][0]["taproot_bip32_derivs"][0]["path"] == "m/86h/1h/0h/0/1"
    assert (
        psbt["inputs"][0]["taproot_bip32_derivs"][0]["master_fingerprint"] == "8c24a510"
    )
    assert psbt["inputs"][0]["taproot_bip32_derivs"][0]["leaf_hashes"] == []
    complete_pubkey = (
        "0274fea50d7f2a69489c2d2a146e317e02f47ad032e81b35fe6059e066670a100e"
    )
    assert (
        psbt["inputs"][0]["taproot_bip32_derivs"][0]["pubkey"] == complete_pubkey[2:]
    )  # The pubkey is "xonly", for details: https://embit.rocks/#/api/ec/public_key?id=xonly
    # Output fields
    for output in psbt["outputs"]:
        if output["change"] == False:
            assert output["address"] == "bcrt1q7mlxxdna2e2ufzgalgp5zhtnndl7qddlxjy5eg"
        else:
            assert output["taproot_bip32_derivs"][0]["path"] == "m/86h/1h/0h/1/0"
            assert (
                output["taproot_bip32_derivs"][0]["pubkey"]
                == "85b747f5ffc1a1ff951790771c86b24725e283afb2d7e5b8392858bc04f5d05c"
            )
            assert (
                output["taproot_bip32_derivs"][0]["pubkey"]
                == output["taproot_internal_key"]
            )
            assert output["taproot_bip32_derivs"][0]["leaf_hashes"] == []


@pytest.mark.slow
def test_check_utxo_and_amounts(funded_hot_wallet_1: Wallet):
    wallet = funded_hot_wallet_1
    # Let's first prepare some locked txids
    unspents = wallet.rpc.listunspent()  # to be able to ref in stable way
    wallet.check_utxo()
    # 10 transactions + 2 unconfirmed
    assert len(wallet.full_utxo) == 12
    # none are locked
    assert len([tx for tx in wallet.full_utxo if tx["locked"]]) == 0
    # Freeze 2 UTXO
    # ["txid:vout", "txid:vout"]
    wallet.toggle_freeze_utxo(
        [
            f"{unspents[0]['txid']}:{unspents[0]['vout']}",
            f"{unspents[1]['txid']}:{unspents[1]['vout']}",
        ]
    )
    # still 12 utxo with 2 unconfirmed
    wallet.check_utxo()
    assert len(wallet.full_utxo) == 12
    # 2 are locked
    assert len([tx for tx in wallet.full_utxo if tx["locked"]]) == 2

    # Check total amount
    assert wallet.amount_total == 15
    # Check confirmed amount
    assert wallet.amount_confirmed == 10
    # Check unconfirmed amount
    assert wallet.amount_unconfirmed == 5
    # Check frozen amount
    assert wallet.amount_frozen == 2
    # Check available amount
    assert wallet.amount_available == 13  # total - frozen
    # Check immature amount
    address = wallet.getnewaddress()
    wallet.rpc.generatetoaddress(1, address)
    wallet.update_balance()
    assert (
        round(wallet.amount_immature, 1) == 50
        or round(wallet.amount_immature, 1) == 25
        or round(wallet.amount_immature, 1) == 12.5
        or round(wallet.amount_immature, 2) == 6.25
    )
    # Check locked unsigned amount (we need to create a PSBT for that)
    selected_coins = [
        {"txid": u["txid"], "vout": u["vout"]}
        for u in [unspents[2], unspents[3], unspents[4]]
    ]
    selected_coins_amount_sum = (
        unspents[2]["amount"] + unspents[3]["amount"] + unspents[4]["amount"]
    )
    assert (
        selected_coins_amount_sum == 3
    )  # Check funded_hot_wallet_1 in fix_devices_and_wallets.py for the amounts give to certain address ranges
    random_address = "bcrt1q7mlxxdna2e2ufzgalgp5zhtnndl7qddlxjy5eg"
    psbt = wallet.createpsbt(
        [random_address],
        [selected_coins_amount_sum],
        True,
        0,
        1,
        selected_coins=selected_coins,
    )
    assert wallet.amount_locked_unsigned == selected_coins_amount_sum
    wallet.delete_pending_psbt(psbt["tx"]["txid"])
    assert wallet.amount_locked_unsigned == 0
