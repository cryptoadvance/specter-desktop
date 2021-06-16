from .cobo import Cobo


class Keystone(Cobo):
    device_type = "keystone"
    name = "Keystone"
    icon = "keystone_icon.svg"

    def create_psbts(self, base64_psbt, wallet):
        psbts = super().create_psbts(base64_psbt, wallet)
        # make sure nonwitness and xpubs are not there
        qr_psbt = wallet.fill_psbt(base64_psbt, non_witness=False, xpubs=False)
        # add a hint to <qr-code> tag that this should be encoded as crypto-psbt
        psbts["qrcode"] = f"crypto-psbt:{qr_psbt}"
        return psbts
