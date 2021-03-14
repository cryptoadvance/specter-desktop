from .coldcard import ColdCard
from .trezor import Trezor
from .ledger import Ledger

from .bitbox02 import BitBox02
from .keepkey import Keepkey
from .specter import Specter
from .cobo import Cobo
from .generic import GenericDevice
from .electrum import Electrum
from .bitcoin_core import BitcoinCore, BitcoinCoreWatchOnly

# all device types
__all__ = [
    Trezor,
    Ledger,
    BitBox02,
    Specter,
    ColdCard,
    Keepkey,
    Cobo,
    Electrum,
    BitcoinCore,
    BitcoinCoreWatchOnly,
    GenericDevice,
]


class DeviceTypes:
    BITBOX02 = "bitbox02"
    BITCOINCORE = "bitcoincore"
    BITCOINCORE_WATCHONLY = "bitcoincore_watchonly"
    COBO = "cobo"
    COLDCARD = "coldcard"
    ELECTRUM = "electrum"
    GENERICDEVICE = "other"
    KEEPKEY = "keepkey"
    SPECTER = "specter"
    TREZOR = "trezor"
