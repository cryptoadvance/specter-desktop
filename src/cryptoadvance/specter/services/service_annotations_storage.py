import os

from cryptoadvance.specter.managers.genericdata_manager import GenericDataManager
from cryptoadvance.specter.wallet import Wallet


class ServiceAnnotationsStorage(GenericDataManager):
    """
    Stores Service-specific annotations for addresses and txs. Each wallet + service
    pairing will get its own <wallet_alias>_<service>.json file.

    Annotations must be in a json-serializable dict, keyed on addr or tx:
    {
        "someaddress": {
            "foo": 1,
            "bar": "hello",
        }
    }
    """

    def __init__(self, service_id: str, wallet: Wallet):
        # Must set these before calling parent's __init__() so that the data_file
        #   property will have the proper member vars.
        self.service_id = service_id
        self.wallet = wallet

        super().__init__(wallet.manager.data_folder)

        if "addrs" not in self.data:
            self.data["addrs"] = {}

        if "txs" not in self.data:
            self.data["txs"] = {}

    @property
    def data_file(self):
        # TODO: currently saving in the wallets/ dir but not in the main vs regtest subdir
        return os.path.join(
            self.wallet.manager.data_folder,
            f"{self.wallet.alias}_{self.service_id}.json",
        )

    def save(self):
        # Expose for external use
        self._save()

    def set_addr_annotations(self, addr: str, annotations: dict, autosave: bool = True):
        self.data["addrs"][addr] = annotations
        if autosave:
            self._save()

    def remove_addr_annotations(self, addr: str, autosave: bool = True):
        self.data["addrs"].pop(addr, None)
        if autosave:
            self._save()

    def get_addr_annotations(self, addr: str):
        return self.data["addrs"].get(addr, None)

    def get_all_addr_annotations(self):
        return self.data["addrs"]

    def set_tx_annotations(self, txid: str, annotations: dict, autosave: bool = True):
        self.data["txs"][txid] = annotations
        if autosave:
            self._save()

    def get_tx_annotations(self, txid: str):
        return self.data["txs"].get(txid, None)

    def get_all_tx_annotations(self):
        return self.data["txs"]
