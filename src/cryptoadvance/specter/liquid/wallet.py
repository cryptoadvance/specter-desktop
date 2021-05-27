from ..wallet import *
from ..addresslist import Address
from embit.liquid.pset import PSET
from embit.liquid.transaction import LTransaction

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
        psbt = PSET.from_string(b64psbt)

        if non_witness:
            for i, inp in enumerate(psbt.tx.vin):
                txid = psbt.tx.vin[0].txid.hex()
                try:
                    res = self.gettransaction(txid)
                    psbt.inputs[i].non_witness_utxo = LTransaction.from_string(res["hex"])
                except:
                    logger.error(
                        "Can't find previous transaction in the wallet. Signing might not be possible for certain devices..."
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