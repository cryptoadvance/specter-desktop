"""
Manages the list of transactions for the wallet
"""
from typing import Union
import os
from .specter_error import SpecterError
from .persistence import delete_file, write_csv, read_csv
from .helpers import get_address_from_dict
from embit.transaction import Transaction
from embit.liquid.networks import get_network
from embit import bip32
import json
import math
import logging
from .util.tx import decoderawtransaction
from .util.psbt import SpecterTx, AbstractTxContext, SpecterPSBT

logger = logging.getLogger(__name__)


def parse_arr(v):
    if not isinstance(v, str):
        return v
    try:
        return json.loads(v.replace("'", '"'))
    except:
        return v


class AbstractTxListContext(AbstractTxContext):
    @property
    def rpc(self):
        if hasattr(self, "parent"):
            return self.parent.rpc
        raise NotImplementedError("Implement this!")

    @property
    def chain(self) -> str:
        if hasattr(self, "parent"):
            return self.parent.chain
        raise NotImplementedError("Implement this!")


class TxItem(dict, AbstractTxListContext):
    TransactionCls = Transaction
    columns = [
        "txid",  # str, txid in hex
        "blockhash",  # str, blockhash, None if not confirmed
        "blockheight",  # int, blockheight, None if not confirmed
        "time",  # int (timestamp in seconds), time received
        "blocktime",  # int (timestamp in seconds), time the block was mined
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
        int,
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

    def __init__(self, parent, addresses, rawdir, **kwargs):
        self.parent = parent
        self._addresses = addresses
        self.rawdir = rawdir
        # copy
        kwargs = dict(**kwargs)
        # replace with None or convert
        for i, k in enumerate(self.columns):
            v = kwargs.get(k, "")
            kwargs[k] = None if v in ["", None] else self.type_converter[i](v)

        super().__init__(**kwargs)
        self._tx = None
        # if we have hex data
        if "hex" in kwargs:
            self._tx = self.TransactionCls.from_string(kwargs["hex"])
        # conflicts were renamed to walletconflicts
        if "walletconflicts" in kwargs:
            self["conflicts"] = kwargs["walletconflicts"]

    @property
    def fname(self):
        return os.path.join(self.rawdir, self.txid + ".bin")

    @property
    def tx(self):
        if not self._tx:
            # Get transaction from file if we don't have it cached.
            # We cache transactions to self._tx
            # only when new tx is added before dump() is called
            try:
                if os.path.isfile(self.fname):
                    with open(self.fname, "rb") as f:
                        tx = self.TransactionCls.read_from(f)
                        self._tx = tx
                        return tx
            except Exception as e:
                logger.error(e)
        # if we failed to load tx from file - load it from RPC
        if not self._tx:
            # get transaction from rpc
            try:
                res = self.rpc.gettransaction(self.txid)
                tx = self.TransactionCls.from_string(res["hex"])
                self._tx = tx
                return tx
            except Exception as e:
                logger.error(e)
        return self._tx

    @property
    def vsize(self):
        if self.get("vsize"):
            return self["vsize"]
        tx = self.tx
        txsize = len(tx.serialize())
        if tx.is_segwit:
            # tx size - flag - marker - witness
            non_witness_size = (
                txsize - 2 - sum([len(inp.witness.serialize()) for inp in tx.vin])
            )
            witness_size = txsize - non_witness_size
            weight = non_witness_size * 4 + witness_size
            vsize = math.ceil(weight / 4)
        else:
            vsize = txsize
            weight = txsize * 4
        return vsize

    def dump(self):
        """Dumps transaction in binary to the folder if it's not there"""
        # nothing to do if file exists or we don't have binary tx
        if os.path.isfile(self.fname) or not self._tx:
            return
        # Try to create a directory if it's not there
        # and write raw tx to file
        # Can fail if multiple threads create the same dir
        try:
            # create dir if it doesn't exist
            if not os.path.isdir(self.rawdir):
                os.mkdir(self.rawdir)
        except Exception as e:
            logger.error(e)
        try:
            with open(self.fname, "wb") as f:
                self.tx.write_to(f)
        except Exception as e:
            logger.error(e)
        # clear cached tx as we saved the transaction to file
        self._tx = None

    @property
    def txid(self):
        return self["txid"]

    @property
    def hex(self):
        return str(self.tx)

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
            "blocktime": self["blocktime"],
            "conflicts": self["conflicts"],
            "bip125-replaceable": self["bip125-replaceable"],
            "vsize": self["vsize"],
            "category": self["category"],
            "address": self["address"],
            "amount": self["amount"],
            "ismine": self["ismine"],
        }


class TxList(dict, AbstractTxListContext):
    ItemCls = TxItem  # for inheritance
    PSBTCls = SpecterPSBT

    def __init__(self, path, parent, addresses):
        self.parent = parent
        self.path = path
        # folder to store transactions in binary form
        self.rawdir = path.replace(".csv", "_raw")
        self._addresses = addresses
        txs = []
        file_exists = False
        try:
            if os.path.isfile(self.path):
                txs = read_csv(
                    self.path,
                    self.ItemCls,
                    self,
                    self._addresses,
                    self.rawdir,
                )
                for tx in txs:
                    self[tx.txid] = tx
                file_exists = True
        except Exception as e:
            logger.error(e)
        self._file_exists = file_exists

    def _save(self):
        # check if we have at least one transaction
        if self:
            # Dump all transactions to binary files
            # This happens only if they have not been dumped before
            for tx in self.values():
                tx.dump()
            write_csv(self.path, list(self.values()), self.ItemCls)
            self._file_exists = True
        else:
            delete_file(self.path)
            self._file_exists = False

    def getfetch(self, txid):
        """
        Returns TxItem instance if it is known,
        otherwise tries to get it from rpc, adds to self and returns TxItem
        """
        if txid not in self:
            tx = self.rpc.gettransaction(txid)
            if "time" not in tx:
                tx["time"] = tx["timereceived"]
            self.add({txid: tx})
        return self[txid]

    def gettransaction(self, txid, blockheight=None, decode=False, full=True):
        """
        Will ask Bitcoin Core for a transaction if blockheight is None or txid not known
        Provide blockheight or 0 if you don't care about confirmations number
        to avoid RPC calls.
        full=True will add a "hex" key
        decode=True will decode transaction similar to Core's decoderawtransaction
        """
        # if we don't know blockheigth or transaction
        # we invalidate which results in asking core
        if txid in self and self[txid]["blockheight"] == None:
            self.invalidate(txid)

        if blockheight is None or txid not in self:
            tx = self.rpc.gettransaction(txid)
            if "time" not in tx:
                tx["time"] = tx["timereceived"]
            # save if we don't know about this tx
            if txid not in self:
                self.add({txid: tx})
        # lookup tx in cache, it should be there already
        tx = self[txid]
        res = dict(**tx)
        if full:
            res["hex"] = tx.hex
        if decode:
            res.update(self._decoderawtransaction(tx.hex))
        return res

    def invalidate(self, txid):
        """removes a tx from the list"""
        if txid not in self:
            raise SpecterError(f"TX with txid {txid} does not exit in {self}")
        del self[txid]
        self._save()

    def _decoderawtransaction(self, tx: Union[Transaction, str, bytes]):
        return SpecterTx(self, tx).to_dict()

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
            "blocktime",  - int unix timestamp in seconds  the block was mined
            "conflicts", - list of txids spending the same inputs (rbf)
            "bip125-replaceable", - str ("yes" or "no") - is rbf enabled for this tx
        }
        """
        # here we store all addresses in transactions
        # to set them used later
        addresses = []
        # first we add all transactions to cache
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
                "blocktime": tx.get("blocktime", None),
                "conflicts": tx.get("walletconflicts", []),
                "bip125-replaceable": tx.get("bip125-replaceable", "no"),
                "hex": tx.get("hex", None),
            }
            txitem = self.ItemCls(self, self._addresses, self.rawdir, **obj)
            self[txid] = txitem
            if txitem.tx:
                for vout in txitem.tx.vout:
                    try:
                        addr = vout.script_pubkey.address(get_network(self.chain))
                        if addr not in addresses:
                            addresses.append(addr)
                    except:
                        pass  # maybe not an address, but a raw script?
        self._addresses.set_used(addresses)
        # detect category, amounts and addresses
        for tx in [self[txid] for txid in self if txid in txs]:
            self._fill_missing(tx)
        self._save()

    def _update_destinations(self, tx, outs):
        addresses = [out.get("address", "Unknown") for out in outs]
        amounts = [out["float_amount"] for out in outs]
        if len(addresses) == 1:
            addresses = addresses[0]
            amounts = amounts[0]
        tx["address"] = addresses
        tx["amount"] = amounts

    def _get_psbt(self, raw_tx):
        psbt = self.PSBTCls.from_transaction(raw_tx, self.descriptor, self.network)
        # fill derivation paths etc
        updated = self.rpc.walletprocesspsbt(str(psbt), False).get("psbt", None)
        if updated:
            psbt.update(updated)
        return psbt

    def _fill_missing(self, tx):
        """This seem to calculate the category of the tx which is one of:
        mixed (default), generate, selftransfer, receive or send

        Also the tx gets a key with a boolean to figure out whether its "mine"
        """
        raw_tx = tx.tx
        psbt = self._get_psbt(raw_tx)
        # detect category
        category = "mixed"

        # calculate everything once
        inputs = [inp.to_dict() for inp in psbt.inputs]
        outputs = [out.to_dict() for out in psbt.outputs]
        all_inputs_mine = all([inp["is_mine"] for inp in inputs])
        all_outputs_mine = all([out["is_mine"] for out in outputs])
        all_inputs_external = not any([inp["is_mine"] for inp in inputs])

        if b"\x00" * 32 in [vin.txid for vin in raw_tx.vin]:
            category = "generate"
        elif all_inputs_mine and all_outputs_mine:
            category = "selftransfer"
        elif all_inputs_external:
            category = "receive"
        elif all_inputs_mine:
            category = "send"

        all_outs = [out for out in outputs]
        my_outs = [out for out in all_outs if out["is_mine"]]
        my_receiving = [out for out in my_outs if not out["change"]]
        external = [out for out in all_outs if out not in my_outs]
        # decide what addresses to show
        if category in ["generate", "receive", "selftransfer"]:
            # either receiving only (if not empty), or only mine (if not empty), or all
            outs = my_receiving or my_outs or all_outs
        elif category in ["send"]:
            # keep only external addresses if they are present
            outs = external or all_outs
        else:
            # not sure what's the best here
            outs = my_receiving or my_outs or external or all_outs

        self._update_destinations(tx, outs)
        tx["category"] = category
        # at least one input or output is ours - tx is ours
        tx["ismine"] = any(scope["is_mine"] for scope in (inputs + outputs))

    def load(self, arr):
        """
        TODO: load transactions from backup
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
            <txid>: {"success": False, "error": "reason"}, if failed to import transaction
        }
        """
        # TODO: how to handle unconfirmed?
        # try to get raw transactions and tx details if not present
        # self.save()
        return [{"success": False, "error": "not implemented"} for a in arr]

    @property
    def file_exists(self):
        return self._file_exists and os.path.isfile(self.path)
