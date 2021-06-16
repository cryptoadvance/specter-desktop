from ..wallet import *
from ..addresslist import Address
from embit.liquid.pset import PSET
from embit.liquid.transaction import LTransaction


class LWallet(Wallet):
    MIN_FEE_RATE = 0.1

    def fetch_transactions(self):
        return

    def txlist(
        self,
        fetch_transactions=True,
        validate_merkle_proofs=False,
        current_blockheight=None,
    ):
        """Returns a list of all transactions in the wallet's CSV cache - processed with information to display in the UI in the transactions list
        #Parameters:
        #    fetch_transactions (bool): Update the TxList CSV caching by fetching transactions from the Bitcoin RPC
        #    validate_merkle_proofs (bool): Return transactions with validated_blockhash
        #    current_blockheight (int): Current blockheight for calculating confirmations number (None will fetch the block count from the RPC)
        """
        # TODO: only from RPC for now
        return self.rpc.listtransactions("*", 10000, 0, True)

    def gettransaction(self, txid, blockheight=None, decode=False):
        # TODO: only from RPC for now
        try:
            # From RPC
            tx_data = self.rpc.gettransaction(txid)
            if decode:
                return self.rpc.decoderawtransaction(tx_data["hex"])
            return tx_data
        except Exception as e:
            logger.warning("Could not get transaction {}, error: {}".format(txid, e))

    def fill_psbt(self, b64psbt, non_witness: bool = True, xpubs: bool = True):
        psbt = PSET.from_string(b64psbt)

        if non_witness:
            for inp in psbt.inputs:
                # we don't need to fill what is already filled
                if inp.non_witness_utxo is not None:
                    continue
                txid = inp.txid.hex()
                try:
                    res = self.gettransaction(txid)
                    inp.non_witness_utxo = Transaction.from_string(res["hex"])
                except Exception as e:
                    logger.error(
                        f"Can't find previous transaction in the wallet. Signing might not be possible for certain devices... Txid: {txid}, Exception: {e}"
                    )
        else:
            # remove non_witness_utxo if we don't want them
            for inp in psbt.inputs:
                if inp.witness_utxo is not None:
                    inp.non_witness_utxo = None

        if xpubs:
            # for multisig add xpub fields
            if len(self.keys) > 1:
                for k in self.keys:
                    key = bip32.HDKey.from_string(k.xpub)
                    if k.fingerprint != "":
                        fingerprint = bytes.fromhex(k.fingerprint)
                    else:
                        fingerprint = get_xpub_fingerprint(k.xpub)
                    if k.derivation != "":
                        der = bip32.parse_path(k.derivation)
                    else:
                        der = []
                    psbt.xpub[key] = DerivationPath(fingerprint, der)
        else:
            psbt.xpub = {}
        return psbt.to_string()

    def get_address_info(self, address):
        try:
            res = self.rpc.getaddressinfo(address)
            used = None
            if "desc" in res:
                used = self.rpc.getreceivedbyaddress(address, 0) > 0
            return Address(
                self.rpc,
                address=address,
                index=None
                if "desc" not in res
                else res["desc"].split("]")[0].split("/")[-1],
                change=None if "desc" not in res else res["ischange"],
                label=next(iter(res["labels"]), ""),
                used=used,
            )
        except:
            return None

    def createpsbt(
        self,
        addresses: [str],
        amounts: [float],
        subtract: bool = False,
        subtract_from: int = 0,
        fee_rate: float = 1.0,
        selected_coins=[],
        readonly=False,
        rbf=True,
        existing_psbt=None,
        rbf_edit_mode=False,
    ):
        """
        fee_rate: in sat/B or BTC/kB. If set to 0 Bitcoin Core sets feeRate automatically.
        """
        if fee_rate > 0 and fee_rate < self.MIN_FEE_RATE:
            fee_rate = self.MIN_FEE_RATE

        options = {"includeWatching": True, "replaceable": rbf}
        extra_inputs = []

        if not existing_psbt:
            if not rbf_edit_mode:
                if self.full_available_balance < sum(amounts):
                    raise SpecterError(
                        "The wallet does not have sufficient funds to make the transaction."
                    )

            if selected_coins != []:
                still_needed = sum(amounts)
                for coin in selected_coins:
                    coin_txid = coin.split(",")[0]
                    coin_vout = int(coin.split(",")[1])
                    coin_amount = self.gettransaction(coin_txid, decode=True)["vout"][
                        coin_vout
                    ]["value"]
                    extra_inputs.append({"txid": coin_txid, "vout": coin_vout})
                    still_needed -= coin_amount
                    if still_needed < 0:
                        break
                if still_needed > 0:
                    raise SpecterError(
                        "Selected coins does not cover Full amount! Please select more coins!"
                    )
            elif self.available_balance["trusted"] <= sum(amounts):
                txlist = self.rpc.listunspent(0, 0)
                b = sum(amounts) - self.available_balance["trusted"]
                for tx in txlist:
                    extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
                    b -= tx["amount"]
                    if b < 0:
                        break

            # subtract fee from amount of this output:
            # currently only one address is supported, so either
            # empty array (subtract from change) or [0]
            subtract_arr = [subtract_from] if subtract else []

            options = {
                "includeWatching": True,
                "changeAddress": self.change_address,
                "subtractFeeFromOutputs": subtract_arr,
                "replaceable": rbf,
            }

            # 209900 is pre-v21 for Elements Core
            if self.manager.bitcoin_core_version_raw >= 209900:
                options["add_inputs"] = selected_coins == []

            if fee_rate > 0:
                # bitcoin core needs us to convert sat/B to BTC/kB
                options["feeRate"] = round((fee_rate * 1000) / 1e8, 8)

            # don't reuse change addresses - use getrawchangeaddress instead
            r = self.rpc.walletcreatefundedpsbt(
                extra_inputs,  # inputs
                [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # output
                0,  # locktime
                options,  # options
                True,  # bip32-der
            )

            b64psbt = r["psbt"]
            psbt = self.rpc.decodepsbt(b64psbt)
        else:
            psbt = existing_psbt
            # vins from psbt v0 or v2
            if "tx" in psbt:
                extra_inputs = [
                    {"txid": tx["txid"], "vout": tx["vout"]} for tx in psbt["tx"]["vin"]
                ]
            else:
                extra_inputs = [
                    {"txid": inp["previous_txid"], "vout": inp["previous_vout"]}
                    for inp in psbt["inputs"]
                ]
            if "changeAddress" in psbt:
                options["changeAddress"] = psbt["changeAddress"]
            if "base64" in psbt:
                b64psbt = psbt["base64"]

        # if fee_rate > 0.0:
        #     if not existing_psbt:
        #         psbt_fees_sats = int(psbt["fee"] * 1e8)
        #         # estimate final size: add weight of inputs
        #         tx_full_size = ceil(
        #             psbt["tx"]["vsize"]
        #             + len(psbt["inputs"]) * self.weight_per_input / 4
        #         )
        #         adjusted_fee_rate = (
        #             fee_rate
        #             * (fee_rate / (psbt_fees_sats / psbt["tx"]["vsize"]))
        #             * (tx_full_size / psbt["tx"]["vsize"])
        #         )
        #         options["feeRate"] = "%.8f" % round((adjusted_fee_rate * 1000) / 1e8, 8)
        #     else:
        #         options["feeRate"] = "%.8f" % round((fee_rate * 1000) / 1e8, 8)
        #     r = self.rpc.walletcreatefundedpsbt(
        #         extra_inputs,  # inputs
        #         [{addresses[i]: amounts[i]} for i in range(len(addresses))],  # output
        #         0,  # locktime
        #         options,  # options
        #         True,  # bip32-der
        #     )

        #     b64psbt = r["psbt"]
        #     psbt = self.rpc.decodepsbt(b64psbt)
        #     psbt["fee_rate"] = options["feeRate"]
        # # estimate full size
        # tx_full_size = ceil(
        #     psbt["tx"]["vsize"] + len(psbt["inputs"]) * self.weight_per_input / 4
        # )
        # psbt["tx_full_size"] = tx_full_size

        psbt["base64"] = b64psbt
        psbt["amount"] = amounts
        psbt["address"] = addresses
        psbt["time"] = time.time()
        psbt["sigs_count"] = 0
        if not readonly:
            self.save_pending_psbt(psbt)

        return psbt
