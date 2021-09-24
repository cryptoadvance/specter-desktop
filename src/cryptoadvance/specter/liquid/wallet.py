from ..wallet import *
from ..addresslist import Address
from embit import ec
from embit.liquid.pset import PSET
from embit.liquid.transaction import LTransaction
from embit.liquid.descriptor import LDescriptor
from embit.descriptor.checksum import add_checksum
from .txlist import LTxList
from .addresslist import LAddressList
from embit.liquid.addresses import to_unconfidential
from ..specter_error import SpecterError
from .util.pset import SpecterPSET


class LWallet(Wallet):
    MIN_FEE_RATE = 0.1
    AddressListCls = LAddressList
    TxListCls = LTxList
    TxCls = LTransaction
    PSBTCls = SpecterPSET
    DescriptorCls = LDescriptor

    @classmethod
    def construct_descriptor(
        cls, sigs_required, key_type, keys, devices, blinding_key=None
    ):
        """
        Creates a wallet descriptor from arguments.
        We need to pass `devices` for Liquid wallet, here it's not used.
        """
        # construct normal bitcoin descriptor first
        btcdescriptor = Wallet.construct_descriptor(
            sigs_required, key_type, keys, devices
        )

        # get blinding key for the wallet if it's not provided
        if len(devices) == 1 and blinding_key is None:
            blinding_key = devices[0].blinding_key
            if not blinding_key:
                raise SpecterError(
                    "Device doesn't have a blinding key. Please import it."
                )

        # if we don't have slip77 key for a device or it is multisig
        # we use chaincodes to generate slip77 key.
        if not blinding_key:
            # For now we use sha256(b"blinding_key", xor(chaincodes)) as a blinding key
            # where chaincodes are corresponding to xpub of the first receiving address.
            # It's not a standard but we use that until musig(blinding_xpubs) is implemented.
            # Chaincodes of the first address are not used anywhere else so they can be used
            # as a source for the blinding keys. They are also independent of the xpub's origin.
            xor = bytearray(32)
            desc_keys = btcdescriptor.derive(0, branch_index=0).keys
            for k in desc_keys:
                if k.is_extended:
                    chaincode = k.key.chain_code
                    for i in range(32):
                        xor[i] = xor[i] ^ chaincode[i]
            secret = hashlib.sha256(b"blinding_key" + bytes(xor)).digest()
            blinding_key = ec.PrivateKey(secret).wif()

        return cls.DescriptorCls.from_string(
            f"blinded(slip77({blinding_key}),{str(btcdescriptor)})"
        )

    def derive_descriptor(self, index: int, change: bool, keep_xpubs=False):
        """
        For derived descriptor for individual address we remove blinding key
        as it is used in HWI calls that doesn't support blinding descriptors yet.
        TODO: handle blinding keys in HWI
        """
        desc = super().derive_descriptor(index, change, keep_xpubs)
        desc.blinding_key = None
        return desc

    def getdata(self):
        self.fetch_transactions()
        self.check_utxo()
        self.get_info()
        # TODO: Should do the same for the non change address (?)
        # check if address was used already
        try:
            value_on_address = self.rpc.getreceivedbyaddress(
                self.change_address, assetlabel=None
            )
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

        options = {"includeWatching": True, "replaceable": rbf}
        extra_inputs = []
        # get change addresses for all assets + for LBTC
        change_addresses = [
            self.get_address(self.change_index + i, change=True, check_keypool=False)
            for i in range(len(assets) + 1)
        ]

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
                "changeAddresses": change_addresses,  # not supported by Elements - custom field for out LiquidRPC
            }

            # 209900 is pre-v21 for Elements Core
            if self.manager.bitcoin_core_version_raw >= 209900:
                options["add_inputs"] = selected_coins == []

            if fee_rate > 0:
                # bitcoin core needs us to convert sat/B to BTC/kB
                options["feeRate"] = round((fee_rate * 1000) / 1e8, 8)

            # looks like change_type is required in nested segwit wallets
            # but not in native segwit
            if "changeAddress" not in options and self.address_type:
                options["change_type"] = self.address_type

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
            # FIXME: get back change addresses
            # if "changeAddress" in psbt:
            #     options["changeAddress"] = psbt["changeAddress"]
            #     if "change_type" in options:
            #         options.pop("change_type")
            if "base64" in psbt:
                b64psbt = psbt["base64"]

        # looks like change_type is required in nested segwit wallets
        # but not in native segwit
        if "changeAddress" not in options and self.address_type:
            options["change_type"] = self.address_type

        if fee_rate > 0.0:
            if not existing_psbt:
                adjusted_fee_rate = self.adjust_fee(psbt, fee_rate)
                options["feeRate"] = "%.8f" % round((adjusted_fee_rate * 1000) / 1e8, 8)
            else:
                options["feeRate"] = "%.8f" % round((fee_rate * 1000) / 1e8, 8)
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
            psbt["fee_rate"] = options["feeRate"]
        # estimate full size
        tx_full_size = ceil(
            psbt["tx"]["vsize"] + len(psbt["inputs"]) * self.weight_per_input / 4
        )
        psbt["tx_full_size"] = tx_full_size

        psbt["base64"] = b64psbt
        psbt["amount"] = amounts
        psbt["address"] = addresses
        if assets:
            psbt["asset"] = assets
        psbt["time"] = time.time()
        psbt["sigs_count"] = 0

        psbt = self.PSBTCls.from_dict(psbt, self.descriptor, self.manager.chain)
        if not readonly:
            self.save_pending_psbt(psbt)
        return psbt.to_dict()

    def adjust_fee(self, psbt, fee_rate):
        psbt_fees_sats = int(psbt.get("fees", {}).get("bitcoin", 0) * 1e8)

        # TODO: handle non-blind outputs differently
        num_blinded_outs = len(psbt["outputs"]) - 1
        # estimate final size: add weight of inputs and outputs
        # out witness weight is 4245 (from some random tx)
        # commitments in blinded tx: 33 for nonce and 33 for value
        commitment_size = 33 + 33
        tx_full_size = ceil(
            psbt["tx"]["vsize"]
            + len(psbt["inputs"]) * self.weight_per_input / 4
            + num_blinded_outs * 4245 / 4
            # probably elements doesn't count commitments
            + len(psbt["inputs"]) * commitment_size
            + num_blinded_outs * commitment_size
        )
        return (
            fee_rate
            * (fee_rate / (psbt_fees_sats / psbt["tx"]["vsize"]))
            * (tx_full_size / psbt["tx"]["vsize"])
        )

    def addresses_info(self, is_change):
        """Create a list of (receive or change) addresses from cache and retrieve the
        related UTXO and amount.
        Parameters: is_change: if true, return the change addresses else the receive ones.
        """

        addresses_info = []

        addresses_cache = [
            v for _, v in self._addresses.items() if v.change == is_change
        ]

        for addr in addresses_cache:

            addr_utxo = 0
            addr_amount = 0
            addr_assets = {}

            for utxo in [
                utxo
                for utxo in self.full_utxo
                if to_unconfidential(utxo["address"]) == to_unconfidential(addr.address)
            ]:
                addr_amount = addr_amount + utxo["amount"]
                addr_utxo = addr_utxo + 1
                addr_assets[utxo.get("asset")] = (
                    addr_assets.get(utxo.get("asset"), 0) + utxo["amount"]
                )

            addresses_info.append(
                {
                    "index": addr.index,
                    "address": addr.address,
                    "label": addr.label,
                    "amount": addr_amount,
                    "used": bool(addr.used),
                    "utxo": addr_utxo,
                    "type": "change" if is_change else "receive",
                    "assets": addr_assets,
                }
            )

        return addresses_info

    @property
    def unconfidential_address(self):
        return to_unconfidential(self.address)
