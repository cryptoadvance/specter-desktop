from cryptoadvance.specter.util.descriptor import *
from embit import bip32, ec, networks, script
from cryptoadvance.specter.util.xpub import hash160
from cryptoadvance.specter.util.base58 import *
import pytest


### Tests based on https://github.com/bitcoin-core/HWI/blob/1b1596ac6f4fb1ce47a0d1ca7feb1fc553d08e09/test/test_descriptor.py


def test_parse_descriptor_with_origin():
    desc: Descriptor = Descriptor.parse(
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
    assert desc.address_type == "wpkh"
    assert type(desc.derive(1)) == Descriptor


def test_parse_multisig_descriptor_with_origin():
    # achow101 uses 48'/0'/0'/2' which isn't testnet, though
    desc = Descriptor.parse(
        "wsh(multi(2,[00000001/48'/1'/0'/2']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0,[00000002/48'/1'/0'/2']tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty/0/0))",
        True,
    )
    assert desc is not None
    assert desc.wsh == True
    assert desc.origin_fingerprint == ["00000001", "00000002"]
    assert desc.origin_path == ["/48'/1'/0'/2'", "/48'/1'/0'/2'"]
    assert desc.base_key == [
        "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B",
        "tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty",
    ]
    assert desc.path_suffix == ["/0/0", "/0/0"]
    assert desc.testnet == True
    assert desc.m_path_base == ["m/48'/1'/0'/2'", "m/48'/1'/0'/2'"]
    assert desc.m_path == ["m/48'/1'/0'/2'/0/0", "m/48'/1'/0'/2'/0/0"]


def test_parse_multisig_descriptor_with_origin_one_lacking():
    desc = Descriptor.parse(
        "wsh(multi(2,[00000001/48'/1'/0'/2']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0,tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty/0/0))",
        True,
    )
    assert desc is not None
    assert desc.wsh == True
    assert desc.origin_fingerprint == ["00000001", None]
    assert desc.origin_path == ["/48'/1'/0'/2'", None]
    assert desc.base_key == [
        "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B",
        "tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty",
    ]
    assert desc.path_suffix == ["/0/0", "/0/0"]
    assert desc.testnet == True
    assert desc.m_path_base == ["m/48'/1'/0'/2'", None]
    assert desc.m_path == ["m/48'/1'/0'/2'/0/0", None]


def test_parse_multisig_descriptor_with_origin_nested():
    desc = Descriptor.parse(
        "sh(wsh(multi(2,[00000001/48'/1'/0'/1']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/0/0,[00000002/48'/1'/0'/1']tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty/0/0)))",
        True,
    )
    assert desc is not None
    assert desc.wsh == None
    assert desc.sh_wsh == True
    assert desc.origin_fingerprint == ["00000001", "00000002"]
    assert desc.origin_path == ["/48'/1'/0'/1'", "/48'/1'/0'/1'"]
    assert desc.base_key == [
        "tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B",
        "tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty",
    ]
    assert desc.path_suffix == ["/0/0", "/0/0"]
    assert desc.testnet == True
    assert desc.m_path_base == ["m/48'/1'/0'/1'", "m/48'/1'/0'/1'"]
    assert desc.m_path == ["m/48'/1'/0'/1'/0/0", "m/48'/1'/0'/1'/0/0"]


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


def test_parse_descriptor_multi_error():
    with pytest.raises(SpecterError) as excinfo:
        Descriptor.parse(
            "wsh(multi(3,[00000001/48'/1'/0'/2']tpubD6NzVbkrYhZ4WaWSyoBvQwbpLkojyoTZPRsgXELWz3Popb3qkjcJyJUGLnL4qHHoQvao8ESaAstxYSnhyswJ76uZPStJRJCTKvosUCJZL5B/*,[00000002/48'/1'/0'/2']tpubDFHiBJDeNvqPWNJbzzxqDVXmJZoNn2GEtoVcFhMjXipQiorGUmps3e5ieDGbRrBPTFTh9TXEKJCwbAGW9uZnfrVPbMxxbFohuFzfT6VThty/0/0))"
        )
    assert (
        str(excinfo.value)
        == "Multisig threshold cannot be larger than the number of keys. Threshold is 3 but only 2 keys specified."
    )


def test_checksums():
    # Correct checksum
    descriptor_ex_checksum = "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))"
    assert DescriptorChecksum(descriptor_ex_checksum) == "tjg09x5t"

    # Empty checksum
    with pytest.raises(SpecterError) as excinfo:
        Descriptor.parse(
            "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#"
        )
    assert str(excinfo.value) == "Checksum is empty."

    # Checksum too long
    with pytest.raises(SpecterError) as excinfo:
        Descriptor.parse(
            "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5tq"
        )
    assert (
        str(excinfo.value)
        == "Checksum tjg09x5tq doesn't have the correct length. Should be 8 characters not 9."
    )

    # Checksum too short
    with pytest.raises(SpecterError) as excinfo:
        Descriptor.parse(
            "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5"
        )
    assert (
        str(excinfo.value)
        == "Checksum tjg09x5 doesn't have the correct length. Should be 8 characters not 7."
    )

    # Error in checksum
    with pytest.raises(SpecterError) as excinfo:
        Descriptor.parse(
            "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjq09x4t"
        )
    assert str(excinfo.value) == "tjq09x4t is the wrong checkum should be tjg09x5t."


### Tests of additional descriptor functionality in Specter


def test_derive_regtest():
    # Using ghost x 11 + machine (1)
    # abandon x 11 + about (2)
    # and zoo x 11 + wrong (3)
    # /48'/1'/0'/1'
    # Using iancoleman to get tpubs

    desc = Descriptor.parse(
        "sh(wsh(sortedmulti(2,tpubDDzWqfZ5TH4819JtJT1MaJGh2FYnbn2KGoqkznXRFdNZAuKLD2CsYtQiV5rEVCUezzz9GaRkeHct5NSxVEG9KWUaRoeEtcafVHr2SVE5DRN/*,tpubDFH9dgzveyD8yHQb8VrpG8FYAuwcLMHMje2CCcbBo1FpaGzYVtJeYYxcYgRqSTta5utUFts8nPPHs9C2bqoxrey5jia6Dwf9mpwrPq7YvcJ/*,tpubDFPtPArj4GzBBcuqDySkeQbKx4r6HwRgcPbbAjbjB5cxYRzJT6iFtiqzce4qQ9XFWZ83DZJ43WCJJsotdG75p7pw4SgUHZ2nkG4YxLQ414i/2)))",
        True,
    )

    assert (
        desc.derive(1).serialize()
        == "sh(wsh(sortedmulti(2,03407a711574ae73aa5824f5a66bf4f9a9f49dd274407eb4c27d996019cf4a6552,0376166abb71efb6c9a497a64c1b24c484c29b8a4219a526737e1f370768b1bbe8,03a1427c178f0b1cd679464c4c90444bcfd775d5edb89cf33828170e8be008d921)))#j54e69dq"
    )
    # pubkeys cross-checked with iancoleman

    assert desc.address(5) == "2NGamwat67EUkABbkY1HLYjQW3oumUcThnV"
    # Verified with bitcoin-cli deriveaddresses

    assert (
        desc.derive(1, keep_xpubs=True).serialize()
        == "sh(wsh(sortedmulti(2,tpubDFPtPArj4GzBBcuqDySkeQbKx4r6HwRgcPbbAjbjB5cxYRzJT6iFtiqzce4qQ9XFWZ83DZJ43WCJJsotdG75p7pw4SgUHZ2nkG4YxLQ414i/2,tpubDFH9dgzveyD8yHQb8VrpG8FYAuwcLMHMje2CCcbBo1FpaGzYVtJeYYxcYgRqSTta5utUFts8nPPHs9C2bqoxrey5jia6Dwf9mpwrPq7YvcJ/1,tpubDDzWqfZ5TH4819JtJT1MaJGh2FYnbn2KGoqkznXRFdNZAuKLD2CsYtQiV5rEVCUezzz9GaRkeHct5NSxVEG9KWUaRoeEtcafVHr2SVE5DRN/1)))#3mfhjamz"
    )


def test_derive_main():
    # Using ghost x 11 + machine (1)
    # abandon x 11 + about (2)
    # and zoo x 11 + wrong (3)
    # /48'/0'/0'/1'
    # Using iancoleman to get xpubs

    desc = Descriptor.parse(
        "sh(wsh(sortedmulti(2,xpub6DiXipxEgSYqTw3xX2apub7vzsC5gBzmikxriTRnfKRKQjUSpiGQ9XzyFktkVLTGVGF5emH8up1qtsyw726rvnmzHRU8cHH8gDxeLMXSkYE/*,xpub6DkFAXWQ2dHxnMKoSBogHrw1rgNJKR4umdbnNVNTYeCGcduxWnNUHgGptqEQWPKRmeW4Zn4FHSbLMBKEWYaMDYu47Ytg6DdFnPNt8hwn5mE/*,xpub6FHZCoNb3tg3mxjcXsQx1xLpNmod6woECf2fB4nQbe9NXbvha2ucpDpnGbTFF68KUMUr1hNQ9E5jVEvpT2kUkVmFVDrJawcbgXzDpJc2hkF/2)))",
        True,
    )

    assert (
        desc.derive(1).serialize()
        == "sh(wsh(sortedmulti(2,029dfee2aaa23e2220476c34eda9a76591c1257f8dfce54e42ff014f922ede0838,03151d5b21c6491915e7a103bff913b4d85246c8209a342bb7104850e4cb394686,03646d8e624fedb63739e7963d0c7ad368a7f7935557b2b28c4c954882b19fe6e1)))#rzmdthwy"
    )
    # pubkeys cross-checked with iancoleman

    assert desc.address(5, "main") == "388fc825v9R6Ev8BKodXQMFumQRe7C8SZ5"
    # Verified with bitcoin-cli deriveaddresses

    assert (
        desc.derive(1, keep_xpubs=True).serialize()
        == "sh(wsh(sortedmulti(2,xpub6DkFAXWQ2dHxnMKoSBogHrw1rgNJKR4umdbnNVNTYeCGcduxWnNUHgGptqEQWPKRmeW4Zn4FHSbLMBKEWYaMDYu47Ytg6DdFnPNt8hwn5mE/1,xpub6DiXipxEgSYqTw3xX2apub7vzsC5gBzmikxriTRnfKRKQjUSpiGQ9XzyFktkVLTGVGF5emH8up1qtsyw726rvnmzHRU8cHH8gDxeLMXSkYE/1,xpub6FHZCoNb3tg3mxjcXsQx1xLpNmod6woECf2fB4nQbe9NXbvha2ucpDpnGbTFF68KUMUr1hNQ9E5jVEvpT2kUkVmFVDrJawcbgXzDpJc2hkF/2)))#mgjhd0rk"
    )


def test_sort():
    descriptor = "sh(wsh(multi(2,tpubDDzWqfZ5TH4819JtJT1MaJGh2FYnbn2KGoqkznXRFdNZAuKLD2CsYtQiV5rEVCUezzz9GaRkeHct5NSxVEG9KWUaRoeEtcafVHr2SVE5DRN/*,tpubDFH9dgzveyD8yHQb8VrpG8FYAuwcLMHMje2CCcbBo1FpaGzYVtJeYYxcYgRqSTta5utUFts8nPPHs9C2bqoxrey5jia6Dwf9mpwrPq7YvcJ/*,tpubDFPtPArj4GzBBcuqDySkeQbKx4r6HwRgcPbbAjbjB5cxYRzJT6iFtiqzce4qQ9XFWZ83DZJ43WCJJsotdG75p7pw4SgUHZ2nkG4YxLQ414i/2)))"
    assert (
        sort_descriptor(descriptor, 1)
        == "sh(wsh(multi(2,tpubDFPtPArj4GzBBcuqDySkeQbKx4r6HwRgcPbbAjbjB5cxYRzJT6iFtiqzce4qQ9XFWZ83DZJ43WCJJsotdG75p7pw4SgUHZ2nkG4YxLQ414i/2,tpubDFH9dgzveyD8yHQb8VrpG8FYAuwcLMHMje2CCcbBo1FpaGzYVtJeYYxcYgRqSTta5utUFts8nPPHs9C2bqoxrey5jia6Dwf9mpwrPq7YvcJ/1,tpubDDzWqfZ5TH4819JtJT1MaJGh2FYnbn2KGoqkznXRFdNZAuKLD2CsYtQiV5rEVCUezzz9GaRkeHct5NSxVEG9KWUaRoeEtcafVHr2SVE5DRN/1)))#w5qd99tr"
    )
