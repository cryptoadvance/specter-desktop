# Adding Devices

Devices are the main building blocks for singlesig and multisig wallets. Different Hardwarewallets are represented as devices as well as the Bitcoin Core Hotwallet or the Electrum Wallet which might hold private keys and export xpubs into Specter Desktop.

To Create your own Device, you have to specify the modules containing subclasses of `Device` in `service.py`:

```
class DiceService(Service):
    # [...]
    devices = ["mynym.specterext.myextensionid.devices.mydevice"]
```

You don't have to place the device in that devices-subdirectory but that's recommended. Here is an example with some explanations:

```python
# [...]
from cryptoadvance.specter.device import Device

class MyDevice(Device):
    # the device_type is a string representation of this class which will be used in the
    # json-file of a device of that type. Simply use the class-name lowercase
    # and make sure it's unique
    device_type = "mydevice"
    # Will be shown when adding a new device and as a searchterm
    name = "Electrum"
    # The Icon. Use a b/w.svg
    icon = "electrum/img/devices/electrum_icon.svg"
    # optional, You might want to have a more specific template for creating a new device
    template = "electrum/device/new_device_keys_electrum.jinja"

    # If your device is a classic Hardwarewallets, it might have one of these features:
    sd_card_support = True
    qr_code_support = True

    # auto, off or on
    # seedsigner uses on. By default it's auto.
    qr_code_animate = "off"

```

For sure there might be various methods to overwrite. Please have a look into the `Device` class.