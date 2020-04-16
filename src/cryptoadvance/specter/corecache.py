
cache = {}

class CoreCache():
    def __init__(self, cli):
        self.cli = cli
        self.walletname = cli.getwalletinfo()["walletname"]
        self.setup_cache()

    @property
    def change_addresses(self):
        return self.cache["change_addresses"]
    
    @property
    def wallet_addresses(self):
        return self.cache["addresses"] + self.change_addresses

    def setup_cache(self):
        """Setup cache object for wallet
        """
        if self.walletname not in cache: 
            cache[self.walletname] = {
                "raw_transactions": {},
                "transactions": [],
                "tx_count": None,
                "tx_changed": True,
                "last_block": None,
                "raw_tx_block_update": {},
                "addresses": [],
                "change_addresses": [],
                "scan_addresses": True
            }

    def cache_raw_txs(self, cli_txs):
        """Cache `raw_transactions` (with full data on all the inputs and outputs of each tx)
        """        
        # Get list of all tx ids
        txids = list(dict.fromkeys(cli_txs.keys()))
        tx_count = len(txids)

        # If there are new transactions (if the transations count changed)
        if tx_count != self.cache["tx_count"]:
            for txid in txids:
                # Cache each tx, if not already cached.
                # Data is immutable (unless reorg occurs) and can be saved in a file for permanent caching
                if txid not in self.cache["raw_transactions"]:
                    # Call Bitcoin Core to get the "raw" transaction - allows to read detailed inputs and outputs
                    raw_tx_hex = self.cli.gettransaction(txid)["hex"]
                    raw_tx = self.cli.decoderawtransaction(raw_tx_hex)
                    # Some data (like fee and category, and when unconfirmed also time) available from the `listtransactions`
                    # command is not available in the `getrawtransacion` - so add it "manually" here.
                    if "fee" in cli_txs[txid]:
                        raw_tx["fee"] = cli_txs[txid]["fee"]
                    if "category" in cli_txs[txid]:
                        raw_tx["category"] = cli_txs[txid]["category"]
                    if "time" in cli_txs[txid]:
                        raw_tx["time"] = cli_txs[txid]["time"]

                    if "blockhash" in cli_txs[txid]:
                        raw_tx["block_height"] = self.cli.getblockheader(cli_txs[txid]["blockhash"])["height"]
                    else:
                        raw_tx["block_height"] = -1

                    # Loop on the transaction's inputs
                    # If not a coinbase transaction:
                    # Get the the output data corresponding to the input (that is: input_txid[output_index])
                    tx_ins = []
                    for vin in raw_tx["vin"]:
                        # If the tx is a coinbase tx - set `coinbase` to True
                        if "coinbase" in vin:
                            raw_tx["coinbase"] = True
                            break
                        # If the tx is a coinbase tx - set `coinbase` to True
                        vin_txid = vin["txid"]
                        vin_vout = vin["vout"]
                        try:
                            raw_tx_hex = self.cli.gettransaction(vin_txid)["hex"]
                            tx_in = self.cli.decoderawtransaction(raw_tx_hex)["vout"][vin_vout]
                            tx_in["txid"] = vin["txid"]
                            tx_ins.append(tx_in)
                        except:
                            pass
                    # For each output in the tx_ins list (the tx inputs in their output "format")
                    # Create object with the address, amount, and whatever the address belongs to the wallet (`internal=True` if it is).
                    raw_tx["from"] = [{
                        "address": out["scriptPubKey"]["addresses"][0],
                        "amount": out["value"],
                        "internal": out["scriptPubKey"]["addresses"][0] in self.wallet_addresses
                    } for out in tx_ins]
                    # For each output in the tx (`vout`)
                    # Create object with the address, amount, and whatever the address belongs to the wallet (`internal=True` if it is).
                    raw_tx["to"] = [({
                        "address": out["scriptPubKey"]["addresses"][0],
                        "amount": out["value"],
                        "internal": out["scriptPubKey"]["addresses"][0] in self.wallet_addresses
                    }) for out in raw_tx["vout"] if "addresses" in out["scriptPubKey"]]
                    # Save the raw_transaction to the cache
                    cache[self.walletname]["raw_transactions"][txid] = raw_tx
            # Set the tx count to avoid unnecessary indexing
            cache[self.walletname]["tx_count"] = tx_count
            # Set the tx changed to indicate the there are new transactions to cache
            cache[self.walletname]["tx_changed"] = True
        else:
            # Set the tx changed to False to avoid unnecessary indexing
            cache[self.walletname]["tx_changed"] = False

        # If unconfirmed transactions were mined, assign them their block height
        blocks = self.cli.getblockcount()
        if blocks != self.cache["last_block"]:
            for txid in self.cache["raw_transactions"]:
                if self.cache["raw_transactions"][txid]["block_height"] == -1 and "blockhash" in cli_txs[txid]:
                    height = self.cli.getblockheader(cli_txs[txid]["blockhash"])["height"]
                    cache[self.walletname]["raw_transactions"][txid]["block_height"] = height
                    cache[self.walletname]["raw_tx_block_update"][txid] = height
            cache[self.walletname]["last_block"] = blocks

        return self.cache["raw_transactions"]
    
    def cache_txs(self, raw_txs):
        """Caches the transactions list.
            Cache the inputs and outputs which belong to the user's wallet for each `raw_transaction` 
            This method relies on a few assumptions regarding the txs format to cache data properly:
                - In `send` transactions, all inputs belong to the wallet.
                - In `send` transactions, there is only one output not belonging to the wallet (i.e. only one recipient).
                - In `coinbase` transactions, there is only one input.
                - Change addresses are derived from the path used by Specter
        """
        # Get the cached `raw_transactions` dict (txid -> tx) as a list of txs
        transactions = list(sorted(raw_txs.values(), key = lambda tx: tx['time'], reverse=True))
        result = []

        # If unconfirmed transactions were mined, assign them their block height
        if len(self.cache["raw_tx_block_update"]) > 0:
            for i in range(0, len(self.cache["transactions"])):
                if self.cache["transactions"][i]["txid"] in cache[self.walletname]["raw_tx_block_update"]:
                    cache[self.walletname]["transactions"][i]["block_height"] = cache[self.walletname]["raw_tx_block_update"][cache[self.walletname]["transactions"][i]["txid"]]
            cache[self.walletname]["raw_tx_block_update"] = {}

        # If the `raw_transactions` did not change - exit here.
        if not self.cache["tx_changed"]:
            return self.cache["transactions"]

        # Loop through the raw_transactions list
        for i, tx in enumerate(transactions):
            # If tx is a user generated one (categories: `send`/ `receive`) and not coinbase (categories: `generated`/ `immature`)
            if tx["category"] == "send" or tx["category"] == "receive":
                is_send = True
                is_self = True

                # Check if the transaction is a `send` or not (if all inputs belong to the wallet)
                if len(tx["from"]) == 0:
                    is_send = False

                for fromdata in tx["from"]:
                    if not fromdata["internal"]:
                        is_send = False

                # Check if the transaction is a `self-transfer` (if all inputs and all outputs belong to the wallet)
                for to in tx["to"]:
                    if not is_send or not to["internal"]:
                        is_self = False
                        break

                tx["is_self"] = is_self

                if not is_send or is_self:
                    for to in tx["to"]:
                        if to["internal"]:
                            # Cache received outputs
                            result.append(self.prepare_tx(tx, to, "receive", destination=None, is_change=(to["address"] in self.change_addresses)))

                if is_send or is_self:
                    destination = None
                    for to in tx["to"]:
                        if to["address"] in self.change_addresses and not is_self:
                            # Cache change output
                            result.append(self.prepare_tx(tx, to, "receive", destination=destination, is_change=True))
                        elif not to["internal"] or (is_self and to["address"] not in self.change_addresses):
                            destination = to
                    for fromdata in tx["from"]:
                        # Cache sent inputs
                        result.append(self.prepare_tx(tx, fromdata, "send", destination=destination))
            else:
                tx["is_self"] = False
                # Cache coinbase output
                result.append(self.prepare_tx(tx, tx["to"][0], tx["category"]))

        # Save the result to the cache
        cache[self.walletname]["transactions"] = result
        return self.cache["transactions"]
    
    def prepare_tx(self, tx, output, category, destination=None, is_change=False):
        tx_clone = tx.copy()
        tx_clone["destination"] = destination
        tx_clone["address"] = output["address"]
        tx_clone["amount"] = output["amount"]
        tx_clone["category"] = category
        tx_clone["is_change"] = is_change
        return tx_clone

    def update_txs(self, txs):
        """Cache Bitcoin Core `listtransactions` result
        """
        # For now avoid caching orphan transactions. We might want to show them somehow in the future.
        cli_txs = {tx["txid"]: tx for tx in txs if tx["category"] != "orphan"}
        raw_txs = self.cache_raw_txs(cli_txs)
        cached_txs = self.cache_txs(raw_txs)

        return cached_txs

    def update_addresses(self, addresses, change=False):
        if change:
            cache[self.walletname]["change_addresses"] += list(dict.fromkeys(self.cache["change_addresses"] + addresses))
        else:
            cache[self.walletname]["addresses"] += list(dict.fromkeys(self.cache["addresses"] + addresses))

    def scanning_started(self):
        cache[self.walletname]["scan_addresses"] = True
    
    def scanning_ended(self):
        cache[self.walletname]["scan_addresses"] = False

    @property
    def scan_addresses(self):
        return self.cache["scan_addresses"]

    def rebuild_cache(self):
        del cache[self.walletname]
        self.setup_cache()

    @property
    def cache(self):
        return cache[self.walletname]
