from cryptoadvance.specter.util.seedqr import (
    parse_standard_seedqr,
    parse_compact_seedqr,
)
import pytest
from cryptoadvance.specter.specter_error import SpecterError


### Based on test vectors from https://github.com/SeedSigner/seedsigner/blob/dev/docs/seed_qr/README.md#test-seedqrs


def test_parse_standard_seedqr():
    digitstream = "011513251154012711900771041507421289190620080870026613431420201617920614089619290300152408010643"
    assert parse_standard_seedqr(digitstream) == (
        [
            "attack",
            "pizza",
            "motion",
            "avocado",
            "network",
            "gather",
            "crop",
            "fresh",
            "patrol",
            "unusual",
            "wild",
            "holiday",
            "candy",
            "pony",
            "ranch",
            "winter",
            "theme",
            "error",
            "hybrid",
            "van",
            "cereal",
            "salon",
            "goddess",
            "expire",
        ]
    )
    digitstream = "011416550964188800731119157218870156061002561932122514430573003611011405110613292018175411971576"
    assert parse_standard_seedqr(digitstream) == (
        [
            "atom",
            "solve",
            "joy",
            "ugly",
            "ankle",
            "message",
            "setup",
            "typical",
            "bean",
            "era",
            "cactus",
            "various",
            "odor",
            "refuse",
            "element",
            "afraid",
            "meadow",
            "quick",
            "medal",
            "plate",
            "wisdom",
            "swap",
            "noble",
            "shallow",
        ]
    )
    digitstream = "073318950739065415961602009907670428187212261116"
    assert parse_standard_seedqr(digitstream) == (
        [
            "forum",
            "undo",
            "fragile",
            "fade",
            "shy",
            "sign",
            "arrest",
            "garment",
            "culture",
            "tube",
            "off",
            "merit",
        ]
    )
    # With one 4-digit above 2047 (first one is 3333)
    digitstream = "333313251154012711900771041507421289190620080870026613431420201617920614089619290300152408010643"
    with pytest.raises(
        SpecterError,
        match="One of the words in the mnemonic was not correctly encoded as 4-digit number.",
    ):
        assert parse_standard_seedqr(digitstream)


def test_parse_compact_seedqr():
    bytestream = b"\x0et\xb6A\x07\xf9L\xc0\xcc\xfa\xe6\xa1=\xcb\xec6b\x15O\xecg\xe0\xe0\t\x99\xc0x\x92Y}\x19\n"
    assert (
        parse_compact_seedqr(bytestream)
        == "attack pizza motion avocado network gather crop fresh patrol unusual wild holiday candy pony ranch winter theme error hybrid van cereal salon goddess expire"
    )

    bytestream = b"\x0eY\xdd\xe2v\x00\x93\x17\xf1'_\x13\x89\x88\x80x\xc9\x93h\xd1\xe8$\x89\xb5\xf6)S\x1f\xc5\xb6\xa5n"
    assert (
        parse_compact_seedqr(bytestream)
        == "atom solve joy ugly ankle message setup typical bean era cactus various odor refuse element afraid meadow quick medal plate wisdom swap noble shallow"
    )

    bytestream = b"[\xbd\x9dq\xa8\xecy\x90\x83\x1a\xff5\x9dBeE"
    assert (
        parse_compact_seedqr(bytestream)
        == "forum undo fragile fade shy sign arrest garment culture tube off merit"
    )
