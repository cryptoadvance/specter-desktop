from .bitcoin_core import BitcoinCore


class ElementsCore(BitcoinCore):
    device_type = "elementscore"
    name = "Elements Core (hot wallet)"
    icon = "elementscore_icon.svg"

    hot_wallet = True
    bitcoin_core_support = False
    liquid_support = True

    def __init__(self, name, alias, keys, fullpath, manager):
        BitcoinCore.__init__(self, name, alias, keys, fullpath, manager)
