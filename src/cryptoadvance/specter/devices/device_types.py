""" A list of static device_type strings. As Devices can, in the meantime, also be created
    in extensions, this file should be limited to device_type_strings which ARE referenced
    in core-code.
    ToDo:   Remove the strings which are only referenced in the corresponding-type.
            There is no point in doing that.
"""


class DeviceTypes:
    BITCOINCORE = "bitcoincore"
    BITCOINCORE_WATCHONLY = "bitcoincore_watchonly"
    ELEMENTSCORE = "elementscore"

    # All those ones are not treated any different in core-code and therefore should no
    # longer be referenced here:
    BITBOX02 = "bitbox02"
    COBO = "cobo"
    COLDCARD = "coldcard"
    GENERICDEVICE = "other"
    JADE = "jade"
    KEEPKEY = "keepkey"
    LEDGER = "ledger"
    SEEDSIGNER = "seedsigner"
    SPECTERDIY = "specter"
    TREZOR = "trezor"
    KEYSTONE = "keystone"
    PASSPORT = "passport"
