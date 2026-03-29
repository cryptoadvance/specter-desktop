import json
import random
import re
import time
from typing import List
import pytest, logging
from embit.descriptor import Descriptor as EmbitDescriptor
from cryptoadvance.specter.util.psbt import SpecterPSBT
from cryptoadvance.specter.commands.psbt_creator import PsbtCreator
from cryptoadvance.specter.wallet.txlist import WalletAwareTxItem
from cryptoadvance.specter.device import Device

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.wallet import Wallet
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.specter_error import SpecterError
from fix_devices_and_wallets import create_hot_wallet_device, create_hot_segwit_wallet

logger = logging.getLogger(__name__)


def send_helper(specter_regtest_configured: Specter, wallet: Wallet, device: Device):
    """A small heper method to send some fund with a hot-wallet. Maybe this should be in wallet.py ?
    To understand der PSBT-workflow, i like this article:
    https://github.com/bitcoin/bitcoin/blob/master/doc/psbt.md
    """
    # sending some funds is quite complicated:
    request_json = """
        {
            "recipients" : [
                { 
                    "address": "bcrt1q3kfetuxpxvujasww6xas94nawklvpz0e52uw8a",
                    "amount": 0.2,
                    "unit": "btc",
                    "label": "someLabel"
                }
            ],
            "rbf_tx_id": "",
            "subtract_from": "0",
            "fee_rate": "64",
            "rbf": true
        }
    """

    psbt_creator: PsbtCreator = PsbtCreator(
        specter_regtest_configured, wallet, "json", request_json=request_json
    )

    psbt_dict = psbt_creator.create_psbt(wallet)
    psbt = psbt_creator.psbt_as_object

    b64psbt = str(psbt_dict["base64"])
    signed_psbt = specter_regtest_configured.device_manager.get_by_alias(
        device.alias
    ).sign_psbt(b64psbt, wallet, "")

    if signed_psbt["complete"]:
        raw = wallet.rpc.finalizepsbt(signed_psbt["psbt"])
    psbt.update(signed_psbt["psbt"], raw)
    specter_regtest_configured.broadcast(raw["hex"])


def test_txlist(
    bitcoin_regtest: BitcoindPlainController,
    specter_regtest_configured: Specter,
    hot_wallet_device_1: Device,
    hot_ghost_machine_device,
    caplog,
):
    """this is very similiar of what you can find in fix_devices_and_wallets.py but here you get a failure and nor an error
    (Always search for failures first before checking errors)
        so this should speed up the fixing process although it's a duplication.
    """
    caplog.set_level(logging.DEBUG)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
    wallet = create_hot_segwit_wallet(
        specter_regtest_configured,
        hot_wallet_device_1,
        f"a_hotwallet_{random.randint(0, 999999)}",
    )
    assert len(wallet.txlist()) == 0
    for i in range(0, 10):
        bitcoin_regtest.testcoin_faucet(wallet.getnewaddress(), amount=1)

    # Send some funds somewhere
    send_helper(specter_regtest_configured, wallet, hot_wallet_device_1)

    wallet.update()
    bitcoin_regtest.get_rpc().generatetoaddress(1, wallet.getnewaddress())
    for i in range(0, 2):
        bitcoin_regtest.testcoin_faucet(
            wallet.getnewaddress(),
            amount=2.5,
            confirm_payment=False,
        )
    time.sleep(5)  # needed for tx to propagate
    wallet.update()

    wallet.fetch_transactions()
    txlist: List(WalletAwareTxItem) = wallet.txlist()
    assert txlist[0].__class__ == WalletAwareTxItem

    tx: WalletAwareTxItem = txlist[0]
    psbt = tx.psbt
    print(psbt)

    print(
        "mine \t category \t flow_amount \t blockh \t time \t conflicts \t #conf \t vsize \t fee"
    )
    print("-" * 100)
    tx: WalletAwareTxItem
    for tx in txlist:
        print(
            f"{tx.ismine} \t {tx.category:<8} \t {tx.flow_amount: {2}.{3}} \t\t {tx.blockheight} \
\t {tx.time} \t {tx.conflicts} \t\t {tx.confirmations} \t  {tx.vsize} \t {tx['fee']}"
        )
        assert tx.ismine
        assert tx.category in ["receive", "generate", "send"]
        assert tx.flow_amount > 0.9 or tx.flow_amount < 0.2
        assert tx.blockheight is None or tx.blockheight > 200
        assert tx.time > 1673512597
        assert tx.conflicts == None
        assert tx.confirmations >= 0

    # 12 txs
    assert len(wallet.txlist()) == 14
    # two of them are unconfirmed
    assert len([tx for tx in wallet.txlist() if tx["confirmations"] == 0]) == 2

    assert wallet.address_index == 15
    assert wallet._addresses.max_used_index(change=False) == 14
    # -1 is a magic value which is returned if no change addresses has been used
    assert wallet._addresses.max_used_index(change=True) == -1

    number_of_additional_txs = 200
    for i in range(0, number_of_additional_txs):
        bitcoin_regtest.testcoin_faucet(
            wallet.getnewaddress(),
            amount=2.5,
            confirm_payment=False,
        )
    wallet.fetch_transactions()

    assert wallet.address_index == 15 + number_of_additional_txs
    assert (
        wallet._addresses.max_used_index(change=False)
        == 14 + number_of_additional_txs + 1
    )
    assert wallet._addresses.max_used_index(change=True) == -1


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
    psbt_dict = psbt.to_dict()
    assert len(psbt_dict["tx"]["vin"]) == 1
    assert len(psbt_dict["inputs"]) == 1

    # Input fields
    assert (
        psbt_dict["inputs"][0]["bip32_derivs"][0]["pubkey"]
        == "0330955ab511845fb48fc5739da551875ed54fa1f2fdd4cf77f3473ce2cffb4c75"
    )
    assert psbt_dict["inputs"][0]["bip32_derivs"][0]["path"] == "m/84h/1h/0h/0/1"
    assert psbt_dict["inputs"][0]["bip32_derivs"][0]["master_fingerprint"] == "8c24a510"

    # Output fields
    for output in psbt_dict["outputs"]:  # The ordering of the outputs is random
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
    psbt_dict = psbt.to_dict()
    # Input fields
    assert (
        psbt_dict["inputs"][0]["taproot_bip32_derivs"][0]["path"] == "m/86h/1h/0h/0/1"
    )
    assert (
        psbt_dict["inputs"][0]["taproot_bip32_derivs"][0]["master_fingerprint"]
        == "8c24a510"
    )
    assert psbt_dict["inputs"][0]["taproot_bip32_derivs"][0]["leaf_hashes"] == []
    complete_pubkey = (
        "0274fea50d7f2a69489c2d2a146e317e02f47ad032e81b35fe6059e066670a100e"
    )
    assert (
        psbt_dict["inputs"][0]["taproot_bip32_derivs"][0]["pubkey"]
        == complete_pubkey[2:]
    )  # The pubkey is "xonly", for details: https://embit.rocks/#/api/ec/public_key?id=xonly
    # Output fields
    for output in psbt_dict["outputs"]:
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
    wallet.delete_pending_psbt(psbt.to_dict()["tx"]["txid"])
    assert wallet.amount_locked_unsigned == 0


@pytest.mark.slow
def test_multiple_outputs_in_one_tx(
    funded_ghost_machine_wallet: Wallet,
    funded_hot_wallet_1: Wallet,
    hot_wallet_device_1,
):
    receiving_wallet = funded_ghost_machine_wallet
    spending_wallet = funded_hot_wallet_1
    # Ghost machine addresses (high address index)
    address_list = [
        "bcrt1qfhxsdnrquh63g7u9f25mmucsavsszz6hqym2rs",
        "bcrt1qm2hl7qqaz7ap9279vphdrxey97005wx7rm7k7n",
        "bcrt1qd5prsvv2kktulyc4a4gj0y6frszmux0wkzafxu",
    ]

    # Create a PSBT with those three addresses, convert it to a transaction and send this transaction
    psbt = spending_wallet.createpsbt(address_list, [1, 2, 3], False, 0, 1)
    signed_psbt = hot_wallet_device_1.sign_psbt(psbt.to_string(), spending_wallet)
    transaction = spending_wallet.rpc.finalizepsbt(signed_psbt["psbt"])
    transaction_hex = transaction["hex"]
    spending_wallet.rpc.sendrawtransaction(transaction_hex)

    # Check the full utxo list of the receiving wallet
    receiving_wallet.check_utxo()
    full_utxo = receiving_wallet.full_utxo
    assert len(full_utxo) == 4  # The wallet already has one UTXO from being funded
    assert full_utxo[0]["amount"] == 1
    assert full_utxo[1]["amount"] == 2
    assert full_utxo[2]["amount"] == 3
    assert full_utxo[3]["amount"] == 20  # The funding UTXO

    # Confirming doesn't change anything since check_utxo() calls listunspent with 0 blocks as minconf argument
    random_address = "bcrt1q7mlxxdna2e2ufzgalgp5zhtnndl7qddlxjy5eg"  # Does not belong to the ghost machine wallet
    spending_wallet.rpc.generatetoaddress(
        1, random_address
    )  # We don't need the confirmation,
    receiving_wallet.check_utxo()
    assert len(full_utxo) == 4
    assert full_utxo[0]["amount"] == 1
    assert full_utxo[1]["amount"] == 2
    assert full_utxo[2]["amount"] == 3
    assert full_utxo[3]["amount"] == 20


@pytest.mark.slow
def test_account_map_combined_descriptor(funded_hot_wallet_1: Wallet):
    """
    Test that account_map property returns a combined descriptor with <0;1> syntax
    instead of just the receive descriptor with /0/*
    
    When exporting wallets, only the receive descriptor /0/* was included,
    but it should include both receive and change addresses using multipath descriptors.
    """
    wallet = funded_hot_wallet_1
    
    # Parse the account_map JSON
    account_map_dict = json.loads(wallet.account_map)
    
    # Check that descriptor key exists
    assert "descriptor" in account_map_dict
    descriptor_str = account_map_dict["descriptor"]
    
    # The descriptor should use BIP 389 multipath syntax <0;1>
    # not just the receive path /0/*
    assert "<0;1>" in descriptor_str, (
        f"Expected descriptor with <0;1> multipath syntax, "
        f"but got: {descriptor_str}"
    )
    
    # Should not have single-branch /0/* or /1/* in the descriptor
    # Check that it doesn't end with /0/* followed by checksum or /1/* followed by checksum
    # Note: Descriptor checksums use charset "qpzry9x8gf2tvdw0s3jn54khce6mua7l" (lowercase + digits only)
    # but we include uppercase for future-proofing
    assert not re.search(r'/0/\*#[a-zA-Z0-9]+$', descriptor_str), (
        f"Descriptor should not end with /0/* (receive only), "
        f"got: {descriptor_str}"
    )
    assert not re.search(r'/1/\*#[a-zA-Z0-9]+$', descriptor_str), (
        f"Descriptor should not end with /1/* (change only), "
        f"got: {descriptor_str}"
    )
    
    # Verify it has a checksum (format: descriptor#checksum)
    assert "#" in descriptor_str, (
        f"Descriptor should have a checksum, got: {descriptor_str}"
    )
    
    # Verify the descriptor can be parsed and has 2 branches
    parsed_desc = EmbitDescriptor.from_string(descriptor_str)
    assert parsed_desc.num_branches == 2, (
        f"Descriptor should have 2 branches (receive and change), "
        f"got {parsed_desc.num_branches}"
    )
