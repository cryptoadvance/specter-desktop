from ..txlist import *
from embit.liquid.transaction import LTransaction


class LTxItem(TxItem):
    TransactionCls = LTransaction


class LTxList(TxList):
    ItemCls = LTxItem
    counter = 0

    def decoderawtransaction(self, txhex):
        # TODO: using rpc for now, can be moved to utils
        return self.rpc.decoderawtransaction(txhex)
