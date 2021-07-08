from ..wallet import *
from ..addresslist import Address
from embit import ec
from embit.liquid.pset import PSET
from embit.liquid.transaction import LTransaction
from .txlist import LTxList
from .addresslist import LAddressList


class LWallet(Wallet):
    MIN_FEE_RATE = 0.1
    AddressListCls = LAddressList
    TxListCls = LTxList

    @classmethod
    def create(
        cls,
        rpc,
        rpc_path,
        working_folder,
        device_manager,
        wallet_manager,
        name,
        alias,
        sigs_required,
        key_type,
        keys,
        devices,
        core_version=None,
    ):
        """Creates a wallet. If core_version is not specified - get it from rpc"""
        # get xpubs in a form [fgp/der]xpub from all keys
        xpubs = [key.metadata["combined"] for key in keys]
        recv_keys = ["%s/0/*" % xpub for xpub in xpubs]
        change_keys = ["%s/1/*" % xpub for xpub in xpubs]
        is_multisig = len(keys) > 1
        # we start by constructing an argument for descriptor wrappers
        if is_multisig:
            recv_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(recv_keys)
            )
            change_descriptor = "sortedmulti({},{})".format(
                sigs_required, ",".join(change_keys)
            )
        else:
            recv_descriptor = recv_keys[0]
            change_descriptor = change_keys[0]
        # now we iterate over script-type in reverse order
        # to get sh(wpkh(xpub)) from sh-wpkh and xpub
        arr = key_type.split("-")
        for el in arr[::-1]:
            recv_descriptor = "%s(%s)" % (el, recv_descriptor)
            change_descriptor = "%s(%s)" % (el, change_descriptor)

        # get blinding key for the wallet
        blinding_key = None
        if len(devices) == 1:
            blinding_key = devices[0].blinding_key
        # if we don't have slip77 key for a device or it is multisig
        # we use chaincodes to generate slip77 key.
        if not blinding_key:
            desc = LDescriptor.from_string(recv_descriptor)
            # For now we use sha256(b"blinding_key", xor(chaincodes)) as a blinding key
            # where chaincodes are corresponding to xpub of the first receiving address.
            # It's not a standard but we use that until musig(blinding_xpubs) is implemented.
            # Chaincodes of the first address are not used anywhere else so they can be used
            # as a source for the blinding keys. They are also independent of the xpub's origin.
            xor = bytearray(32)
            desc_keys = desc.derive(0).keys
            for k in desc_keys:
                if k.is_extended:
                    chaincode = k.key.chain_code
                    for i in range(32):
                        xor[i] = xor[i] ^ chaincode[i]
            secret = hashlib.sha256(b"blinding_key" + bytes(xor)).digest()
            blinding_key = ec.PrivateKey(secret).wif()
        if blinding_key:
            recv_descriptor = f"blinded(slip77({blinding_key}),{recv_descriptor})"
            change_descriptor = f"blinded(slip77({blinding_key}),{change_descriptor})"

        recv_descriptor = AddChecksum(recv_descriptor)
        change_descriptor = AddChecksum(change_descriptor)
        assert recv_descriptor != change_descriptor

        # get Core version if we don't know it
        if core_version is None:
            core_version = rpc.getnetworkinfo().get("version", 0)

        use_descriptors = core_version >= 209900
        # v20.99 is pre-v21 Elements Core for descriptors
        if use_descriptors:
            # Use descriptor wallet
            rpc.createwallet(os.path.join(rpc_path, alias), True, True, "", False, True)
        else:
            rpc.createwallet(os.path.join(rpc_path, alias), True)

        wallet_rpc = rpc.wallet(os.path.join(rpc_path, alias))
        # import descriptors
        args = [
            {
                "desc": desc,
                "internal": change,
                "timestamp": "now",
                "watchonly": True,
            }
            for (change, desc) in [(False, recv_descriptor), (True, change_descriptor)]
        ]
        for arg in args:
            if use_descriptors:
                arg["active"] = True
            else:
                arg["keypool"] = True
                arg["range"] = [0, cls.GAP_LIMIT]

        assert args[0] != args[1]

        # Descriptor wallets were introduced in v0.21.0, but upgraded nodes may
        # still have legacy wallets. Use getwalletinfo to check the wallet type.
        # The "keypool" for descriptor wallets is automatically refilled
        if use_descriptors:
            res = wallet_rpc.importdescriptors(args)
        else:
            res = wallet_rpc.importmulti(args, {"rescan": False})

        assert all([r["success"] for r in res])

        return cls(
            name,
            alias,
            "{} of {} {}".format(sigs_required, len(keys), purposes[key_type])
            if len(keys) > 1
            else purposes[key_type],
            addrtypes[key_type],
            "",
            -1,
            "",
            -1,
            0,
            0,
            recv_descriptor,
            change_descriptor,
            keys,
            devices,
            sigs_required,
            {},
            [],
            os.path.join(working_folder, "%s.json" % alias),
            device_manager,
            wallet_manager,
        )

    def getdata(self):
        self.fetch_transactions()
        self.check_utxo()
        self.get_info()
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        try:
            value_on_address = self.rpc.getreceivedbyaddress(self.change_address, assetlabel=None)
        except Exception as e:
            # Could happen if address not in wallet (wallet was imported)
            # try adding keypool
            logger.info(
                f"Didn't get transactions on change address {self.change_address}. Refilling keypool."
            )
            logger.error(e)
            self.keypoolrefill(0, end=self.keypool, change=False)
            self.keypoolrefill(0, end=self.change_keypool, change=True)
            value_on_address = {}

        # if not - just return
        if sum(value_on_address.values(), 0) > 0:
            self.change_index += 1
            self.getnewaddress(change=True)

    def get_balance(self):
        try:
            full_balance = (
                self.rpc.getbalances(assetlabel=None)["mine"]
                if self.use_descriptors
                else self.rpc.getbalances(assetlabel=None)["watchonly"]
            )
            balance = {"assets": {}}
            assets = {
                "bitcoin",
            }
            # get all assets
            for k in full_balance:
                for asset in full_balance[k].keys():
                    assets.add(asset)
            # get balances for every asset
            for asset in assets:
                asset_balance = {}
                for cat in full_balance:
                    v = full_balance[cat].get(asset, 0)
                    asset_balance[cat] = v
                if asset == "bitcoin":
                    balance.update(asset_balance)
                else:
                    balance["assets"][asset] = asset_balance

            # calculate available balance
            available = {}
            available.update(balance)
            # locked_utxo = self.rpc.listlockunspent()
            # we need better tx decoding here to include assets
            # for tx in locked_utxo:
            #     tx_data = self.gettransaction(tx["txid"])
            #     raw_tx = decoderawtransaction(tx_data["hex"], self.manager.chain)
            #     delta = raw_tx["vout"][tx["vout"]]["value"]
            #     if "confirmations" not in tx_data or tx_data["confirmations"] == 0:
            #         available["untrusted_pending"] -= delta
            #     else:
            #         available["trusted"] -= delta
            #         available["trusted"] = round(available["trusted"], 8)
            # available["untrusted_pending"] = round(available["untrusted_pending"], 8)
            balance["available"] = available
        except:
            balance = {
                "trusted": 0,
                "untrusted_pending": 0,
                "immature": 0,
                "available": {"trusted": 0, "untrusted_pending": 0},
                "assets": {},
            }
        self.balance = balance
        return self.balance

    def fetch_transactions(self):
        """Load transactions from Bitcoin Core"""
        arr = []
        idx = 0
        # unconfirmed_selftransfers needed since Bitcoin Core does not properly list `selftransfer` txs in `listtransactions` command
        # Until v0.21, it listed there consolidations to a receive address, but not change address
        # Since v0.21, it does not list there consolidations at all
        # Therefore we need to check here if a transaction might got confirmed
        # NOTE: This might be a problem in case of re-org...
        # More details: https://github.com/cryptoadvance/specter-desktop/issues/996
        unconfirmed_selftransfers = [
            txid
            for txid in self._transactions
            if self._transactions[txid].get("category", "") == "selftransfer"
            and not self._transactions[txid].get("blockhash", None)
        ]
        unconfirmed_selftransfers_txs = []
        if unconfirmed_selftransfers:
            unconfirmed_selftransfers_txs = self.rpc.multi(
                [("gettransaction", txid) for txid in unconfirmed_selftransfers]
            )
        while True:
            txlist = (
                self.rpc.listtransactions(
                    "*",
                    LISTTRANSACTIONS_BATCH_SIZE,
                    LISTTRANSACTIONS_BATCH_SIZE * idx,
                    True,
                )
                + [tx["result"] for tx in unconfirmed_selftransfers_txs]
            )
            # list of transactions that we don't know about,
            # or that it has a different blockhash (reorg / confirmed)
            # or doesn't have an address(?)
            # or has wallet conflicts
            res = [
                tx
                for tx in txlist
                if tx["txid"] not in self._transactions
                or not self._transactions[tx["txid"]].get("address", None)
                or self._transactions[tx["txid"]].get("blockhash", None)
                != tx.get("blockhash", None)
                or (
                    self._transactions[tx["txid"]].get("blockhash", None)
                    and not self._transactions[tx["txid"]].get("blockheight", None)
                )  # Fix for Core v19 with Specter v1
                or self._transactions[tx["txid"]].get("conflicts", [])
                != tx.get("walletconflicts", [])
            ]
            # TODO: Looks like Core ignore a consolidation (self-transfer) going into the change address (in listtransactions)
            # This means it'll show unconfirmed for us forever...
            arr.extend(res)
            idx += 1
            # not sure if Core <20 returns last batch or empty array at the end
            if (
                len(res) < LISTTRANSACTIONS_BATCH_SIZE
                or len(arr) < LISTTRANSACTIONS_BATCH_SIZE * idx
            ):
                break
        txs = dict.fromkeys([a["txid"] for a in arr])
        txids = list(txs.keys())
        # get all raw transactions
        res = self.rpc.multi([("gettransaction", txid) for txid in txids])
        for i, r in enumerate(res):
            txid = txids[i]
            # check if we already added it
            if txs.get(txid, None) is not None:
                continue
            txs[txid] = r["result"]

        # This is a fix for Bitcoin Core versions < v0.20
        # These do not return the blockheight as part of the `gettransaction` command
        # So here we check if this property is lacking and if so
        # query the current block height and manually calculate it.
        # ##################### Remove from here after dropping Core v0.19 support #####################
        check_blockheight = False
        for tx in txs.values():
            if tx and tx.get("confirmations", 0) > 0 and "blockheight" not in tx:
                check_blockheight = True
                break
        if check_blockheight:
            current_blockheight = self.rpc.getblockcount()
            for tx in txs.values():
                if tx.get("confirmations", 0) > 0:
                    tx["blockheight"] = current_blockheight - tx["confirmations"] + 1
        # ##################### Remove until here after dropping Core v0.19 support #####################
        self._transactions.add(txs)
        # if self.use_descriptors:
        #     while (
        #         len(
        #             [
        #                 tx
        #                 for tx in self._transactions
        #                 if self._transactions[tx]["category"] != "send"
        #                 and not self._transactions[tx]["address"]
        #             ]
        #         )
        #         != 0
        #     ):
        #         addresses = [
        #             dict(
        #                 address=self.get_address(
        #                     idx, change=False, check_keypool=False
        #                 ),
        #                 index=idx,
        #                 change=False,
        #             )
        #             for idx in range(
        #                 self._addresses.max_index(change=False),
        #                 self._addresses.max_index(change=False) + self.GAP_LIMIT,
        #             )
        #         ]
        #         change_addresses = [
        #             dict(
        #                 address=self.get_address(idx, change=True, check_keypool=False),
        #                 index=idx,
        #                 change=True,
        #             )
        #             for idx in range(
        #                 self._addresses.max_index(change=True),
        #                 self._addresses.max_index(change=True) + self.GAP_LIMIT,
        #             )
        #         ]
        #         self._addresses.add(addresses, check_rpc=False)
        #         self._addresses.add(change_addresses, check_rpc=False)

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

    # def gettransaction(self, txid, blockheight=None, decode=False, full=True):
    #     # TODO: only from RPC for now
    #     try:
    #         # From RPC
    #         tx_data = self.rpc.gettransaction(txid)
    #         if decode:
    #             return self.rpc.decoderawtransaction(tx_data["hex"])
    #         return tx_data
    #     except Exception as e:
    #         logger.warning("Could not get transaction {}, error: {}".format(txid, e))

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
        assets=None,
    ):
        """
        fee_rate: in sat/B or BTC/kB. If set to 0 Bitcoin Core sets feeRate automatically.
        """
        if fee_rate > 0 and fee_rate < self.MIN_FEE_RATE:
            fee_rate = self.MIN_FEE_RATE

        # FIXME: stupid scale of the fee rate for now
        fee_rate = 2 * fee_rate

        options = {"includeWatching": True, "replaceable": rbf}
        extra_inputs = []

        if not existing_psbt:
            # if not rbf_edit_mode:
            #     if self.full_available_balance < sum(amounts):
            #         raise SpecterError(
            #             "The wallet does not have sufficient funds to make the transaction."
            #         )

            # if selected_coins != []:
            #     still_needed = sum(amounts)
            #     for coin in selected_coins:
            #         coin_txid = coin.split(",")[0]
            #         coin_vout = int(coin.split(",")[1])
            #         coin_amount = self.gettransaction(coin_txid, decode=True)["vout"][
            #             coin_vout
            #         ]["value"]
            #         extra_inputs.append({"txid": coin_txid, "vout": coin_vout})
            #         still_needed -= coin_amount
            #         if still_needed < 0:
            #             break
            #     if still_needed > 0:
            #         raise SpecterError(
            #             "Selected coins does not cover Full amount! Please select more coins!"
            #         )
            # elif self.available_balance["trusted"] <= sum(amounts):
            #     txlist = self.rpc.listunspent(0, 0)
            #     b = sum(amounts) - self.available_balance["trusted"]
            #     for tx in txlist:
            #         extra_inputs.append({"txid": tx["txid"], "vout": tx["vout"]})
            #         b -= tx["amount"]
            #         if b < 0:
            #             break

            # subtract fee from amount of this output:
            # currently only one address is supported, so either
            # empty array (subtract from change) or [0]
            subtract_arr = [subtract_from] if subtract else []

            options = {
                "includeWatching": True,
                # FIXME: get back change addresses
                # "changeAddress": self.change_address,
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
                [
                    {addresses[i]: amounts[i], "asset": assets[i]}
                    for i in range(len(addresses))
                ],  # output
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
        if assets:
            psbt["asset"] = assets
        psbt["time"] = time.time()
        psbt["sigs_count"] = 0
        if not readonly:
            self.save_pending_psbt(psbt)

        return psbt
