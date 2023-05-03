from .hwi_device import HWIDevice


class Keepkey(HWIDevice):
    device_type = "keepkey"
    name = "KeepKey"
    icon = "img/devices/keepkey_icon.svg"

    supports_hwi_toggle_passphrase = True
    supports_hwi_multisig_display_address = True
