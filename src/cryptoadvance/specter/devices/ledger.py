from .hwi_device import HWIDevice


class Ledger(HWIDevice):
    device_type = "ledger"
    name = "Ledger"

    def __init__(self, name, alias, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = False
