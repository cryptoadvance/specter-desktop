from ..wallet import *
from embit.liquid.pset import PSET

class LWallet(Wallet):

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
        # TODO: very minimal
        psbt = PSET.from_string(b64psbt)
        if not non_witness:
            # remove non_witness_utxo if we don't want them
            for inp in psbt.inputs:
                if inp.witness_utxo is not None:
                    inp.non_witness_utxo = None

        return psbt.to_string()