from cryptoadvance.specter.util.descriptor import *
from embit import bip32, ec, networks, script
from cryptoadvance.specter.util.xpub import hash160
from cryptoadvance.specter.util.base58 import *
import pytest


### Tests of additional descriptor functionality in Specter


def test_derive_pubkey():
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


### Tests based on  https://github.com/bitcoin-core/HWI/blob/1b1596ac6f4fb1ce47a0d1ca7feb1fc553d08e09/test/test_descriptor.py


def test_parse_descriptor_with_origin():
    desc = Descriptor.parse(
        "wpkh([00000001/84'/1'/0']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)",
        True,
    )
    assert desc is not None
    assert desc.wpkh == True
    assert desc.sh_wpkh == None
    assert desc.origin_fingerprint == "00000001"
    assert desc.origin_path == "/84'/1'/0'"
    assert (
        desc.base_key
        == "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B"
    )
    assert desc.path_suffix == "/0/0"
    assert desc.testnet == True
    assert desc.m_path_base == "m/84'/1'/0'"
    assert desc.m_path == "m/84'/1'/0'/0/0"


def test_parse_multisig_descriptor_with_origin():
    desc = Descriptor.parse(
        "wsh(multi(2,[00000001/48'/1'/0'/2']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0,[00000002/48'/0'/0'/2']tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty/0/0))",
        True,
    )
    assert desc is not None
    assert desc.wsh == True
    assert desc.origin_fingerprint == ["00000001", "00000002"]
    assert desc.origin_path == ["/48'/0'/0'/2'", "/48'/0'/0'/2'"]
    assert desc.base_key == [
        "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B",
        "tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty",
    ]
    assert desc.path_suffix == ["/0/0", "/0/0"]
    assert desc.testnet == True
    assert desc.m_path_base == ["m/48'/0'/0'/2'", "m/48'/0'/0'/2'"]
    assert desc.m_path == ["m/48'/0'/0'/2'/0/0", "m/48'/0'/0'/2'/0/0"]


def test_parse_descriptor_without_origin():
    desc = Descriptor.parse(
        "wpkh(tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)",
        True,
    )
    assert desc is not None
    assert desc.wpkh == True
    assert desc.sh_wpkh == None
    assert desc.origin_fingerprint == None
    assert desc.origin_path == None
    assert (
        desc.base_key
        == "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B"
    )
    assert desc.path_suffix == "/0/0"
    assert desc.testnet == True
    assert desc.m_path == None


def test_parse_descriptor_with_origin_fingerprint_only():
    desc = Descriptor.parse(
        "wpkh([00000001]tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)",
        True,
    )
    assert desc is not None
    assert desc.wpkh == True
    assert desc.sh_wpkh == None
    assert desc.origin_fingerprint == "00000001"
    assert desc.origin_path == ""
    assert (
        desc.base_key
        == "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B"
    )
    assert desc.path_suffix == "/0/0"
    assert desc.testnet == True
    assert desc.m_path == None


def test_parse_descriptor_with_key_at_end_with_origin():
    desc = Descriptor.parse(
        "wpkh([00000001/84'/1'/0'/0/0]0297dc3f4420402e01a113984311bf4a1b8de376cac0bdcfaf1b3ac81f13433c7)",
        True,
    )
    assert desc is not None
    assert desc.wpkh == True
    assert desc.sh_wpkh == None
    assert desc.origin_fingerprint == "00000001"
    assert desc.origin_path == "/84'/1'/0'/0/0"
    assert (
        desc.base_key
        == "0297dc3f4420402e01a113984311bf4a1b8de376cac0bdcfaf1b3ac81f13433c7"
    )
    assert desc.path_suffix == None
    assert desc.testnet == True
    assert desc.m_path == "m/84'/1'/0'/0/0"


def test_parse_descriptor_with_key_at_end_without_origin():
    desc = Descriptor.parse(
        "wpkh(0297dc3f4420402e01a113984311bf4a1b8de376cac0bdcfaf1b3ac81f13433c7)", True
    )
    assert desc is not None
    assert desc.wpkh == True
    assert desc.sh_wpkh == None
    assert desc.origin_fingerprint == None
    assert desc.origin_path == None
    assert (
        desc.base_key
        == "0297dc3f4420402e01a113984311bf4a1b8de376cac0bdcfaf1b3ac81f13433c7"
    )
    assert desc.path_suffix == None
    assert desc.testnet == True
    assert desc.m_path == None


def test_parse_empty_descriptor():
    desc = Descriptor.parse("", True)
    assert desc is None


def test_parse_descriptor_replace_h():
    desc = Descriptor.parse(
        "wpkh([00000001/84h/1h/0']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)",
        True,
    )
    assert desc is not None
    assert desc.origin_path == "/84'/1'/0'"


def test_serialize_descriptor_with_origin():
    descriptor = "wpkh([00000001/84'/1'/0']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)#mz20k55p"
    desc = Descriptor.parse(descriptor, True)
    assert desc.serialize() == descriptor


def test_serialize_descriptor_without_origin():
    descriptor = "wpkh(tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0)#ac0p4yhq"
    desc = Descriptor.parse(descriptor, True)
    assert desc.serialize() == descriptor


def test_serialize_descriptor_with_key_at_end_with_origin():
    descriptor = "wpkh([00000001/84'/1'/0'/0/0]0297dc3f4420402e01a113984311bf4a1b8de376cac0bdcfaf1b3ac81f13433c7)#rh7p6vk2"
    desc = Descriptor.parse(descriptor, True)
    assert desc.serialize() == descriptor


# def test_checksums():
# # Check sum check only returns None currently if sth. is wrong with the checksum
# # Need to run pytest --capture=no here to see the print statements
#     with pytest.raises(Exception) as e:
#         assert Descriptor.parse("sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#") is not None
#     assert e.type is AssertionError
#     print("Passes because AssertionError as expected.")


def test_checksums(subtests):
    # Check sum check currently only returns None (no more concrete error raised) if sth. is wrong with the checksum
    with subtests.test(msg="Valid checksum or no checksum"):
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggrsrxfy"
            )
            is not None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5t"
            )
            is not None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))"
            )
            is not None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))"
            )
            is not None
        )
    with subtests.test(msg="Empty checksum"):
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#"
            )
            is None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#"
            )
            is None
        )
    with subtests.test(msg="Too long checksum"):
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggrsrxfyq"
            )
            is None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5tq"
            )
            is None
        )
    with subtests.test(msg="Too short checksum"):
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggrsrxf"
            )
            is None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5"
            )
            is None
        )
    with subtests.test(msg="Error in payload"):
        assert (
            Descriptor.parse(
                "sh(multi(3,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggrsrxfy"
            )
            is None
        )
        assert (
            Descriptor.parse(
                "sh(multi(3,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5t"
            )
            is None
        )
    with subtests.test(msg="Error in checksum"):
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggssrxfy"
            )
            is None
        )
        assert (
            Descriptor.parse(
                "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjq09x4t"
            )
            is None
        )
