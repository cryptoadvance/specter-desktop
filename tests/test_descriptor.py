from cryptoadvance.specter.util.descriptor import *


def test_parse():
    descs = [
        "wpkh([5d5c5649/84h/1h/0h]tpubDCB5nE2GEEuX9xyFigt33xT1RidfkSsH2VSqDx93D1TrvghcZgoDBTjWnWwKTtA6DfvW7fKDAzPJoSduEbt1QkUW2YGaC2CgYxvmF9RyRZS/0/*)#ypamvruf",
        "sh(wpkh([5d5c5649/84h/1h/0h]tpubDCB5nE2GEEuX9xyFigt33xT1RidfkSsH2VSqDx93D1TrvghcZgoDBTjWnWwKTtA6DfvW7fKDAzPJoSduEbt1QkUW2YGaC2CgYxvmF9RyRZS/0/*))",
        "wsh(sortedmulti(2,[5d5c5649/48h/1h/0h/2h]tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/*,[0b9fb36b/48h/1h/0h/2h]tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/*))#2mdfgjf6",
        "sh(wsh(sortedmulti(2,[5d5c5649/48h/1h/0h/2h]tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/*,[0b9fb36b/48h/1h/0h/2h]tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/*)))",
        "sh(wsh(sortedmulti(2,tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/*,[0b9fb36b/48h/1h/0h/2h]tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/*,tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV,tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/10,03d568305d7ce6185f2512472bcad032a672626cf15dc2c6b5f68fdd2f3e5898ef)))",
    ]

    for desc in descs:
        d = Descriptor.parse(desc, True)


def test_derive():
    desc = "sh(wsh(sortedmulti(2,tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/*,[0b9fb36b/48h/1h/0h/2h]tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/*,tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV,tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/10,03d568305d7ce6185f2512472bcad032a672626cf15dc2c6b5f68fdd2f3e5898ef)))"
    d = Descriptor.parse(desc, True)
    assert (
        d.derive(1).serialize()
        == "sh(wsh(sortedmulti(2,[0b9fb36b/48'/1'/0'/2'/10]0249f0282636a8f3fac54a37387686705ddf717ab255cc18d4cc60fff284b8585c,[0b9fb36b/48'/1'/0'/2']02c0ca2aa23a2c83039437973d7eb44d15978900733569583103d03c705aa8383a,[0b9fb36b/48'/1'/0'/2'/0/1]036e5e49573aa861e10c3a01342bc7badcaf8acb88a02aaf4bdae46187260ca262,[0b9fb36b/48'/1'/0'/2']03d568305d7ce6185f2512472bcad032a672626cf15dc2c6b5f68fdd2f3e5898ef,03d7b53b60cbf4c0a9075d65911ce37f759d513f9ac3eca45752256f8aa2d82a9e)))#6n9weurx"
    )
    assert (
        d.derive(1, keep_xpubs=True).serialize()
        == "sh(wsh(sortedmulti(2,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/10,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/1,[0b9fb36b/48'/1'/0'/2']03d568305d7ce6185f2512472bcad032a672626cf15dc2c6b5f68fdd2f3e5898ef,tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/1)))#7r3s692f"
    )
    assert (
        sort_descriptor(desc, 11)
        == "sh(wsh(multi(2,tpubDEizCJr6sdiKWC6Be8b5EB7akzS7omSX8CHfAYNYewweRDzjmX2kgDAnig9RcVxqtcxdKuYQSKhkjHecYjyej22b7WThS8r1RBmY3Rfczb9/0/11,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/10,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV,[0b9fb36b/48'/1'/0'/2']tpubDEhAkijE6ovaiWkJpnGnLhW3VJSSbbQeAtRWQro8EaWgNarWFv2TumZ1sj4iBPReCufziRnnb9QSYSEE8tgZQbbaXJTdLtGtQgQTGXEJdfV/0/11,[0b9fb36b/48'/1'/0'/2']03d568305d7ce6185f2512472bcad032a672626cf15dc2c6b5f68fdd2f3e5898ef)))#sys0qqe8"
    )
    assert d.address(10) == "2N1TgzrzxjdgkWSuJLoNUtoLhZBJQSakRRk"
    assert d.address(10, "main") == "39uUw84w8BBQJfGkffkcGrMSLq6Ee4A2f7"
