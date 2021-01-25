"""
Manages the list of addresses for the wallet, including labels and derivation paths
"""
import os
from .persistence import write_csv, read_csv
from embit.transaction import Transaction
from embit.networks import NETWORKS
import json
import logging
from .util.tx import decoderawtransaction

logger = logging.getLogger(__name__)


def parse_arr(v):
    if not isinstance(v, str):
        return v
    try:
        return json.loads(v.replace("'", '"'))
    except:
        return v


class TxItem(dict):
    columns = [
        "txid",  # str, txid in hex
        "hex",  # str, raw tx in hex
        "blockhash",  # str, blockhash, None if not confirmed
        "blockheight",  # int, blockheight, None if not confirmed
        "time",  # int (timestamp in seconds), time received
        "bip125-replaceable",  # str ("yes" / "no"), whatever RBF is enabled for the transaction
        "conflicts",  # rbf conflicts, list of txids
        "vsize",
        "category",
        "address",
        "amount",
        "ismine",
    ]
    type_converter = [
        str,
        str,
        str,
        int,
        int,
        str,
        parse_arr,
        int,
        str,
        parse_arr,
        parse_arr,
        bool,
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

    def __dict__(self):
        return {
            "txid": self["txid"],
            "blockhash": self["blockhash"],
            "blockheight": self["blockheight"],
            "time": self["time"],
            "conflicts": self["conflicts"],
            "bip125-replaceable": self["bip125-replaceable"],
            "hex": self["hex"],
            "vsize": self["vsize"],
            "category": self["category"],
            "address": self["address"],
            "amount": self["amount"],
            "ismine": self["ismine"],
        }


class TxList(dict):
    def __init__(self, path, rpc, addresses, chain):
        self.chain = chain
        self.path = path
        self.rpc = rpc
        self._addresses = addresses
        txs = []
        file_exists = False
        try:
            if os.path.isfile(self.path):
                txs = read_csv(self.path, TxItem, self.rpc, self._addresses)
                for tx in txs:
                    self[tx.txid] = tx
                file_exists = True
        except Exception as e:
            logger.error(e)
        self._file_exists = file_exists

    def save(self):
        if len(list(self.keys())) > 0:
            write_csv(self.path, list(self.values()), TxItem)
        self._file_exists = True

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
        return {"hex": tx["hex"], "time": tx["time"]}

    def add(self, txs):
        """
        adds transactions to the list without any rpc calls.
        assuming tx is already watched by the wallet.
        Transactions should be a dict with dicts with fields:
        "<txid>": {
            "txid", - hex txid
            "hex",  - hex raw transaction
            "blockheight", - int blockheight if confirmed, None otherwise
            "blockhash", - str blockhash if confirmed, None otherwise
            "time", - int unix timestamp in seconds when tx was received
            "conflicts", - list of txids spending the same inputs (rbf)
            "bip125-replaceable", - str ("yes" or "no") - is rbf enabled for this tx
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
                "blockhash": tx.get("blockhash", None),
                "time": time,
                "conflicts": tx.get("walletconflicts", []),
                "bip125-replaceable": tx.get("bip125-replaceable", "no"),
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
        for tx in [self[tx] for tx in self if tx in txs]:
            raw_tx = decoderawtransaction(tx["hex"], self.chain)
            tx["vsize"] = raw_tx["vsize"]

            category = ""
            addresses = []
            amounts = {}
            inputs_mine_count = 0
            for vin in raw_tx["vin"]:
                # coinbase tx
                if (
                    vin["txid"]
                    == "0000000000000000000000000000000000000000000000000000000000000000"
                ):
                    category = "generate"
                    break
                if vin["txid"] in self:
                    try:
                        address = decoderawtransaction(
                            self[vin["txid"]]["hex"],
                            self.chain,
                        )["vout"][vin["vout"]]["addresses"][0]
                        address_info = self._addresses.get(address, None)
                        if address_info and not address_info.is_external:
                            inputs_mine_count += 1
                    except Exception:
                        continue

            outputs_mine_count = 0
            for out in raw_tx["vout"]:
                try:
                    address = out["addresses"][0]
                except Exception:
                    # couldn't get address...
                    continue
                address_info = self._addresses.get(address, None)
                if address_info and not address_info.is_external:
                    outputs_mine_count += 1
                addresses.append(address)
                amounts[address] = out["value"]

            if inputs_mine_count:
                if outputs_mine_count == len(raw_tx["vout"]):
                    category = "selftransfer"
                    # remove change addresses from the dest list
                    addresses2 = [
                        address
                        for address in addresses
                        if self._addresses.get(address, None)
                        and not self._addresses[address].change
                    ]
                    # use new list only if it's not empty
                    if len(addresses2) > 0:
                        addresses = addresses2
                else:
                    category = "send"
                    addresses = [
                        address
                        for address in addresses
                        if not self._addresses.get(address, None)
                        or self._addresses[address].is_external
                    ]
            else:
                if not category:
                    category = "receive"
                addresses = [
                    address
                    for address in addresses
                    if self._addresses.get(address, None)
                    and not self._addresses[address].is_external
                ]

            amounts = [amounts[address] for address in addresses]

            if len(addresses) == 1:
                addresses = addresses[0]
                amounts = amounts[0]

            tx["category"] = category
            tx["address"] = addresses
            tx["amount"] = amounts
            if len(addresses) == 0:
                tx["ismine"] = False
            else:
                tx["ismine"] = True
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
        return self._file_exists and os.path.isfile(self.path)
