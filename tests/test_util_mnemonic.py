import pytest
from cryptoadvance.specter.util.mnemonic import *

ghost_machine = (
    "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
)
ganso_madera = (
    "ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso madera"
)
exulter_ivoire = "exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter ivoire"


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
    assert Mnemonic.detect_language(ghost_machine) == "english"
    assert Mnemonic.detect_language(ganso_madera) == "spanish"
    assert Mnemonic.detect_language(exulter_ivoire) == "french"


def test_generate_mnemonic():
    # returns an English wordlist as long string like:
    "tomorrow question cook lend burden bone own junior stage square leaf father edge decrease pipe tired useful junior calm silver topple require rug clock"

    assert len(generate_mnemonic(strength=128).split(" ")) == 12
    assert len(generate_mnemonic(strength=256).split(" ")) == 24

    # Who needs those?
    assert len(generate_mnemonic(strength=160).split(" ")) == 15
    # 192 and 224 is also possible


def test_validate_mnemonic():
    assert validate_mnemonic(ghost_machine)
    assert validate_mnemonic(ganso_madera)
    assert validate_mnemonic(exulter_ivoire)

    with pytest.raises(SpecterError, match="Language not detected") as se:
        validate_mnemonic(
            "muh ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )


def test_mnemonic_to_root():
    # BIP32 root keys from iancoleman
    root_ghost_machine = mnemonic_to_root(ghost_machine, passphrase="")
    assert (
        root_ghost_machine.to_string()
        == "xprv9s21ZrQH143K3cTKa3Bs6BJHTe9CrpeynNGA5z4SMsqMawSmfvfv4z8JChkbHgM8BWzvUxMACHTE3NwihzPZRcdQcJ4N7FTbj52UdsxkMDh"
    )
    root_ganso_madera = mnemonic_to_root(ganso_madera, passphrase="")
    assert (
        root_ganso_madera.to_string()
        == "xprv9s21ZrQH143K2VDXXVUMLDUEzqVhiPsTAmammLqoFKrQSPgUtg388VxyoT1mkJRZxUNvHhCjFgVGYmfaUpd55tGRvdTQJY6aTTsZzHcDBCa"
    )
    root_exulter_ivoire = mnemonic_to_root(exulter_ivoire, passphrase="")
    assert (
        root_exulter_ivoire.to_string()
        == "xprv9s21ZrQH143K4Jc59ZMcfPASgm9Pw1HhepftnsfZnFT7u31CpsMi5evhLskDCWh5kL4SzFvQZ7oaZKv5sRuGicGz4w8dTH6FzLy2eEGJ7Ph"
    )
