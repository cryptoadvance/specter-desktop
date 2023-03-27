from .txlist import TxList


class AbstractWallet:
    @property
    def transactions(self) -> TxList:
        if hasattr(self, "_transactions"):
            return self._transactions
        else:
            return None

    @property
    def addresses(self) -> TxList:
        if hasattr(self, "_addresses"):
            return self._addresses
        else:
            return None

    @property
    # abstractmethod
    def rpc(self):
        """Cache RPC instance. Reuse if manager's RPC instance hasn't changed. Create new RPC instance otherwise.
        This RPC instance is also used by objects created by the wallet, such as TxList or TxItem
        """
        pass
