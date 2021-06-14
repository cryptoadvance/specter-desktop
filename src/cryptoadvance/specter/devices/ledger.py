from .hwi_device import HWIDevice


class Ledger(HWIDevice):
    device_type = "ledger"
    name = "Ledger"
    icon = "ledger_icon.svg"

    def __init__(self, name, alias, keys, blinding_key, fullpath, manager):
        HWIDevice.__init__(self, name, alias, keys, blinding_key, fullpath, manager)

    def create_psbts(self, base64_psbt, wallet):
        return {"hwi": wallet.fill_psbt(base64_psbt, non_witness=False)}
