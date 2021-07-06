from ..txlist import *
from embit.liquid.transaction import LTransaction


class LTxItem(TxItem):
    TransactionCls = LTransaction


class LTxList(TxList):
    ItemCls = LTxItem
    counter = 0

    def add(self, txs):
        print(self)
        super().add(*args, **kwargs)

    def decoderawtransaction(self, txhex):
        res = self.rpc.decoderawtransaction(txhex)
        self.counter += 1
        if self.counter > 20:
            raise RuntimeError()
        return res
