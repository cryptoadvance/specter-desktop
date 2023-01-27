import json
import os
import shutil
import time
from binascii import hexlify
from datetime import datetime
from pathlib import Path
from tokenize import Floatnumber
from typing import List

import pytest
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.txlist import TxItem, TxList, WalletAwareTxItem
from cryptoadvance.specter.util.psbt import (
    SpecterInputScope,
    SpecterOutputScope,
    SpecterPSBT,
    SpecterScope,
)
from embit.descriptor import Descriptor
from embit.descriptor.arguments import Key
from embit.networks import NETWORKS
from embit.psbt import PSBT, InputScope, OutputScope
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from mock import MagicMock, PropertyMock

descriptor = "pkh([78738c82/84h/1h/0h]vpub5YN2RvKrA9vGAoAdpsruQGfQMWZzaGt3M5SGMMhW8i2W4SyNSHMoLtyyLLS6EjSzLfrQcbtWdQcwNS6AkCWne1Y7U8bt9JgVYxfeH9mCVPH/1/*)"
# The example transaction from a regtest

# 42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e
with open("tests/xtestdata_txlist/tx1_confirmed.json") as f:
    tx1_confirmed = json.load(f)

#
with open("tests/xtestdata_txlist/tx2_unconfirmed.json") as f:
    tx2_unconfirmed = json.load(f)

with open("tests/xtestdata_txlist/tx2_confirmed.json") as f:
    tx2_confirmed = json.load(f)

with open("tests/xtestdata_txlist/tx2_confirmed2.json") as f:
    tx2_confirmed2 = json.load(f)


def calc_descriptor(wrpc) -> Descriptor:
    """calculates one descriptor via a wallet_rpc , most importantly:
    replace("/0/", "/{0,1}/")
    """
    i = 0
    for desc in wrpc.listdescriptors()["descriptors"]:
        i += 1
        # print(f"{i} {desc}")
        if desc["desc"].startswith("wpkh([") and not desc["internal"]:
            descriptor = desc

    # We need One descriptor for both, receiving and change-addresses. However, core
    # delivers two of them, one for each.
    # So we take the receiving one, and create that special form out of it:
    descriptor = descriptor["desc"].replace("/0/", "/{0,1}/")
    descriptor = Descriptor.from_string(descriptor)
    return descriptor


def calc_parent_mock(wrpc, parent_mock):

    # The wallet is not directly passed but via the parent which
    # holds the wallet_rpc and the descriptor describing the wallet

    # mock the property rpc to be wallet rpc
    type(parent_mock).rpc = PropertyMock(return_value=wrpc)
    # so here is the matching descriptor:

    print("\nDESCRIPTOR\n==========")
    descriptor = calc_descriptor(wrpc)
    print("Our descriptor:")
    print(descriptor)
    print("\n")
    type(parent_mock).descriptor = PropertyMock(return_value=descriptor)
    return parent_mock


@pytest.fixture
def parent_mock(bitcoin_regtest):
    """A Mock implementing AbstractTxListContext and AbstractTxContext"""
    parent_mock = MagicMock()
    # AbstractTxListContext:
    type(parent_mock).rpc = PropertyMock(return_value=bitcoin_regtest.get_rpc())
    assert parent_mock.rpc.getblockchaininfo()["chain"] == "regtest"
    type(parent_mock).chain = PropertyMock(return_value="regtest")
    assert parent_mock.chain == "regtest"
    # AbstractTxContext
    type(parent_mock).network = PropertyMock(return_value=NETWORKS["regtest"])
    # omit descriptor!
    return parent_mock


def test_understandTransaction():
    mytx: Transaction = Transaction.from_string(tx1_confirmed["hex"])
    assert mytx.version == 2
    assert mytx.locktime == 415

    assert type(mytx.vin[0]) == TransactionInput
    assert (
        hexlify(mytx.vin[0].txid)
        == b"c7c9dd852fa9cbe72b2f6e3b2eeba1a2b47dc4422b3719a55381be8010d7993f"
    )

    assert type(mytx.vout[0]) == TransactionOutput
    assert mytx.vout[0].value == 1999999890  # sats
    assert (
        hexlify(mytx.txid())
        == b"42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e"
    )

    # The computed txid is the same than the input
    assert mytx.txid().hex() == tx1_confirmed["txid"]


def test_TxItem_load(empty_data_folder):
    fname = "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e.bin"
    shutil.copyfile(
        f"tests/xtestdata_txlist/{fname}", os.path.join(empty_data_folder, fname)
    )
    mytxitem = TxItem(
        None,
        [],
        empty_data_folder,
        arbitrary_key=1642182445,  # arbitrary stuff can get passed
        txid="c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e",
    )
    mytxitem_copy = mytxitem.copy()
    # The property is loading the tx from disk
    assert type(mytxitem.tx) == Transaction
    assert type(mytxitem_copy.tx) == Transaction
    assert (
        mytxitem.txid
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )
    assert (
        mytxitem_copy.txid
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )
    assert (
        mytxitem.tx.txid().hex()
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )
    assert (
        mytxitem_copy.tx.txid().hex()
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )
    assert mytxitem["arbitrary_key"] == 1642182445
    assert mytxitem_copy["arbitrary_key"] == 1642182445


def test_TxItem(empty_data_folder):
    # those two arrays could have been implemented as dict and need
    # therefore same size
    assert len(TxItem.type_converter) == len(TxItem.columns)
    mytxitem = TxItem(
        None,
        [],
        empty_data_folder,
        hex=tx1_confirmed["hex"],
        blocktime=1642182445,  # arbitrary stuff can get passed
    )
    assert type(mytxitem.tx) == Transaction  # the parsed Tx from the hex
    assert (
        mytxitem.txid
        == "42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e"
    )
    assert (
        str(mytxitem)
        == "42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e"
    )
    assert (
        mytxitem.__repr__()
        == "TxItem(42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e with hex)"
    )
    # a TxItem pretty much works like a dict with some extrafunctionality
    assert mytxitem["blocktime"] == 1642182445
    # We can also add data after the fact
    mytxitem["some_data"] = 123
    assert mytxitem["some_data"] == 123
    assert mytxitem.copy()["some_data"] == 123
    # Don't do that with reserved keys which have meaning:
    mytxitem["confirmations"] = 123
    assert (
        mytxitem["confirmations"] == 123
    )  # might work for the instance itself but ...
    assert not mytxitem.copy()["confirmations"] == 123  # not for the copy

    assert type(mytxitem.tx.vout) == list
    # It's not saved yet:
    assert not os.listdir(empty_data_folder)
    # let's save:
    mytxitem.dump()
    assert os.listdir(empty_data_folder)
    mydict = dict(mytxitem)


def test_WalletAwareTxItem_fromTxItem(bitcoin_regtest, parent_mock, empty_data_folder):
    result = bitcoin_regtest.get_rpc().createwallet(
        "test_WalletAwareTxItem_fromTxItem", False, False, "", False, True
    )
    wrpc = bitcoin_regtest.get_rpc().wallet("test_WalletAwareTxItem_fromTxItem")
    parent_mock = calc_parent_mock(wrpc, parent_mock)
    # Let's fund the wallet
    txid_funding_addr = wrpc.getnewaddress()
    print(f"address: {txid_funding_addr}")
    txid_funding = bitcoin_regtest.testcoin_faucet(txid_funding_addr, amount=1)
    print(f"balance: {wrpc.getbalances()['mine']['trusted']}")
    assert wrpc.getbalances()["mine"]["trusted"] == 1
    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_funding
    )
    mywalletawaretxitem_copy = mywalletawaretxitem.copy()
    assert mywalletawaretxitem.flow_amount == mywalletawaretxitem_copy.flow_amount
    assert mywalletawaretxitem.txid == mywalletawaretxitem_copy.txid


def test_WalletAwareTxItem(bitcoin_regtest, parent_mock, empty_data_folder):
    # those two arrays could have been implemented as dict and need
    # therefore same size
    assert len(WalletAwareTxItem.type_converter) == len(WalletAwareTxItem.columns)

    # No testing of a WalletAwareTxItem if you don't have a wallet
    result = bitcoin_regtest.get_rpc().createwallet(
        "test_WalletAwareTxItem", False, False, "", False, True
    )
    wrpc = bitcoin_regtest.get_rpc().wallet("test_WalletAwareTxItem")
    parent_mock = calc_parent_mock(wrpc, parent_mock)

    # Let's fund the wallet
    print("=========================================")
    print("\nFUNDING TX (1btc)")
    print("=========================================")
    txid_funding_addr = wrpc.getnewaddress()
    print(f"address: {txid_funding_addr}")
    txid_funding = bitcoin_regtest.testcoin_faucet(txid_funding_addr, amount=1)
    print(f"balance: {wrpc.getbalances()['mine']['trusted']}")
    assert wrpc.getbalances()["mine"]["trusted"] == 1

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_funding
    )

    print("INPUTS\n------")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n------")
    for out in mywalletawaretxitem.psbt.outputs:
        print(str(out))
    assert mywalletawaretxitem.flow_amount == 1
    assert mywalletawaretxitem.category == "receive"

    # Let's do a selftransfer
    print("=========================================")
    print("\n\nSELFTRANSFER TX (0.1btc)")
    print("=========================================")
    txid_selftransfer_addr = wrpc.getnewaddress()
    print(f"address = {txid_selftransfer_addr}")
    txid_selftransfer = wrpc.sendtoaddress(txid_selftransfer_addr, 0.1)
    print(f"balance: {wrpc.getbalances()['mine']['trusted']}")
    assert wrpc.getbalances()["mine"]["trusted"] < 1
    assert wrpc.getbalances()["mine"]["trusted"] > 0.99

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_selftransfer
    )

    print("INPUTS\n------")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n-------")
    print(str(mywalletawaretxitem.psbt.outputs[0]))
    print(str(mywalletawaretxitem.psbt.outputs[1]))

    print("\n\nOUTPUT[0] INVESTIGATION\n====================")
    assert mywalletawaretxitem.tx.is_segwit
    assert type(mywalletawaretxitem.tx.vout[0]) == TransactionOutput

    address = mywalletawaretxitem.tx.vout[0].script_pubkey.address(NETWORKS["regtest"])
    # Core thinks that the address belongs to the wallet
    assert wrpc.getaddressinfo(address)["ismine"]

    print(
        f"address (via my.tx.vout[0].script_pubkey.address):        {mywalletawaretxitem.tx.vout[0].script_pubkey.address(NETWORKS['regtest'])}"
    )

    specter_psbt = mywalletawaretxitem.psbt
    embit_psbt = specter_psbt.psbt

    # Some Type Checks
    assert type(specter_psbt) == SpecterPSBT
    assert type(specter_psbt.psbt) == PSBT
    assert type(specter_psbt.psbt.outputs[0]) == OutputScope
    assert type(specter_psbt.outputs[0]) == SpecterOutputScope
    assert type(specter_psbt.outputs[0].scope) == OutputScope
    assert type(specter_psbt.outputs[0].scope.vout) == TransactionOutput

    # The ways to get the addresses ...
    address = specter_psbt.outputs[0].address
    print(f"address (via specter_psbt.SpecterOutputScope.address):    {address}")
    assert address == specter_psbt.outputs[0].scope.script_pubkey.address(
        NETWORKS["regtest"]
    )
    assert address == specter_psbt.outputs[0].scope.vout.script_pubkey.address(
        NETWORKS["regtest"]
    )
    assert address == embit_psbt.outputs[0].script_pubkey.address(NETWORKS["regtest"])

    # Let's check the two outputs
    # Order is not reliable, so make fixed indexes
    if specter_psbt.outputs[0].address == txid_selftransfer_addr:
        rcv_idx = 0
        cha_idx = 1
    else:
        rcv_idx = 1
        cha_idx = 0
    # The receiving one:
    assert (
        specter_psbt.outputs[rcv_idx].scope.vout.value == 10000000
    )  # 0.1 btc == 10 mil sats
    assert specter_psbt.outputs[rcv_idx].is_mine
    assert specter_psbt.outputs[
        rcv_idx
    ].is_receiving  # the 0 output is the receiving one (0.1)
    assert not specter_psbt.outputs[rcv_idx].is_change

    # The change one:
    assert specter_psbt.outputs[cha_idx].scope.vout.value < 90000000
    assert specter_psbt.outputs[cha_idx].is_mine
    assert specter_psbt.outputs[cha_idx].is_change
    assert not specter_psbt.outputs[cha_idx].is_receiving

    # amounts
    assert specter_psbt.inputs[0].float_amount == 1
    assert specter_psbt.outputs[rcv_idx].float_amount == 0.1
    assert specter_psbt.outputs[cha_idx].float_amount >= 0.89
    assert mywalletawaretxitem.flow_amount >= -0.0001  # the wallet lost some fees
    assert mywalletawaretxitem.category == "selftransfer"

    print("=========================================")
    print("\n\nOutgoing-Transaction (0.2 btc)")
    print("=========================================")

    txid_outgoing_addr = "n4MN27Lk7Yh3pwfjCiAbRXtRVjs4Uk67fG"
    print(f"address = {txid_outgoing_addr}")
    txid_outgoing = wrpc.sendtoaddress(txid_outgoing_addr, 0.2)
    print(f"balance: {wrpc.getbalances()['mine']['trusted']}")
    assert wrpc.getbalances()["mine"]["trusted"] < 0.8

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_outgoing
    )

    print("INPUTS\n-------")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n------")
    for out in mywalletawaretxitem.psbt.outputs:
        print(str(out))

    # Let's check the two outputs
    # Order is not reliable, so make fixed indexes
    specter_psbt = mywalletawaretxitem.psbt
    if specter_psbt.outputs[0].address == txid_outgoing_addr:
        snd_idx = 0
        cha_idx = 1
    else:
        snd_idx = 1
        cha_idx = 0
    # The sending one:
    assert not specter_psbt.outputs[snd_idx].is_mine
    assert not specter_psbt.outputs[
        snd_idx
    ].is_receiving  # the 0 output is the receiving one (0.1)
    assert not specter_psbt.outputs[snd_idx].is_change

    # The change one:
    assert specter_psbt.outputs[cha_idx].is_mine
    assert specter_psbt.outputs[cha_idx].is_change
    assert not specter_psbt.outputs[cha_idx].is_receiving

    # amounts
    assert specter_psbt.inputs[0].float_amount >= 0.8
    assert specter_psbt.outputs[snd_idx].float_amount == 0.2
    assert specter_psbt.outputs[cha_idx].float_amount >= 0.6
    assert mywalletawaretxitem.flow_amount <= -0.2  # 0.2 wallet lost plus some fees


def test_txlist(empty_data_folder, parent_mock, bitcoin_regtest):
    # assert funded_hot_wallet_1.rpc()
    # Non Empty hotwallet using descriptors
    result = bitcoin_regtest.get_rpc().createwallet(
        "mywallet_for_test_txlist", False, False, "", False, True
    )
    wrpc = bitcoin_regtest.get_rpc().wallet("mywallet_for_test_txlist")
    parent_mock = calc_parent_mock(wrpc, parent_mock)

    # so here is the matching descriptor:
    descriptor: Descriptor = calc_descriptor(wrpc)
    print(f"Descriptor: {descriptor}")

    # mock the property rpc to be wallet rpc
    type(parent_mock).rpc = PropertyMock(return_value=wrpc)

    for i in range(0, 10):
        bitcoin_regtest.testcoin_faucet(wrpc.getnewaddress(), amount=0.1)

    filename = os.path.join(empty_data_folder, "my_filename.csv")
    mytxlist = TxList(filename, parent_mock, MagicMock())

    print("How do the Txs look like?\n===================")

    tx_from_listtransactions = wrpc.listtransactions()[-1]
    tx = tx_from_listtransactions
    print("a transaction as it looks like from listtransaction:")
    # print(tx)
    print(f"  those keys: {sorted(tx.keys())}")
    print()
    tx_from_gettransaction = wrpc.gettransaction(tx["txid"])
    tx = tx_from_gettransaction
    print("A tx from gettransaction")
    # print(tx)
    print(f"  those keys: {sorted(tx.keys())}")
    print()
    print("A tx from decoderawtransaction")
    hex = tx["hex"]
    tx_from_decoderawtransaction = wrpc.decoderawtransaction(hex)
    tx = tx_from_decoderawtransaction
    # print(tx)
    print(f"  those keys: {sorted(tx.keys())}")
    print(tx["vout"])

    # print("So now we create a PSBT out of that: ")
    # psbt = SpecterPSBT.from_transaction(hex, parent_mock.descriptor, parent_mock.network)
    # print(psbt)

    mytxlist.add({tx["txid"]: tx_from_gettransaction})
    assert type(mytxlist[tx["txid"]]) == WalletAwareTxItem
    assert type(mytxlist[tx["txid"]].psbt) == SpecterPSBT

    assert type(mytxlist[tx["txid"]].psbt.outputs[0]) == SpecterOutputScope
    assert type(mytxlist[tx["txid"]].psbt.outputs[0].float_amount) == float
    assert len(mytxlist[tx["txid"]].psbt.outputs) == 2
    assert (
        mytxlist[tx["txid"]].psbt.outputs[0].is_mine
        or mytxlist[tx["txid"]].psbt.outputs[1].is_mine
    )

    assert type(mytxlist[tx["txid"]].psbt.inputs[0]) == SpecterInputScope
    print(mytxlist[tx["txid"]].psbt.inputs[0].scope)
    assert type(mytxlist[tx["txid"]].psbt.inputs[0].scope) == InputScope
    assert type(mytxlist[tx["txid"]].psbt.inputs[0].float_amount) == float

    for tx in mytxlist.values():
        assert tx.flow_amount > 0
    # assert False


def test_txlist_invalidate(empty_data_folder, bitcoin_regtest: BitcoindPlainController):
    def print_time():
        curr_dt = datetime.now()
        print(f"current time\t\t\t\t\t: {int(round(curr_dt.timestamp()))}\n")

    # Setup the infra
    rpc = bitcoin_regtest.get_rpc()
    rpc.mine
    rpc.createwallet("txlist2")
    wrpc = rpc.wallet("txlist2")
    address = wrpc.getnewaddress()
    bitcoin_regtest.testcoin_faucet(address, amount=10, confirm_payment=True)
    # itcoin_regtest.mine(self, address=address, block_count=100)

    # Create the mytxlist
    parent_mock = MagicMock()
    parent_mock.rpc = wrpc
    parent_mock.descriptor = Descriptor.from_string(descriptor)
    assert type(parent_mock.descriptor.key) == Key
    assert parent_mock.descriptor.key.allowed_derivation != None
    assert parent_mock.descriptor.to_string() == descriptor
    filename = os.path.join(empty_data_folder, "my_filename.csv")
    mytxlist = TxList(filename, parent_mock, MagicMock())

    # create a tx

    txid = wrpc.sendtoaddress("bcrt1qsj30deg0fgzckvlrn5757yk55yajqv6dqx0x7u", "1")
    tx_via_core = wrpc.gettransaction(txid)
    print_time()
    assert tx_via_core, "we have created a transaction"
    assert tx_via_core["confirmations"] == 0, "it's not confirmed, yet"
    print(f"TxId: {txid}")
    print(f"Tx via core:\n{tx_via_core}\n")
    assert (
        tx_via_core["time"] == tx_via_core["timereceived"]
    ), "time and timereceived should be the same"
    print(f"timereceived \t\t\t\t\t: {tx_via_core['time']}")
    print_time()

    tx_item = mytxlist.getfetch(txid)
    assert isinstance(tx_item, TxItem), "The tx should get returned via the txlist"
    assert (
        mytxlist[txid] == tx_item
    ), "is should be the same item you get via obtaining it via the dict-method"

    # analyzing the content of the tx
    tx = mytxlist.gettransaction(txid)
    print(f"Tx via cache:\n{tx}\n")
    mpool_hittime = tx["time"]
    assert tx["blockheight"] == None
    print(f"this is the time when the tx hit the mempool {mpool_hittime}")
    print_time()
    print("let's sleep for 2 seconds")
    time.sleep(2)
    print_time()
    # Get the tx confirmed

    bitcoin_regtest.mine(block_count=1)
    print("\n-----------------------mining----------------------------------\n")
    tx_via_core = wrpc.gettransaction(txid)
    assert tx_via_core["confirmations"] == 1, "it should now be broadcasted"
    print(f"Tx via core:\n{tx_via_core}\n")
    print(f"blocktime \t\t\t\t\t: {tx_via_core['blocktime']}")
    print_time()
    print(
        f"Difference of blocktime - current-time:\t\t\t {int(round(datetime.now().timestamp())) - tx_via_core['blocktime']}"
    )
    print(f"How is it possible that this number is negative?")

    assert (
        tx_via_core["blocktime"] > tx_via_core["time"]
    ), "blocktime should be larger than time"

    # optional: invalidate
    # mytxlist.invalidate(txid)

    # get it again
    tx = mytxlist.gettransaction(txid)
    print(f"Tx via cache:\n{tx}\n")
    assert tx["blockheight"], "The tx should now have a blockheight"
    assert tx["blocktime"], "The tx should now have a blocktime"
    assert (
        tx["blocktime"] > mpool_hittime
    ), "The time of the transaction should now be bigger than the time it got hit the mempool"
