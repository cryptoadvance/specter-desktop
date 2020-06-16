from .hwi_device import HWIDevice

class Ledger(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, 'ledger', keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = False
