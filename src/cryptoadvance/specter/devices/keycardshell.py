from .keystone import Keystone

class KeycardShell(Keystone):
    device_type = "keycardshell"
    name = "Keycard Shell"
    icon = "img/devices/keycardshell_icon.svg"
    exportable_to_wallet = False
    sd_card_support = False
    taproot_support = False

    def export_wallet(self, wallet):
        if not wallet.is_multisig:
            return None
