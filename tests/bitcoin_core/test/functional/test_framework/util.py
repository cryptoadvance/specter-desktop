#!/usr/bin/env python3
# Copyright (c) 2014-2020 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Helpful routines for regression testing."""

"""
HEAVILY trimmed down to bare minimum for Specter test cases
* create_lots_of_big_transactions edited for Specter compatibility
"""


from binascii import unhexlify
from decimal import Decimal, ROUND_DOWN
from io import BytesIO


def assert_equal(thing1, thing2, *args):
    if thing1 != thing2 or any(thing1 != arg for arg in args):
        raise AssertionError(
            "not(%s)" % " == ".join(str(arg) for arg in (thing1, thing2) + args)
        )


def hex_str_to_bytes(hex_str):
    return unhexlify(hex_str.encode("ascii"))


def satoshi_round(amount):
    return Decimal(amount).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)


# Create large OP_RETURN txouts that can be appended to a transaction
# to make it large (helper for constructing large transactions).
def gen_return_txouts():
    # Some pre-processing to create a bunch of OP_RETURN txouts to insert into transactions we create
    # So we have big transactions (and therefore can't fit very many into each block)
    # create one script_pubkey
    script_pubkey = "6a4d0200"  # OP_RETURN OP_PUSH2 512 bytes
    for _ in range(512):
        script_pubkey = script_pubkey + "01"
    # concatenate 128 txouts of above script_pubkey which we'll insert before the txout for change
    txouts = []
    from .messages import CTxOut

    txout = CTxOut()
    txout.nValue = 0
    txout.scriptPubKey = hex_str_to_bytes(script_pubkey)
    for _ in range(128):
        txouts.append(txout)
    return txouts


# Create a spend of each passed-in utxo, splicing in "txouts" to each raw
# transaction to make it large.  See gen_return_txouts() above.
def create_lots_of_big_transactions(wallet, txouts, utxos, num, fee):
    node = wallet.rpc
    addr = node.getnewaddress()
    txids = []
    from .messages import CTransaction

    for _ in range(num):
        t = utxos.pop()
        inputs = [{"txid": t["txid"], "vout": t["vout"]}]
        outputs = {}
        change = t["amount"] - fee
        outputs[addr] = float(satoshi_round(change))
        rawtx = node.createrawtransaction(inputs, outputs)
        tx = CTransaction()
        tx.deserialize(BytesIO(hex_str_to_bytes(rawtx)))
        for txout in txouts:
            tx.vout.append(txout)
        newtx = tx.serialize().hex()
        psbtF = wallet.rpc.converttopsbt(newtx)
        psbtFF = wallet.rpc.walletprocesspsbt(psbtF)
        signed = wallet.devices[0].sign_psbt(psbtFF["psbt"], wallet)
        assert signed["complete"]
        finalized = wallet.rpc.finalizepsbt(signed["psbt"])
        txid = node.sendrawtransaction(finalized["hex"])
        txids.append(txid)
    return txids
