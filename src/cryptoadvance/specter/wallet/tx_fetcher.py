import logging
from .abstract_wallet import AbstractWallet

logger = logging.getLogger(__name__)


class TxFetcher:
    """A class to refactor the fetch_transaction_method which no one understands"""

    LISTTRANSACTIONS_BATCH_SIZE = 1000

    def __init__(self, wallet: AbstractWallet):
        self.wallet = wallet

    def _fetch_transactions(self):

        # unconfirmed_selftransfers needed since Bitcoin Core does not properly list `selftransfer` txs in `listtransactions` command
        # Until v0.21, it listed there consolidations to a receive address, but not change address
        # Since v0.21, it does not list there consolidations at all
        # Therefore we need to check here if a transaction might got confirmed
        # NOTE: This might be a problem in case of re-org...
        # More details: https://github.com/cryptoadvance/specter-desktop/issues/996

        arr = [
            tx["result"]
            for tx in self.unconfirmed_selftransfers_txs
            if tx.get("result")
        ]
        arr.extend(self.interesting_txs())
        txs = self.transform_to_dict_with_txid_as_key(
            arr
        )  # and gettransaction as value

        # fix for core versions < v0.20 (add blockheight if not there)
        self.fill_blockheight_if_necessary(txs)

        if self.wallet.use_descriptors:
            # Get all used addresses that belong to the wallet

            addresses_info = self.extract_addresses(txs)

            # representing the highest index of the addresses from the wallet and
            # the passed addresses
            (
                max_used_receiving,
                max_used_change,
            ) = self.calculate_max_used_from_addresses(addresses_info)

            # If max receiving address bigger than current max receiving index minus the gap limit - self._addresses.max_index(change=False)
            if (
                max_used_receiving + self.wallet.GAP_LIMIT
                > self.wallet._addresses.max_index(change=False)
            ):
                addresses = [
                    dict(
                        address=self.wallet.get_address(
                            idx, change=False, check_keypool=False
                        ),
                        index=idx,
                        change=False,
                    )
                    for idx in range(
                        self.wallet.addresses.max_index(change=False),
                        max_used_receiving + self.wallet.GAP_LIMIT,
                    )
                ]
                self.wallet.addresses.add(addresses, check_rpc=False)

            # If max change address bigger than current max change index minus the gap limit  - wallet.addresses.max_index(change=True)
            if (
                max_used_change + self.wallet.GAP_LIMIT
                > self.wallet.addresses.max_index(change=True)
            ):
                # Add change addresses until the new max address plus the GAP_LIMIT
                change_addresses = [
                    dict(
                        address=self.wallet.get_address(
                            idx, change=True, check_keypool=False
                        ),
                        index=idx,
                        change=True,
                    )
                    for idx in range(
                        self.wallet.addresses.max_index(change=True),
                        max_used_change + self.wallet.GAP_LIMIT,
                    )
                ]
                self.wallet.addresses.add(change_addresses, check_rpc=False)

        # only delete with confirmed txs
        self.wallet.delete_spent_pending_psbts(
            [
                tx["hex"]
                for tx in txs.values()
                if tx.get("confirmations", 0) > 0 or tx.get("blockheight")
            ]
        )
        self.wallet.transactions.add(txs)

    def is_interesting_tx(self, tx: dict):
        """transactions that we don't know about,
        # or that it has a different blockhash (reorg / confirmed)
        # or doesn't have an address(?)
        # or has wallet conflicts
        """
        if (
            # we don't know about tx
            tx["txid"] not in self.wallet._transactions
            # we don't know addresses
            or not self.wallet._transactions[tx["txid"]].get("address", None)
            # blockhash is different (reorg / unconfirmed)
            or self.wallet._transactions[tx["txid"]].get("blockhash", None)
            != tx.get("blockhash", None)
            # we have conflicts
            or self.wallet._transactions[tx["txid"]].get("conflicts", [])
            != tx.get("walletconflicts", [])
        ):
            return True
        return False

    def interesting_txs(self):
        """returns an array of interesting transactions (see is_interesting_tx() ) where txid is
        the key and the result is whatever listtransactions is retuirning as values
        """
        idx = 0
        arr = []
        while True:
            txlist = self.wallet.rpc.listtransactions(
                "*",
                self.LISTTRANSACTIONS_BATCH_SIZE,  # count
                self.LISTTRANSACTIONS_BATCH_SIZE * idx,  # skip
                True,
            )
            # filter interesting TXs
            res = [tx for tx in txlist if self.is_interesting_tx(tx)]
            arr.extend(res)
            idx += 1
            # stop if we reached known transactions
            # not sure if Core <20 returns last batch or empty array at the end
            if (
                len(res) < self.LISTTRANSACTIONS_BATCH_SIZE
                or len(arr) < self.LISTTRANSACTIONS_BATCH_SIZE * idx
            ):
                break

        return arr

    def transform_to_dict_with_txid_as_key(self, arr):
        """gets an array of tx-dicts where and transoforms it
        to a dict with txid as keys and the corresponding result
        of gettransaction as value.
        """
        # Start with an dict with txids as keys and None as values:
        txs = dict.fromkeys([a["txid"] for a in arr])
        txids = list(txs.keys())
        # get all raw transactions
        res = self.wallet.rpc.multi([("gettransaction", txid) for txid in txids])
        for i, r in enumerate(res):
            txid = txids[i]
            # check if we already added it
            if txs.get(txid, None) is not None:
                continue
            txs[txid] = r["result"]
        return txs

    def fill_blockheight_if_necessary(self, txs):
        """
        This is a fix for Bitcoin Core versions < v0.20
        These do not return the blockheight as part of the `gettransaction` command
        So here we check if this property is lacking and if so
        query the current block height and manually calculate it.

        Remove after dropping Core v0.19 support
        """
        check_blockheight = False
        for tx in txs.values():
            if tx and tx.get("confirmations", 0) > 0 and "blockheight" not in tx:
                check_blockheight = True
                break
        if check_blockheight:
            current_blockheight = self.wallet.rpc.getblockcount()
            for tx in txs.values():
                if tx.get("confirmations", 0) > 0:
                    tx["blockheight"] = current_blockheight - tx["confirmations"] + 1

    @property
    def unconfirmed_selftransfers_txs(self):
        if not hasattr(self, "_unconfirmed_selftransfers_txs"):
            unconfirmed_selftransfers = [
                txid
                for txid in self.wallet._transactions
                if self.wallet._transactions[txid].category == "selftransfer"
                and not self.wallet._transactions[txid].get("blockhash", None)
            ]
            unconfirmed_selftransfers_txs = []
            if unconfirmed_selftransfers:
                self._unconfirmed_selftransfers_txs = self.wallet.rpc.multi(
                    [("gettransaction", txid) for txid in unconfirmed_selftransfers]
                )
            else:
                self._unconfirmed_selftransfers_txs = []
        return self._unconfirmed_selftransfers_txs

    def extract_addresses(self, txs):
        """Takes txs (dict with txid as key and the result of gettransaction as value )
        and extracts all the addresses which
        * belongs to the wallet
        * are not yet in self.addresses
        """
        potential_relevant_txs = [
            tx
            for tx in txs.values()
            if tx
            and tx.get("details")
            and (
                tx.get("details")[0].get("category") != "send"
                and tx["details"][0].get("address") not in self.wallet.addresses
            )
        ]

        addresses_info_multi = self.wallet.rpc.multi(
            [
                ("getaddressinfo", address)
                for address in [
                    tx["details"][0].get("address") for tx in potential_relevant_txs
                ]
                if address
            ]
        )

        addresses_info = [
            r["result"]
            for r in addresses_info_multi
            if r["result"].get("ismine", False)
        ]
        logger.info(f"Those addresses got used recently: {addresses_info}")
        return addresses_info

    def calculate_max_used_from_addresses(self, addresses_info):
        """Return a tuple of max_used_receiving and max_used_change
        representing the highest index of the addresses from the wallet and
        the passed addresses
        """
        # Gets max index used receiving and change addresses
        max_used_receiving = self.wallet.addresses.max_used_index(change=False)
        max_used_change = self.wallet.addresses.max_used_index(change=True)

        for address in addresses_info:
            desc = self.wallet.DescriptorCls.from_string(address["desc"])
            indexes = [
                {
                    "idx": k.origin.derivation[-1],
                    "change": k.origin.derivation[-2],
                }
                for k in desc.keys
            ]
            for idx in indexes:
                if int(idx["change"]) == 0:
                    max_used_receiving = max(max_used_receiving, int(idx["idx"]))
                elif int(idx["change"]) == 1:
                    max_used_change = max(max_used_change, int(idx["idx"]))
        return max_used_receiving, max_used_change

    @classmethod
    def fetch_transactions(cls, wallet: AbstractWallet):
        """Loads new transactions from Bitcoin Core. A quite confusing method which mainly tries to figure out which transactions are new
        and need to be added to the local TxList wallet._transactions and adding them.
        So the method doesn't return anything but has these side_effects:
        1. Adding the new interesting transactions to wallet._transactions
        2. for wallet.use_descriptors create new addresses and add them to wallet._addresses
        3. calls wallet.delete_spent_pending_psbts
        Most of that code could probably encapsulated in the TxList class.
        """
        tx_fetcher = TxFetcher(wallet)
        tx_fetcher._fetch_transactions()
