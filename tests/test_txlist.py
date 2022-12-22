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
from cryptoadvance.specter.util.psbt import SpecterScope
from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.txlist import TxItem, TxList, WalletAwareTxItem
from embit.descriptor.arguments import Key
from embit.descriptor import Descriptor
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from embit.psbt import InputScope, OutputScope
from mock import MagicMock, PropertyMock

from cryptoadvance.specter.util.psbt import (
    SpecterInputScope,
    SpecterOutputScope,
    SpecterPSBT,
)


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
    parent_mock.network.return_value = "regtest"
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
    # The property is loading the tx from disk
    assert type(mytxitem.tx) == Transaction
    assert (
        mytxitem.txid
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )
    assert (
        mytxitem.tx.txid().hex()
        == "c518428b318612e60ba8a90ef767a0c6ea0ccf989ed69c3b10b1df537fab850e"
    )


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
    mytxitem["confirmations"] = 123
    assert mytxitem["confirmations"] == 123
    assert type(mytxitem.tx.vout) == list
    # It's not saved yet:
    assert not os.listdir(empty_data_folder)
    # let's save:
    mytxitem.dump()
    assert os.listdir(empty_data_folder)


def test_WalletAwareTxItem(bitcoin_regtest, parent_mock, empty_data_folder):
    # No testing of a WalletAwareTxItem if you don't have a wallet
    result = bitcoin_regtest.get_rpc().createwallet(
        "test_WalletAwareTxItem", False, False, "", False, True
    )
    wrpc = bitcoin_regtest.get_rpc().wallet("test_WalletAwareTxItem")
    # ... with some funds
    txid_funding = bitcoin_regtest.testcoin_faucet(wrpc.getnewaddress(), amount=1)
    assert wrpc.getbalances()["mine"]["trusted"] == 1

    txid_selftransfer = wrpc.sendtoaddress(wrpc.getnewaddress(), 0.1)
    # bitcoin_regtest.get_rpc().generatetoaddress(1, bitcoin_regtest.get_rpc().wallet("").getnewaddress(""))
    assert wrpc.getbalances()["mine"]["trusted"] < 1
    assert wrpc.getbalances()["mine"]["trusted"] > 0.99
    print(wrpc.getbalances())
    txid_outgoing = wrpc.sendtoaddress("n4MN27Lk7Yh3pwfjCiAbRXtRVjs4Uk67fG", 0.2)
    assert wrpc.getbalances()["mine"]["trusted"] < 0.8
    print(wrpc.getbalances())

    # The wallet is not directly passed but via the parent which
    # holds the wallet_rpc and the descriptor describing the wallet

    # mock the property rpc to be wallet rpc
    type(parent_mock).rpc = PropertyMock(return_value=wrpc)
    # so here is the matching descriptor:
    i = 0
    for desc in wrpc.listdescriptors()["descriptors"]:
        print(f"{i}: {desc}")
        i += 1
        if desc["desc"].startswith("wpkh(["):
            descriptor = desc
    print()
    descriptor = wrpc.listdescriptors()["descriptors"][2]
    print(descriptor)
    assert descriptor["desc"].startswith("wpkh([")  # Single Segit
    descriptor = Descriptor.from_string(descriptor["desc"])
    print("Our descriptor:")
    print(descriptor)
    type(parent_mock).descriptor = PropertyMock(return_value=descriptor)

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_funding
    )
    assert mywalletawaretxitem.category == "receive"
    print("Receiving-Transaction:")
    print("\nINPUTS\n=====")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n=====")
    for out in mywalletawaretxitem.psbt.outputs:
        print(str(out))
    assert mywalletawaretxitem.flow_amount == 1

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_selftransfer
    )
    # assert mywalletawaretxitem.category == "selftransfer"
    print("\n\nSelftransfer-Transaction:")
    print("INPUTS\n=======")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n=======")
    for out in mywalletawaretxitem.psbt.outputs:
        print(str(out))
    assert type(mywalletawaretxitem.psbt.outputs[1].scope) == OutputScope
    assert type(mywalletawaretxitem.psbt.outputs[1].scope.vout) == TransactionOutput
    assert mywalletawaretxitem.psbt.outputs[1].scope.vout.value < 89000000
    assert mywalletawaretxitem.psbt.outputs[0].is_mine
    assert mywalletawaretxitem.psbt.outputs[1].is_mine
    # Why not?
    assert mywalletawaretxitem.flow_amount == 0.1

    mywalletawaretxitem = WalletAwareTxItem(
        parent_mock, [], empty_data_folder, txid=txid_outgoing
    )
    # assert mywalletawaretxitem.category == "selftransfer"
    print("\n\nOutgoing-Transaction:")
    print("INPUTS\n=======")
    for inp in mywalletawaretxitem.psbt.inputs:
        print(str(inp))
    print("\nOUTPUTS\n=======")
    for out in mywalletawaretxitem.psbt.outputs:
        print(str(out))
    # why not?
    assert mywalletawaretxitem.psbt.input[0].is_mine
    # Why not?
    assert mywalletawaretxitem.flow_amount == 0.1


def test_txlist(empty_data_folder, parent_mock, bitcoin_regtest):
    # assert funded_hot_wallet_1.rpc()
    # Non Empty hotwallet using descriptors
    result = bitcoin_regtest.get_rpc().createwallet(
        "mywallet", False, False, "", False, True
    )
    wrpc = bitcoin_regtest.get_rpc().wallet("mywallet")
    print(json.dumps(wrpc.listdescriptors()))

    # A new address is by default of type bech32
    print(wrpc.getnewaddress())

    # so here is the matching descriptor:
    descriptor = wrpc.listdescriptors()["descriptors"][0]
    print(f"Descriptor: {descriptor}")

    # mock the property rpc to be wallet rpc
    type(parent_mock).rpc = PropertyMock(return_value=wrpc)

    for i in range(0, 10):
        bitcoin_regtest.testcoin_faucet(wrpc.getnewaddress(), amount=0.1)
    assert bitcoin_regtest.get_rpc().listwallets() == ["", "mywallet"]

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
    assert mytxlist[tx["txid"]].psbt.outputs[0].is_mine

    assert type(mytxlist[tx["txid"]].psbt.inputs[0]) == SpecterInputScope
    print(mytxlist[tx["txid"]].psbt.inputs[0].scope)
    assert type(mytxlist[tx["txid"]].psbt.inputs[0].scope) == InputScope
    assert type(mytxlist[tx["txid"]].psbt.inputs[0].float_amount) == float
    assert mytxlist[tx["txid"]].psbt.inputs[0].is_mine

    for tx in mytxlist.values():
        assert tx.flow_amount < 0
    assert False


def test_txlist_unrelated_tx(empty_data_folder, bitcoin_regtest):
    parent_mock = MagicMock()
    bitcoin_regtest.get_rpc().createwallet("txlist1")
    wrpc = bitcoin_regtest.get_rpc().wallet("txlist1")
    parent_mock.rpc = wrpc

    parent_mock.descriptor = Descriptor.from_string(descriptor)
    assert type(parent_mock.descriptor.key) == Key
    assert parent_mock.descriptor.key.allowed_derivation != None
    assert parent_mock.descriptor.to_string() == descriptor
    filename = os.path.join(empty_data_folder, "my_filename.csv")
    mytxlist = TxList(filename, parent_mock, MagicMock())
    # mytxlist.descriptor = descriptor
    mytxlist.add({tx1_confirmed["txid"]: tx1_confirmed})
    assert mytxlist[tx1_confirmed["txid"]].flow_amount == 0  # makes sense as the
    assert mytxlist[tx1_confirmed["txid"]]["flow_amount"] == 0
    # .add will save implicitely.
    # mytxlist._save()
    with open(filename, "r+") as file:
        # Reading form a file

        assert file.readline().startswith(
            "txid,blockhash,blockheight,time,blocktime,bip125-replaceable,conflicts,vsize,category,address,amount,ismine"
        )
        assert file.readline().startswith(
            "42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e,72523c637e0b93505806564495b1acf915a88bacc45f50e35e8a536becd2f914,,1642494258,1642494258,no,[],,receive,Unknown,19.9999989,False"
        )
    assert len(mytxlist) == 1
    mytxlist.invalidate(tx1_confirmed["txid"])
    assert len(mytxlist) == 0
    assert not Path(filename).is_file()

    # Mock rpc-calls
    mock_rpc = MagicMock()
    mock_rpc.gettransaction.return_value = tx2_confirmed
    mock_parent = MagicMock()
    mock_parent.rpc = mock_rpc
    mytxlist.parent = mock_parent
    mytxlist.getfetch(
        "42f5c9e826e52cde883cde7a6c7b768db302e0b8b32fc52db75ad3c5711b4a9e"
    )

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
