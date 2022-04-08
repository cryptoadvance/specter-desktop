import pytest
from cryptoadvance.specter.util.mnemonic import *


def test_initialize_mnemonic(caplog):
    initialize_mnemonic("gu")


def test_generate_mnemonic():
    # returns an endlish wordlist as long string like:
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

    with pytest.raises(SpecterError, match="Language not detected") as se:
        validate_mnemonic(
            "muh ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )
