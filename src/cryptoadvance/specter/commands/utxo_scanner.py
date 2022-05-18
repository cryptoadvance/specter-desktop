import logging
import threading
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.requests_tools import failsafe_request_get

logger = logging.getLogger(__name__)


class UtxoScanner:
    """A Command class which simplifies the scanning of UTXOs and the import into a (core+specter) wallet"""

    # 1. pass descriptor (change + recv) and range to rpc.scantxoutset
    #    get list of tx each having deriv-path
    # 2. Update the address-indexes with the max from recv+change (to get fresh addresses and not used once)
    # 3. rpc.getblockhash of height(each tx)
    # 4. rpc.gettxoutproof get a proof that the tx is included in a block, needs tx_id and blockhash for each tx
    #    This will only work on fullnodes (!)

    timeout = (
        300  # 0.001 # As this is async, have longer timeout for all rpc-calls: 5 mins
    )

    def __init__(self, wallet, requests_session, explorer: str = None, only_tor=False):
        if requests_session == None and explorer != None:
            raise SpecterError("Cannot use a blockchainexplorer without a Session!")

        if (
            explorer
            and explorer.endswith(".onion")
            and not requests_session.proxies["https"]
        ):
            raise SpecterError(
                "Cannot Query an Onion Explorer without a working Tor Setup! Check your Tor Setup or choose a non Tor Explorer."
            )
        self.wallet = wallet
        self.explorer = explorer
        self.requests_session = requests_session
        if self.explorer:
            self.explorer = self.explorer.rstrip("/")
        self.only_tor = only_tor
        self.error_msgs = []

    def execute(self, asyncc=False):
        if asyncc:
            t = threading.Thread(
                target=self._execute,
            )
            t.start()
        else:
            self._execute()

    def _execute(self):
        self.args = self.get_scantxoutset_args()
        # get something like:
        # [{'txid': '917a4d55...', 'vout': 1, 'scriptPubKey': '0014c313...5b19317',
        #   'desc': "wpkh([e3b947d9/84'/1'/0'/1/0]0244290480...ab2f94d940a7a)#gey9w279",
        #   'amount': 0.02119209, 'height': 1939628
        # }]
        self.unspents = self.wallet.rpc.scantxoutset(*self.args, timeout=self.timeout)[
            "unspents"
        ]
        logger.info(f"Found {len(self.unspents)} utxo")
        self.adjust_keypools()
        # Endgoal: calling importprunedfunds with the raw-transaction and a proof that the tx was included in a block
        self.add_blockhashes_to_txs_in_unspents()
        self.add_proofs_to_txs_in_unspents()
        self.add_rawtxs_to_txs_in_unspents()
        self.missing = [tx for tx in self.unspents if tx["raw"] is None]
        self.existing = [tx for tx in self.unspents if tx["raw"] is not None]
        # Now we're ready to import at least the existing txs
        logger.info(f"Importing {len(self.existing)} utxos to core-wallet")
        self.wallet.rpc.multi(
            [("importprunedfunds", tx["raw"], tx["proof"]) for tx in self.existing],
            timeout=self.timeout,
        )
        if len(self.missing) == 0:
            logger.info(f"no more missing utxos. Rescan completed successfully!")
            return self.execute_post_processing()
        # let's continue with the missing ones via an explorer
        if not self.check_explorer_working():
            logger.error(f"Completed unsuccessfully!")
            return self.execute_post_processing()
        self.add_proofs_to_txs_in_missing_via_exlorer()
        self.add_rawtxs_to_txs_in_missing_via_exlorer()
        self.existing_via_explorer = [
            tx for tx in self.missing if tx["raw"] is not None
        ]
        self.missing_even_after_explorer = [
            tx for tx in self.missing if tx["raw"] is None
        ]
        # Now importing the missing ones
        logger.info(
            f"Importing {len(self.existing_via_explorer)} utxos to core-wallet (found via Explorer)"
        )
        self.wallet.rpc.multi(
            [
                ("importprunedfunds", tx["raw"], tx["proof"])
                for tx in self.existing_via_explorer
            ],
            timeout=self.timeout,
        )
        if len(self.missing_even_after_explorer) != 0:
            logger.error(
                f"Even after explorer {len(self.missing_even_after_explorer)} txs could not be resolved"
            )
            logger.error(
                f"Giving up, here is a list of the still missing TXIDs: {[ tx['txid'] for tx in self.missing_even_after_explorer]}"
            )
            self.error_msgs.append(
                f"Some TXs could not be imported: {[ tx['txid'] for tx in self.missing_even_after_explorer]}"
            )
        return self.execute_post_processing()

    def execute_post_processing(self):
        self.wallet.fetch_transactions()
        self.wallet.check_addresses()

    def get_scantxoutset_args(self):
        return [
            "start",
            [
                {
                    "desc": self.wallet.recv_descriptor,
                    "range": max(self.wallet.keypool, 1000),
                },
                {
                    "desc": self.wallet.change_descriptor,
                    "range": max(self.wallet.change_keypool, 1000),
                },
            ],
        ]

    def adjust_keypools(self):
        """check the unspent for max indexes of recv+change addresses and adjusts the index of the wallet (if needed)
        saves the wallet if changed.
        """
        # check derivation indexes in found unspents (last 2 indexes in [brackets])
        derivations = [
            #                      purpose / account / cointype / change / index
            # {... 'desc': "wpkh([e3b947d9/84'/1'/0'/1/0]02442...7a)#gey9w279"
            tx["desc"].split("[")[1].split("]")[0].split("/")[-2:]
            for tx in self.unspents
        ]
        # we get a list of change / index parts of the derivations
        # [['1', '0'],['1', '1'],['0', '2']] represents 2 change and one recv-address (index 2)

        # get the maximum index for both address-types:
        max_recv = max([-1] + [int(der[1]) for der in derivations if der[0] == "0"])
        max_change = max([-1] + [int(der[1]) for der in derivations if der[0] == "1"])

        updated = False
        if max_recv >= self.wallet.address_index:
            # skip to max_recv
            self.wallet.address_index = max_recv
            logger.info(f"Adjusted address_index of {self.wallet} to {max_change}")
            # get next
            self.wallet.getnewaddress(change=False, save=False)
            updated = True
        if max_change >= self.wallet.change_index:
            # skip to max_change
            self.wallet.change_index = max_change
            logger.info(f"Adjusted change_index of {self.wallet} to {max_change}")
            # get next
            self.wallet.getnewaddress(change=True, save=False)
            updated = True
        # save only if needed
        if updated:
            self.wallet.save_to_file()

    def add_blockhashes_to_txs_in_unspents(self):
        """includes the blockhash of the block each tx in unspents has been mined into"""
        res = self.wallet.rpc.multi(
            [("getblockhash", tx["height"]) for tx in self.unspents],
            timeout=self.timeout,
        )
        block_hashes = [r["result"] for r in res]
        for i, tx in enumerate(self.unspents):
            # each tx in the unspents get the hash of the block it has been included in
            tx["blockhash"] = block_hashes[i]

    def add_proofs_to_txs_in_unspents(self):
        """includes the proof that the txs in unspents has been mined into the block"""
        res = self.wallet.rpc.multi(
            [("gettxoutproof", [tx["txid"]], tx["blockhash"]) for tx in self.unspents],
            timeout=self.timeout,
        )
        proofs = [r["result"] for r in res]
        for i, tx in enumerate(self.unspents):
            tx["proof"] = proofs[i]

    def add_rawtxs_to_txs_in_unspents(self):
        """includes the raw tx to the txs in unspents"""
        res = self.wallet.rpc.multi(
            [
                ("getrawtransaction", tx["txid"], False, tx["blockhash"])
                for tx in self.unspents
            ],
            timeout=self.timeout,
        )
        raws = [r["result"] for r in res]
        for i, tx in enumerate(self.unspents):
            tx["raw"] = raws[i]

    def check_explorer_working(self):
        """returns a boolean if the explorer link is usable. Will log.error and fill self.error_msgs if not"""
        if self.explorer is None:
            logger.error(
                f"Not all txs could be resolved and can't use explorer to get the rest"
            )
            self.error_msgs.append(
                "Not all txs could be resolved and can't use explorer to get the rest"
            )
            return False
        if not self.explorer.startswith("http"):
            logger.error(f"explorer seem to have an invalid url: {self.explorer}")
            self.error_msgs.append(
                f"explorer seem to have an invalid url: {self.explorer}"
            )
            return False
        try:
            request = failsafe_request_get(
                self.requests_session, f"{self.explorer}", parse_json=False
            )
        except SpecterError:
            return False
        if not request.ok:
            logger.error(f"explorer seem to have an invalid url: {self.explorer}")
            self.error_msgs.append(
                f"explorer seem to have an invalid url: {self.explorer}"
            )
            return False
        return True

    def add_proofs_to_txs_in_missing_via_exlorer(self):
        proofs = [
            self.requests_session.get(
                f"{self.explorer}/api/tx/{tx['txid']}/merkleblock-proof"
            ).text
            for tx in self.missing
        ]
        for i, tx in enumerate(self.missing):
            tx["proof"] = proofs[i]

    def add_rawtxs_to_txs_in_missing_via_exlorer(self):
        raws = [
            self.requests_session.get(f"{self.explorer}/api/tx/{tx['txid']}/hex").text
            for tx in self.missing
        ]
        for i, tx in enumerate(self.missing):
            tx["raw"] = raws[i]
