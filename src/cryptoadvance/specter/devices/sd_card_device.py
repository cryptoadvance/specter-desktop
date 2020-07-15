from .hwi_device import HWIDevice

class SDCardDevice(HWIDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        HWIDevice.__init__(self, name, alias, device_type, keys, fullpath, manager)
        self.sd_card_support = True
        self.exportable_to_wallet = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        psbts['sdcard'] = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=True)
        return psbts
