import pytest
from cryptoadvance.specter.util.mnemonic import *

ghost_machine = (
    "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
)
ganso_madera = (
    "ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso madera"
)
exulter_ivoire = "exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter ivoire"

gravoso_mummia = "gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso mummia"


def test_initialize_mnemonic(caplog):
    mnemo_en = initialize_mnemonic("en")
    assert isinstance(mnemo_en, Mnemonic)
    assert mnemo_en.language == "english"
    mnemo_es = initialize_mnemonic("es")
    assert mnemo_es.language == "spanish"
    mnemo_undefined = initialize_mnemonic("gu")
    # Defaults to English if language code is undefined
    assert mnemo_undefined.language == "english"
    mnemo_fr = initialize_mnemonic("fr")
    # TODO: Change when language detection works better upstream (https://github.com/trezor/python-mnemonic/issues/98)
    assert mnemo_fr.language == "english"


def test_detect_language(caplog):
    assert Mnemonic.detect_language(ghost_machine) == "english"
    assert Mnemonic.detect_language(ganso_madera) == "spanish"
    assert Mnemonic.detect_language(exulter_ivoire) == "french"
    assert Mnemonic.detect_language(gravoso_mummia) == "italian"


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
    # assert validate_mnemonic(exulter_ivoire) TODO: Change in the future
    assert validate_mnemonic(gravoso_mummia)

    with pytest.raises(SpecterError, match="Language not detected") as se:
        validate_mnemonic(
            "muh ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )
    with pytest.raises(
        SpecterError, match="The language French is not supported"
    ) as se:  # TODO: Change in the future
        validate_mnemonic(exulter_ivoire)


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
    root_gravoso_mummia = mnemonic_to_root(gravoso_mummia, passphrase="")
    assert (
        root_gravoso_mummia.to_string()
        == "xprv9s21ZrQH143K33VMWAAXEnZ6Sps5XB3YJxLsoDYUeb2Q3TFQdw2ZHF5BRoGA7aojGAyFk9D3EsWFneTN9JeZYo3tmigKkcWyTirRZGxmbB2"
    )


def test_duplicates_in_wordlists():
    mnemo_en = initialize_mnemonic("en")
    mnemo_es = initialize_mnemonic("es")
    mnemo_it = initialize_mnemonic("it")

    wordlist_en = mnemo_en.wordlist
    wordlist_es = mnemo_es.wordlist
    wordlist_it = mnemo_it.wordlist

    # Check that there are no overlaps in the available wordlists
    # (There is an overlap of 100 words between the English and the French wordlists)
    # EN-IT
    assert len([word for word in wordlist_en if word in wordlist_it]) == 0
    # EN-ES
    assert len([word for word in wordlist_en if word in wordlist_es]) == 0
    # ES-IT
    assert len([word for word in wordlist_es if word in wordlist_it]) == 0
