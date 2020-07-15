from .hwi_device import HWIDevice

class Trezor(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, 'trezor', keys, fullpath, manager)
        self.sd_card_support = False
        self.qr_code_support = False
        self.supports_hwi_toggle_passphrase = True
        self.supports_hwi_multisig_display_address = True