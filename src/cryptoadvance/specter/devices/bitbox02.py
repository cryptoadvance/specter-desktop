from .hwi_device import HWIDevice


class BitBox02(HWIDevice):
    device_type = "bitbox02"
    name = "BitBox02"
    icon = "img/devices/bitbox02_icon.svg"
    supports_hwi_multisig_display_address = True

    @classmethod
    def get_client(cls, *args, **kwargs):
        # Convert args tuple to a list to modify it
        args_list = list(args)

        if args_list[1] == "":  # passphrase
            # prevent this error-message raised from hwilib since about 2.2.1:
            # "Internal error: The BitBox02 does not accept a passphrase from the host. Please enable the passphrase option and enter the passphrase on the device during unlock."
            # IMHO hwilib should treat "" same as none but it does not
            args_list[1] = None
        return super().get_client(*args_list, **kwargs)
