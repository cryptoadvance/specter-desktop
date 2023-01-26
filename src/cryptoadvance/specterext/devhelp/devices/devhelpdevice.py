""" This Device is not a real device but just something to demonstrate the creation of devices in extensions
"""

from cryptoadvance.specter.devices.hwi_device import HWIDevice


class DevhelpDevice(HWIDevice):
    device_type = "devhelpdevice"
    name = "DevHelpDevice"
    icon = "devhelp/img/mydevice-logo.svg"
    supports_hwi_multisig_display_address = True
