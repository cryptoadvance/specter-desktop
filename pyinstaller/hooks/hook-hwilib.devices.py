from hwilib.devices import __all__

hiddenimports = []
for d in __all__:
    hiddenimports.append("hwilib.devices." + d)
