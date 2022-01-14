import copy
import logging
from io import BytesIO

from embit.descriptor.checksum import add_checksum
from embit.ec import PrivateKey, PublicKey
from embit.hashes import tagged_hash
from embit.liquid import finalizer, slip77
from embit.liquid.addresses import addr_decode
from embit.liquid.addresses import address as liquid_address
from embit.liquid.descriptor import LDescriptor
from embit.liquid.networks import get_network
from embit.liquid.pset import PSET, PSBTError
from embit.liquid.transaction import LTransaction, unblind
from embit.psbt import read_string

from ..rpc import BitcoinRPC, RpcError
from .util.pset import to_canonical_pset

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

    _master_blinding_key = None
    _asset_labels = None

    @property
    def asset_labels(self):
        if self._asset_labels is None:
            self._asset_labels = super().__getattr__("dumpassetlabels")()
        return self._asset_labels

    @property
    def master_blinding_key(self):
        if self._master_blinding_key is None:
            self._master_blinding_key = PrivateKey(
                bytes.fromhex(self.dumpmasterblindingkey())
            )
        return self._master_blinding_key

    def dumpassetlabels(self, *args, **kwargs):
        # inject cache
        res = super().__getattr__("dumpassetlabels")()
        self._asset_labels = res
        return res

    def importmasterblindingkey(self, *args, **kwargs):
        # clear cache
        self._master_blinding_key = None
        return super().__getattr__("importmasterblindingkey")(*args, **kwargs)

    def _patch_assetlabels(self, obj):
        # check if assets are labeled and replace with real assetsids
        if isinstance(obj, dict):
            for asset in list(obj.keys()):
                if asset in self.asset_labels and asset != "bitcoin":
                    assetid = self.asset_labels[asset]
                    obj[assetid] = obj[asset]
                    del obj[asset]

    def getbalance(
        self,
        dummy="*",
        minconf=0,
        include_watchonly=True,
        avoid_reuse=False,
        assetlabel="bitcoin",  # pass None to get all
        **kwargs,
    ):
        """
        Bitcoin-like getbalance rpc call without assets,
        set assetlabel=None to get balances for all assets
        """
        args = [dummy, minconf, include_watchonly, avoid_reuse]
        # if assetlabel is explicitly set to None - return all assets
        if assetlabel is not None:
            args.append(assetlabel)
        res = super().__getattr__("getbalance")(*args, **kwargs)
        self._patch_assetlabels(res)
        return res

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
            for k in res:
                for kk in res[k]:
                    self._patch_assetlabels(res[k][kk])
            return res
        # otherwise get balances for a particular assetlabel
        for k in res:
            for kk in res[k]:
                v = res[k][kk].get(assetlabel, 0)
                res[k][kk] = v
        return res

    def getreceivedbyaddress(self, address, minconf=1, assetlabel="bitcoin", **kwargs):
        args = [address, minconf]
        if assetlabel is not None:
            args.append(assetlabel)
        return super().__getattr__("getreceivedbyaddress")(*args, **kwargs)

    def walletcreatefundedpsbt(
        self, inputs, outputs, locktime=0, options={}, *args, blind=True, **kwargs
    ):
        """
        Creates and blinds an Elements PSBT transaction.
        Arguments:
        1. inputs: [{txid, vout[, sequence, pegin stuff]}]
        2. outputs: [{address: amount, "asset": asset}, ...] # TODO: add assets support
        3. locktime = 0
        4. options {includeWatching, changeAddress, subtractFeeFromOutputs,
                    replaceable, add_inputs, feeRate, fee_rate, changeAddresses}
        5. bip32 derivations
        6. solving data
        7. blind = True - Specter-LiquidRPC specific thing - blind transaction after creation
        """
        options = copy.deepcopy(options)
        change_addresses = (
            options.pop("changeAddresses") if "changeAddresses" in options else None
        )
        destinations = []
        for o in outputs:
            for k in o:
                if k != "asset":
                    destinations.append(addr_decode(k)[0])
        res = super().__getattr__("walletcreatefundedpsbt")(
            inputs, outputs, locktime, options, *args, **kwargs
        )
        psbt = res.get("psbt", None)

        # remove zero-output (bug in Elements)
        # TODO: remove after release
        if psbt:
            try:
                tx = PSET.from_string(psbt)
                # check if there are zero outputs
                has_zero = len([out for out in tx.outputs if out.value == 0]) > 0
                has_blinded = any([out.blinding_pubkey for out in tx.outputs])
                logger.error(has_zer, has_blinded)
                if has_blinded and has_zero:
                    tx.outputs = [out for out in tx.outputs if out.value > 0]
                    psbt = str(tx)
                    res["psbt"] = psbt
            except:
                pass

        # replace change addresses from the transactions if we can
        if change_addresses and psbt:
            try:
                tx = PSET.from_string(psbt)
                cur = 0
                for out in tx.outputs:
                    # fee
                    if out.script_pubkey.data == b"":
                        continue
                    # not change for sure
                    if not out.bip32_derivations:
                        continue
                    # do change replacement
                    if out.script_pubkey not in destinations:
                        sc, bkey = addr_decode(change_addresses[cur])
                        cur += 1
                        out.script_pubkey = sc
                        out.blinding_pubkey = bkey.sec() if bkey else None
                        out.bip32_derivations = {}
                        out.redeem_script = None
                        out.witness_script = None
                # fill derivation info
                patched = (
                    super().__getattr__("walletprocesspsbt")(str(tx), False).get("psbt")
                )
                patchedtx = PSET.from_string(patched)
                assert len(tx.outputs) == len(patchedtx.outputs)
                for out1, out2 in zip(tx.outputs, patchedtx.outputs):
                    # fee
                    if out1.script_pubkey.data == b"":
                        continue
                    # not change for sure
                    if not out2.bip32_derivations:
                        continue
                    # do change replacement
                    if out1.script_pubkey not in destinations:
                        out1.bip32_derivations = out2.bip32_derivations
                        out1.redeem_script = out2.redeem_script
                        out1.witness_script = out2.witness_script

                res["psbt"] = str(tx)
            except Exception as e:
                logger.error(e)
                raise e

        psbt = res.get("psbt", None)
        # check if we should blind the transaction
        if psbt and blind:
            # check that change is also blinded - fixes a bug in pset branch
            tx = PSET.from_string(psbt)
            changepos = res.get("changepos", None)
            # no change output
            if changepos < 0:
                changepos = None

            # generate all blinding stuff ourselves in deterministic way
            tx.unblind(
                self.master_blinding_key
            )  # get values and blinding factors for inputs
            seed = tagged_hash("liquid/blinding_seed", self.master_blinding_key.secret)
            try:
                tx.blind(seed)  # generate all blinding factors etc
                # proprietary fields for Specter - 00 is global blinding seed
                tx.unknown[b"\xfc\x07specter\x00"] = seed
            except PSBTError:
                seed = None

            # reblind and encode nonces in change output
            if seed and changepos is not None:
                txseed = tx.txseed(seed)
                # blinding seed to calculate per-output nonces
                message = b"\x01\x00\x20" + txseed
                for i, out in enumerate(tx.outputs):
                    # skip unblinded and change address itself
                    if out.blinding_pubkey is None or i == changepos:
                        continue
                    # key 01<i> is blinding pubkey for output i
                    message += b"\x05\x01" + i.to_bytes(4, "little")
                    # message is blinding pubkey
                    message += bytes([len(out.blinding_pubkey)]) + out.blinding_pubkey
                # extra message for rangeproof - proprietary field
                tx.outputs[changepos].unknown[b"\xfc\x07specter\x01"] = message
                # re-generate rangeproof with extra message
                nonce = tagged_hash(
                    "liquid/range_proof", txseed + changepos.to_bytes(4, "little")
                )
                tx.outputs[changepos].reblind(nonce, extra_message=message)

            res["psbt"] = str(tx)
        return res

    def walletprocesspsbt(self, psbt, *args, **kwargs):
        try:
            if self.getwalletinfo().get("private_keys_enabled", False):
                psbt = to_canonical_pset(psbt)
        except Exception as e:
            logger.warn(f"Failed to clean psbt: {e}")
        return super().__getattr__("walletprocesspsbt")(psbt, *args, **kwargs)

    def finalizepsbt(self, psbt, *args, **kwargs):
        psbt = to_canonical_pset(psbt)
        res = super().__getattr__("finalizepsbt")(psbt, *args, **kwargs)
        if res["complete"] == False:
            try:
                # try using our finalizer
                tx = finalizer.finalize_psbt(PSET.from_string(psbt))
                if tx and self.testmempoolaccept([str(tx)]):
                    return {"complete": True, "hex": str(tx)}
            except Exception as e:
                logger.exception(e)
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

            for inp1, inp2 in zip(tx.inputs, t2.inputs):
                inp1.value = inp1.value or inp2.value
                inp1.value_blinding_factor = (
                    inp1.value_blinding_factor or inp2.value_blinding_factor
                )
                inp1.asset = inp1.asset or inp2.asset
                inp1.asset_blinding_factor = (
                    inp1.asset_blinding_factor or inp2.asset_blinding_factor
                )
                inp1.txid = inp1.txid or inp2.txid
                inp1.vout = inp1.vout or inp2.vout
                inp1.sequence = inp1.sequence or inp2.sequence
                inp1.non_witness_utxo = inp1.non_witness_utxo or inp2.non_witness_utxo
                inp1.sighash_type = inp1.sighash_type or inp2.sighash_type
                inp1.redeem_script = inp1.redeem_script or inp2.redeem_script
                inp1.witness_script = inp1.witness_script or inp2.witness_script
                inp1.final_scriptsig = inp1.final_scriptsig or inp2.final_scriptsig
                inp1.final_scriptwitness = (
                    inp1.final_scriptwitness or inp2.final_scriptwitness
                )
                inp1.partial_sigs.update(inp2.partial_sigs)
                inp1.bip32_derivations.update(inp2.bip32_derivations)
                inp1.unknown.update(inp2.unknown)
                inp1.range_proof = inp1.range_proof or inp2.range_proof

            for out1, out2 in zip(tx.outputs, t2.outputs):
                out1.value_commitment = out1.value_commitment or out2.value_commitment
                out1.value_blinding_factor = (
                    out1.value_blinding_factor or out2.value_blinding_factor
                )
                out1.asset_commitment = out1.asset_commitment or out2.asset_commitment
                out1.asset_blinding_factor = (
                    out1.asset_blinding_factor or out2.asset_blinding_factor
                )
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

    def decoderawtransaction(self, tx):
        blinded = super().__getattr__("decoderawtransaction")(tx)
        try:
            unblinded = self.unblindrawtransaction(tx)["hex"]
            obj = super().__getattr__("decoderawtransaction")(unblinded)
            if "vsize" in blinded:
                obj["vsize"] = blinded["vsize"]
            if "size" in blinded:
                obj["size"] = blinded["size"]
            if "weight" in blinded:
                obj["weight"] = blinded["weight"]
            if "hex" in blinded:
                obj["hex"] = blinded["hex"]
        except Exception as e:
            logger.error(e)
            obj = blinded
        try:
            # unblind the rest of outputs
            b = LTransaction.from_string(tx)

            mbpk = self.master_blinding_key
            net = get_network(self.getblockchaininfo().get("chain"))

            outputs = obj["vout"]
            datas = []
            fee = 0
            # search for datas encoded in rangeproofs
            for i, out in enumerate(b.vout):
                o = outputs[i]
                if isinstance(out.value, int):
                    if "value" in o:
                        assert o["value"] == round(out.value * 1e-8, 8)
                    else:
                        o["value"] = round(out.value * 1e-8, 8)
                    if "asset" in o:
                        assert o["asset"] == bytes(reversed(out.asset[-32:])).hex()
                    else:
                        o["asset"] = bytes(reversed(out.asset[-32:])).hex()
                    try:
                        o["scriptPubKey"]["addresses"] = [
                            liquid_address(out.script_pubkey, network=net)
                        ]
                    except:
                        pass
                    if out.script_pubkey.data == b"":
                        # fee negative?
                        fee -= out.value

                pk = slip77.blinding_key(mbpk, out.script_pubkey)
                try:
                    res = out.unblind(pk.secret, message_length=1000)
                    value, asset, vbf, abf, extra, min_value, max_value = res
                    if "value" in o:
                        assert o["value"] == round(value * 1e-8, 8)
                    else:
                        o["value"] = round(value * 1e-8, 8)
                    if "asset" in o:
                        assert o["asset"] == bytes(reversed(asset[-32:])).hex()
                    else:
                        o["asset"] = bytes(reversed(asset[-32:])).hex()
                    try:
                        o["scriptPubKey"]["addresses"] = [
                            liquid_address(out.script_pubkey, pk, network=net)
                        ]
                    except:
                        pass
                    if len(extra.rstrip(b"\x00")) > 0:
                        datas.append(extra)
                except Exception as e:
                    pass

            # should be changed with seed from tx
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

            for i, out in enumerate(outputs):
                o = out
                if i in pubkeys and len(pubkeys[i]) in [33, 65]:
                    nonce = tagged_hash(
                        "liquid/range_proof", txseed + i.to_bytes(4, "little")
                    )
                    if b.vout[i].ecdh_pubkey == PrivateKey(nonce).sec():
                        try:
                            res = unblind(
                                pubkeys[i],
                                nonce,
                                b.vout[i].witness.range_proof.data,
                                b.vout[i].value,
                                b.vout[i].asset,
                                b.vout[i].script_pubkey,
                            )
                            value, asset, vbf, abf, extra, min_value, max_value = res
                            if "value" in o:
                                assert o["value"] == round(value * 1e-8, 8)
                            else:
                                o["value"] = round(value * 1e-8, 8)
                            if "asset" in o:
                                assert o["asset"] == bytes(reversed(asset[-32:])).hex()
                            else:
                                o["asset"] = bytes(reversed(asset[-32:])).hex()
                            try:
                                o["scriptPubKey"]["addresses"] = [
                                    liquid_address(
                                        b.vout[i].script_pubkey,
                                        PublicKey.parse(pubkeys[i]),
                                        network=net,
                                    )
                                ]
                            except:
                                pass
                        except Exception as e:
                            logger.warn(f"Failed at unblinding output {i}: {e}")
                    else:
                        logger.warn(f"Failed at unblinding: {e}")
            if fee != 0:
                obj["fee"] = round(-fee * 1e-8, 8)
        except Exception as e:
            logger.warn(f"Failed at unblinding transaction: {e}")
        return obj

    def __repr__(self) -> str:
        return f"<LiquidRpc {self.url}>"

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
            timeout=cls.default_timeout,  # Elements is slower
            session=rpc.session,
            proxy_url=rpc.proxy_url,
            only_tor=rpc.only_tor,
        )
