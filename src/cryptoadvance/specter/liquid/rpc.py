from ..rpc import RpcError, BitcoinRPC
from embit.liquid.descriptor import LDescriptor
from embit.liquid.pset import PSET
from embit.descriptor.checksum import add_checksum
from embit.liquid.addresses import addr_decode
import logging

logger = logging.getLogger(__name__)


class LiquidRPC(BitcoinRPC):
    """
    This class introduces fixes to Elements RPC that are broken in current Elements Core.
    It also adds custom fields that are normaly not present in the final blind pset, but
    that we find useful.

    In particular this class:
    - combines walletcreatefundedpsbt and blindpsbt calls into one call by default (walletcreatefundedpsbt)
    - TODO: adds support for assets in walletcreatefundedpsbt
    - TODO: adds custom fields to pset:
      - blinding pubkeys for HW recv addr verification
      - ecdh nonce for deterministic range proof
      - extra data that should be encoded in the change rangeproof
    """

    def getbalance(
        self,
        dummy="*",
        minconf=0,
        include_watchonly=True,
        avoid_reuse=False,
        assetlabel="bitcoin",  # pass None to get all
        **kwargs
    ):
        """
        Bitcoin-like getbalance rpc call without assets,
        set assetlabel=None to get balances for all assets
        """
        args = [dummy, minconf, include_watchonly, avoid_reuse]
        # if assetlabel is explicitly set to None - return all assets
        if assetlabel is not None:
            args.append(assetlabel)
        return super().__getattr__("getbalance")(*args, **kwargs)

    def _patch_descriptors(self, arr):
        # used by importmulti and importdescriptors
        descs = [LDescriptor.from_string(a["desc"].split("#")[0]) for a in arr]
        blinded = [d.is_blinded for d in descs]
        bkey = None
        if any(blinded) and not all(blinded):
            raise RpcError("All descriptors should be either blinded or not")
        if all(blinded):
            bkeys = {d.blinding_key.key.secret for d in descs}
            if len(bkeys) > 1:
                raise RpcError("All descriptors should use the same blinding key")
            bkey = bkeys.pop().hex()
            arr = [a.copy() for a in arr]
            for i, a in enumerate(arr):
                descs[i].blinding_key = None
                a["desc"] = add_checksum(str(descs[i]))
        return arr, bkey

    def importdescriptors(self, arr, *args, **kwargs):
        arr, bkey = self._patch_descriptors(arr)
        res = super().__getattr__("importdescriptors")(arr, *args, **kwargs)
        if bkey is not None:
            self.importmasterblindingkey(bkey, **kwargs)
        return res

    def importmulti(self, arr, *args, **kwargs):
        arr, bkey = self._patch_descriptors(arr)
        res = super().__getattr__("importmulti")(arr, *args, **kwargs)
        if bkey is not None:
            self.importmasterblindingkey(bkey, **kwargs)
        return res

    def getbalances(self, assetlabel="bitcoin", **kwargs):
        """
        Bitcoin-like getbalance rpc call without assets,
        set assetlabel=None to get balances for all assets
        """
        res = super().__getattr__("getbalances")(**kwargs)
        # if assetlabel is explicitly set to None - return as is
        if assetlabel is None:
            return res
        # otherwise get balances for a particular assetlabel
        for k in res:
            for kk in res[k]:
                v = res[k][kk].get(assetlabel, 0)
                res[k][kk] = v
        return res

    def decodepsbt(self, *args, **kwargs):
        res = super().__getattr__("decodepsbt")(*args, **kwargs)
        res["fee"] = res["fees"]["bitcoin"]
        return res

    def getreceivedbyaddress(self, address, minconf=1, assetlabel="bitcoin", **kwargs):
        args = [address, minconf]
        if assetlabel is not None:
            args.append(assetlabel)
        return super().__getattr__("getreceivedbyaddress")(*args, **kwargs)

    def walletcreatefundedpsbt(self, inputs, outputs, *args, blind=True, **kwargs):
        """
        Creates and blinds an Elements PSBT transaction.
        Arguments:
        1. inputs: [{txid, vout[, sequence, pegin stuff]}]
        2. outputs: [{address: amount, "asset": asset}, ...] # TODO: add assets support
        3. locktime = 0
        4. options {includeWatching, changeAddress, subtractFeeFromOutputs,
                    replaceable, add_inputs, feeRate, fee_rate}
        5. bip32 derivations
        6. solving data
        7. blind = True - Specter-LiquidRPC specific thing - blind transaction after creation
        """
        res = super().__getattr__("walletcreatefundedpsbt")(
            inputs, outputs, *args, **kwargs
        )
        psbt = res.get("psbt", None)
        # check if we should blind the transaction
        if psbt and blind:
            # check that change is also blinded - fixes a bug in pset branch
            tx = PSET.from_string(psbt)
            der = None
            changepos = res["changepos"]
            if len(args) >= 2:
                addr = args[1].get("changeAddress", None)
                if addr:
                    _, bpub = addr_decode(addr)
                    der = tx.outputs[changepos].bip32_derivations
                    if bpub and (tx.outputs[changepos].blinding_pubkey is None):
                        tx.outputs[changepos].blinding_pubkey = bpub.sec()
                    res["psbt"] = str(tx)
                    psbt = str(tx)
            # blindpsbt is used on master branch
            try:
                blinded = self.blindpsbt(psbt)
                logger.info("transaction blinded")
            except Exception as e:
                # in pset branch (achow/pset) walletprocesspsbt is used instead
                logger.warn(e)
                # blind without signing
                blinded = self.walletprocesspsbt(psbt, False)["psbt"]
            res["psbt"] = blinded
        return res

    def combinepsbt(self, psbts, *args, **kwargs):
        if len(psbts) == 0:
            raise RpcError("Provide at least one psbt")
        tx = PSET.from_string(psbts[0])
        for b64 in psbts[1:]:
            t2 = PSET.from_string(b64)
            tx.version = tx.version or t2.version
            tx.tx_version = tx.tx_version or t2.tx_version
            tx.locktime = tx.locktime or t2.locktime
            tx.xpubs.update(t2.xpubs)
            tx.unknown.update(t2.unknown)


            for i in range(len(tx.inputs)):
                inp1 = tx.inputs[i]
                inp2 = t2.inputs[i]
                inp1.value = inp1.value or inp2.value
                inp1.value_blinding_factor = inp1.value_blinding_factor or inp2.value_blinding_factor
                inp1.asset = inp1.asset or inp2.asset
                inp1.asset_blinding_factor = inp1.asset_blinding_factor or inp2.asset_blinding_factor
                inp1.txid = inp1.txid or inp2.txid
                inp1.vout = inp1.vout or inp2.vout
                inp1.sequence = inp1.sequence or inp2.sequence
                inp1.non_witness_utxo = inp1.non_witness_utxo or inp2.non_witness_utxo
                inp1.sighash_type = inp1.sighash_type or inp2.sighash_type
                inp1.redeem_script = inp1.redeem_script or inp2.redeem_script
                inp1.witness_script = inp1.witness_script or inp2.witness_script
                inp1.final_scriptsig = inp1.final_scriptsig or inp2.final_scriptsig
                inp1.final_scriptwitness = inp1.final_scriptwitness or inp2.final_scriptwitness
                inp1.partial_sigs.update(inp2.partial_sigs)
                inp1.bip32_derivations.update(inp2.bip32_derivations)
                inp1.unknown.update(inp2.unknown)

            for i in range(len(tx.outputs)):
                out1 = tx.outputs[i]
                out2 = t2.outputs[i]
                out1.value_commitment = out1.value_commitment or out2.value_commitment
                out1.value_blinding_factor = out1.value_blinding_factor or out2.value_blinding_factor
                out1.asset_commitment = out1.asset_commitment or out2.asset_commitment
                out1.asset_blinding_factor = out1.asset_blinding_factor or out2.asset_blinding_factor
                out1.range_proof = out1.range_proof or out2.range_proof
                out1.surjection_proof = out1.surjection_proof or out2.surjection_proof
                out1.ecdh_pubkey = out1.ecdh_pubkey or out2.ecdh_pubkey
                out1.blinding_pubkey = out1.blinding_pubkey or out2.blinding_pubkey
                out1.asset = out1.asset or out2.asset

                out1.value = out1.value or out2.value
                out1.script_pubkey = out1.script_pubkey or out2.script_pubkey
                out1.unknown = out1.unknown or out2.unknown
                out1.redeem_script = out1.redeem_script or out2.redeem_script
                out1.witness_script = out1.witness_script or out2.witness_script
                out1.bip32_derivations.update(out2.bip32_derivations)
                out1.unknown.update(out2.unknown)
        return str(tx)

    def decodepsbt(self, b64psbt, *args, **kwargs):
        decoded = super().__getattr__("decodepsbt")(b64psbt, *args, **kwargs)
        # pset branch - no fee and global tx fields...
        if "tx" not in decoded or "fee" not in decoded:
            pset = PSET.from_string(b64psbt)
            if "tx" not in decoded:
                decoded["tx"] = self.decoderawtransaction(str(pset.tx))
            if "fee" not in decoded:
                decoded["fee"] = pset.fee() * 1e-8
        for out in decoded["outputs"]:
            if "value" not in out:
                out["value"] = -1
        for out in decoded["tx"]["vout"]:
            if "value" not in out:
                out["value"] = -1
        return decoded

    def decoderawtransaction(self, tx):
        unblinded = self.unblindrawtransaction(tx)["hex"]
        return super().__getattr__("decoderawtransaction")(unblinded)

    @classmethod
    def from_bitcoin_rpc(cls, rpc):
        """Convert BitcoinRPC to LiquidRPC"""
        return cls(
            user=rpc.user,
            password=rpc.password,
            host=rpc.host,
            port=rpc.port,
            protocol=rpc.protocol,
            path=rpc.path,
            timeout=rpc.timeout,
            session=rpc.session,
            proxy_url=rpc.proxy_url,
            only_tor=rpc.only_tor,
        )
