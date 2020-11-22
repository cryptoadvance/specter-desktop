from .hwi_device import HWIDevice

from .hwi import ledger


class Ledger(HWIDevice):
    device_type = "ledger"
    name = "Ledger"
    icon = "ledger_icon.svg"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        return {"hwi": wallet.fill_psbt(base64_psbt, non_witness=False)}

    @classmethod
    def get_client(cls, *args, **kwargs):
        return ledger.LedgerClient(*args, **kwargs)

    @classmethod
    def enumerate(cls, *args, **kwargs):
        return ledger.enumerate(*args, **kwargs)
