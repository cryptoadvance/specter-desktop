"""
Manages the list of addresses for the wallet, including labels and derivation paths
"""
import os
from .persistence import write_csv, read_csv
from embit.transaction import Transaction
from embit.networks import NETWORKS
import json


class TxItem(dict):
    columns = [
        "txid",  # str, txid in hex
        "hex",  # str, raw tx in hex
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

    def __init__(self, rpc, addresses, **kwargs):
        self.rpc = rpc
        self._addresses = addresses
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
    def __init__(self, path, rpc, addresses, chain):
        self.chain = chain
        self.path = path
        self.rpc = rpc
        self._addresses = addresses
        txs = []
        if os.path.isfile(self.path):
            txs = read_csv(self.path, TxItem, self.rpc, self._addresses)
        for tx in txs:
            self[tx.txid] = tx

    def save(self):
        if len(list(self.keys())) > 0:
            write_csv(self.path, list(self.values()), TxItem)

    def gettransaction(self, txid, blockheight=None):
        """
        Will ask Bitcoin Core for a transaction if blockheight is None or txid not known
        Provide blockheight or 0 if you don't care about confirmations number
        to avoid RPC calls
        """
        if blockheight is None or txid not in self:
            tx = self.rpc.gettransaction(txid)
            # save if we don't know about this tx
            if txid not in self:
                self.add({txid: tx})
            if "time" not in tx:
                tx["time"] = tx["timereceived"]
            return tx
        tx = self[txid]
        return {
            "hex": tx["hex"],
            "time": tx["time"],
        }

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
        addresses = []
        for txid in txs:
            tx = txs[txid]
            # find minimal from 3 times:
            maxtime = 10445238000  # TODO: change after 31 dec 2300 lol
            time = min(
                tx.get("blocktime", maxtime),
                tx.get("timereceived", maxtime),
                tx.get("time", maxtime),
            )
            obj = {
                "txid": txid,
                "blockheight": tx.get("blockheight", None),
                "time": time,
                "conflicts": tx.get("walletconflicts", []),
                "hex": tx.get("hex", None),
            }
            txitem = TxItem(self.rpc, self._addresses, **obj)
            self[txid] = txitem
            if txitem.tx:
                for vout in txitem.tx.vout:
                    try:
                        addr = vout.script_pubkey.address(NETWORKS[self.chain])
                        addresses.append(addr)
                    except:
                        pass  # maybe not an address, but a raw script?
        self._addresses.set_used(addresses)
        self.save()

    def load(self, arr):
        """
        Load transactions to Core with merkle proofs to avoid rescan
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
