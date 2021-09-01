from .hwi_device import HWIDevice


class SDCardDevice(HWIDevice):

    sd_card_support = True
    exportable_to_wallet = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        psbts["sdcard"] = wallet.fill_psbt(base64_psbt, non_witness=True, xpubs=True)
        return psbts
