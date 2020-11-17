"""
Manages the list of addresses for the wallet, including labels and derivation paths
"""
import os
from .persistence import write_csv, read_csv
from embit.transaction import Transaction
import json


class TxItem(dict):
    columns = [
        "txid",  # str, txid in hex
        "hex",  # str, raw tx in hex
        # add merkle proof? it's kinda large
        "blockheight",  # int, blockheight, None if not confirmed
        "time",  # int (timestamp in seconds), time received
        "conflicts",  # rbf conflicts, list of txids
    ]
    type_converter = [
        str,
        str,
        int,
        int,
        lambda v: json.loads(v) if isinstance(v, str) else v,
    ]

    def __init__(self, rpc, **kwargs):
        self.rpc = rpc
        # copy
        kwargs = dict(**kwargs)
        # replace with None or convert
        for i, k in enumerate(self.columns):
            v = kwargs.get(k, "")
            kwargs[k] = None if v in ["", None] else self.type_converter[i](v)

        super().__init__(**kwargs)
        # parse transaction
        self.tx = (
            None if not self["hex"] else Transaction.parse(bytes.fromhex(self["hex"]))
        )

    @property
    def txid(self):
        return self["txid"]

    @property
    def hex(self):
        return self["hex"]

    def __str__(self):
        return self.txid

    def __repr__(self):
        return f"TxItem({str(self)})"


class TxList(dict):
    def __init__(self, path, rpc):
        self.path = path
        self.rpc = rpc
        txs = []
        if os.path.isfile(self.path):
            txs = read_csv(self.path, TxItem, self.rpc)
        for tx in txs:
            self[tx.txid] = tx

    def save(self):
        if len(list(self.keys())) > 0:
            write_csv(self.path, list(self.values()), TxItem)

    def add(self, txs):
        """
        adds transactions to the list without any rpc calls.
        assuming tx is already watched by the wallet.
        Transactions should be a dict with dicts with fields:
        "<txid>": {
            "txid", - hex txid
            "hex",  - hex raw transaction
            "blockheight", - int blockheight if confirmed, None otherwise
            "time", - int unix timestamp in seconds when tx was received
            "conflicts", - list of txids spending the same inputs (rbf)
        }
        """
        for txid in txs:
            self[txid] = TxItem(self.rpc, **txs[txid])
        self.save()

    def load(self, arr):
        """
        arr should be a dict with dicts:
        "<txid>": { 
            "txid",         - hex txid
            "hex",          - optional, raw hex transactions
            "merkle_proof", - optional, hex merkle proof
            "blockheight",  - optional, block height
            "blockhash",    - optional, block hash
            "time",         - optional, time received
        }
        If optional fields are not found we will try to get them from rpc calls.
        If we fail - transaction will not be added.
        Retuns an dict of dicts:
        {
            <txid>: {"success": True}, on success,
            <txid>: {"error": "reason"}, if failed to import transaction
        }
        """
        # TODO: how to handle unconfirmed?
        # try to get raw transactions and tx details if not present
        # self.save()
        return [{"error": "not implemented"} for a in arr]

    @property
    def file_exists(self):
        return os.path.isfile(self.path)
