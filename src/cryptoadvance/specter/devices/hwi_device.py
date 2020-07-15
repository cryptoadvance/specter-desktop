from ..device import Device

class HWIDevice(Device):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        Device.__init__(self, name, alias, device_type, keys, fullpath, manager)
        self.hwi_support = True
        self.exportable_to_wallet = False

    def create_psbts(self, base64_psbt, wallet):
        return { 'hwi': wallet.fill_psbt(base64_psbt) }
