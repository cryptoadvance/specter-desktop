import pytest
from cryptoadvance.specter.util.mnemonic import *


def test_initialize_mnemonic(caplog):
    mnemo_en = initialize_mnemonic("en")
    assert isinstance(mnemo_en, Mnemonic)
    assert mnemo_en.language == "english"
    mnemo_es = initialize_mnemonic("es")
    assert mnemo_es.language == "spanish"
    mnemo_undefined = initialize_mnemonic("gu")
    # Default to English if language code is undefined
    assert mnemo_undefined.language == "english"


def test_detect_language(caplog):
    assert (
        Mnemonic.detect_language(
            "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )
        == "english"
    )
    assert (
        Mnemonic.detect_language(
            "ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso madera"
        )
        == "spanish"
    )


def test_generate_mnemonic():
    # returns an English wordlist as long string like:
    "tomorrow question cook lend burden bone own junior stage square leaf father edge decrease pipe tired useful junior calm silver topple require rug clock"

    assert len(generate_mnemonic(strength=128).split(" ")) == 12
    assert len(generate_mnemonic(strength=256).split(" ")) == 24

    # Who needs those?
    assert len(generate_mnemonic(strength=160).split(" ")) == 15
    # 192 and 224 is also possible


def test_validate_mnemonic():
    assert validate_mnemonic(
        "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
    )

    # Spanish equivalent to the ghost machine
    assert validate_mnemonic(
        "ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso madera"
    )

    with pytest.raises(SpecterError, match="Language not detected") as se:
        validate_mnemonic(
            "muh ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )
