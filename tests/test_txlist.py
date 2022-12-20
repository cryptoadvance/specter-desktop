import json
import os
import time
from binascii import hexlify
from datetime import datetime
from pathlib import Path
from typing import List

from cryptoadvance.specter.process_controller.bitcoind_controller import (
    BitcoindPlainController,
)
from cryptoadvance.specter.txlist import TxItem, TxList
from embit.descriptor.arguments import Key
from embit.descriptor.descriptor import Descriptor
from embit.transaction import Transaction, TransactionInput, TransactionOutput
from mock import MagicMock

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


def test_TxItem(empty_data_folder):
    # those two arrays could have been implemented as dict and need
    # same size
    assert len(TxItem.type_converter) == len(TxItem.columns)
    mytxitem = TxItem(
        None,
        [],
        empty_data_folder,
        hex=tx1_confirmed["hex"],
        blocktime=1642182445,  # arbitrary stuff can get passed
    )
    assert str(mytxitem) == "txid undefined"
    assert mytxitem.__repr__() == "TxItem(txid undefined)"
    # a TxItem pretty much works like a dict with some extrafunctionality
    assert mytxitem["blocktime"] == 1642182445
    # We can also add data after the fact
    mytxitem["confirmations"] = 123
    assert type(mytxitem.tx.vout) == list
    assert mytxitem["confirmations"] == 123


def test_txlist(empty_data_folder, bitcoin_regtest):
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
