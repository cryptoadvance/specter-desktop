from ..txlist import *
from embit.liquid.transaction import LTransaction, TxOutWitness, unblind
from embit.liquid.pset import PSET
from embit.liquid import slip77
from embit.hashes import tagged_hash
from embit.ec import PrivateKey
from .util.pset import SpecterLTx, get_value, get_asset, SpecterPSET
from io import BytesIO
from embit.psbt import read_string


class LTxItem(WalletAwareTxItem):
    TransactionCls = LTransaction
    columns = [
        "txid",  # str, txid in hex
        "blockhash",  # str, blockhash, None if not confirmed
        "blockheight",  # int, blockheight, None if not confirmed
        "time",  # int (timestamp in seconds), time received
        "bip125-replaceable",  # str ("yes" / "no"), whatever RBF is enabled for the transaction
        "conflicts",  # rbf conflicts, list of txids
        "vsize",
        "category",
        "address",
        "amount",
        "asset",
        "ismine",
    ]
    type_converter = [
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
        parse_arr,
        bool,
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # unblind what's blinded and remove
        # will fill automatically
        self.vsize
        self._unblind()

    def _unblind(self):
        if not self.descriptor.is_blinded:
            return

        b = self.tx

        mbpk = self.descriptor.blinding_key.key
        net = self.network

        values = [0 for out in b.vout]
        assets = [b"\xFF" * 32 for out in b.vout]
        datas = []
        # search for datas encoded in rangeproofs
        for i, out in enumerate(b.vout):
            # unblinded
            if isinstance(out.value, int):
                values[i] = out.value
                assets[i] = out.asset
                continue

            pk = slip77.blinding_key(mbpk, out.script_pubkey)
            try:
                res = out.unblind(pk.secret, message_length=1000)
                value, asset, vbf, abf, extra, *_ = res
                if len(extra.rstrip(b"\x00")) > 0:
                    datas.append(extra)
                values[i] = value
                assets[i] = asset
            except RuntimeError as e:
                if str(e).startswith("Failed to rewind the proof"):
                    logger.warn(f"this can probably be ignored: {e}")
                else:
                    raise e

        # to calculate blinding seed
        tx = PSET(b)
        seed = tagged_hash("liquid/blinding_seed", mbpk.secret)
        txseed = tx.txseed(seed)
        pubkeys = {}

        for extra in datas:
            s = BytesIO(extra)
            while True:
                k = read_string(s)
                if len(k) == 0:
                    break
                v = read_string(s)
                if k[0] == 1 and len(k) == 5:
                    idx = int.from_bytes(k[1:], "little")
                    pubkeys[idx] = v
                elif k == b"\x01\x00":
                    txseed = v

        for i, out in enumerate(b.vout):
            if out.witness.range_proof.is_empty:
                continue
            if i in pubkeys and len(pubkeys[i]) in [33, 65]:
                nonce = tagged_hash(
                    "liquid/range_proof", txseed + i.to_bytes(4, "little")
                )
                if out.ecdh_pubkey == PrivateKey(nonce).sec():
                    try:
                        res = unblind(
                            pubkeys[i],
                            nonce,
                            out.witness.range_proof.data,
                            out.value,
                            out.asset,
                            out.script_pubkey,
                        )
                        value, asset, vbf, abf, extra, min_value, max_value = res
                        assets[i] = asset
                        values[i] = value
                    except Exception as e:
                        logger.exception(f"Failed at unblinding output {i}: {e}", e)
                else:
                    logger.warn(f"Failed at unblinding: {e}")

        for i, out in enumerate(b.vout):
            out.asset = assets[i]
            out.value = values[i]
            out.witness = TxOutWitness()

    @property
    def vsize(self):
        if self.get("vsize"):
            return self["vsize"]
        tx = self.tx
        txsize = len(tx.serialize())
        # tx size - flag - marker - witness
        non_witness_size = (
            txsize
            - 2
            - sum([len(inp.witness.serialize()) for inp in tx.vin])
            - sum([len(out.witness.serialize()) for out in tx.vout])
        )
        witness_size = txsize - non_witness_size
        weight = non_witness_size * 4 + witness_size
        vsize = math.ceil(weight / 4)
        return vsize

    # Three properties which are defined in WalletAwareTxItem which we can't calculate here but which need to
    # return something as the getter is called in WalletAwareTxItem`#s constructor
    # This is definitely not a good way to fix this.
    # ToDo: Do it properly if we have more time for Liquid

    @property
    def category(self):
        return None

    @property
    def address(self):
        return None

    @property
    def flow_amount(self):
        return None

    @property
    def ismine(self):
        return None

    def __dict__(self):
        return {
            "txid": self["txid"],
            "blockhash": self["blockhash"],
            "blockheight": self["blockheight"],
            "time": self["time"],
            "conflicts": self["conflicts"],
            "bip125-replaceable": self["bip125-replaceable"],
            "vsize": self["vsize"],
            "category": self["category"],
            "address": self["address"],
            "amount": self["amount"],
            "asset": self["asset"],
            "ismine": self["ismine"],
        }


class LTxList(TxList):
    ItemCls = LTxItem
    PSBTCls = SpecterPSET
    counter = 0

    def _get_psbt(self, raw_tx):
        psbt = self.PSBTCls.from_transaction(raw_tx, self.descriptor, self.network)
        psbt.psbt.version = 2
        # fill derivation paths etc
        updated = self.rpc.walletprocesspsbt(str(psbt), False).get("psbt", None)
        if updated:
            psbt.update(updated)
        return psbt

    def _update_destinations(self, tx, outs):
        # remove dummy and fee
        outs = [out for out in outs if out.get("address") not in ["Fee", "DUMMY"]]
        # process the rest
        addresses = [out.get("address", "Unknown") for out in outs]
        amounts = [out.get("float_amount", 0) for out in outs]
        assets = [out.get("asset", "ff" * 32) for out in outs]
        if len(addresses) == 1:
            addresses = addresses[0]
            amounts = amounts[0]
            assets = assets[0]
        tx["address"] = addresses
        tx["amount"] = amounts
        tx["asset"] = assets

    def decoderawtransaction(self, tx: Union[LTransaction, str, bytes]):
        return SpecterLTx(self, tx).to_dict()
