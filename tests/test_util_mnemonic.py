import pytest
from cryptoadvance.specter.util.mnemonic import *
from collections import Counter, defaultdict
from itertools import combinations

ghost_machine = (
    "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
)
ganso_madera = (
    "ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso ganso madera"
)
exulter_ivoire = "exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter exulter ivoire"

gravoso_mummia = "gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso gravoso mummia"

french = "cylindre corniche attentif boulon toboggan foudre bambin intrigue sélectif adverbe codifier neurone"

japanese = "ちほう そざい そんみん まもる いりょう ねだん たんとう きくばり つみき たんのう けんい なおす"

czech = "poryv troska mozol poledne louka levobok kuna lump korpus zvesela lyra kauce"

portuguese = "assador borbulha sorteio enguia castelo fanfarra vertente duplo legista aferir vazio apito"


def test_initialize_mnemonic(caplog):

    for key in MNEMONIC_LANGUAGES:
        mnemo = initialize_mnemonic(key)
        assert isinstance(mnemo, Mnemonic)
        assert mnemo.language == MNEMONIC_LANGUAGES[key]

    mnemo_undefined = initialize_mnemonic("gu")
    # Defaults to English if language code is undefined
    assert mnemo_undefined.language == "english"


def test_get_language():
    assert get_language(ghost_machine) == "english"
    assert get_language(ganso_madera) == "spanish"
    assert get_language(gravoso_mummia) == "italian"
    assert get_language(french) == "french"
    assert get_language(japanese) == "japanese"
    assert get_language(czech) == "czech"
    assert get_language(portuguese) == "portuguese"
    # This mnemonic created a problem on Cirrus, since "client" is part of the English and the French wordlists
    assert (
        get_language(
            "client sand bargain grace barely cheese warfare merge pigeon slice maple joy"
        )
        == "english"
    )
    with pytest.raises(SpecterError, match="Language unrecognized for") as se:
        get_language(
            "muh ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"
        )


def test_generate_mnemonic():
    assert len(generate_mnemonic(strength=128).split(" ")) == 12
    assert len(generate_mnemonic(strength=256).split(" ")) == 24
    assert len(generate_mnemonic(strength=160).split(" ")) == 15


def test_validate_mnemonic():
    assert validate_mnemonic(ghost_machine)
    assert validate_mnemonic(ganso_madera)
    assert validate_mnemonic(gravoso_mummia)


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
    root_gravoso_mummia = mnemonic_to_root(gravoso_mummia, passphrase="")
    assert (
        root_gravoso_mummia.to_string()
        == "xprv9s21ZrQH143K33VMWAAXEnZ6Sps5XB3YJxLsoDYUeb2Q3TFQdw2ZHF5BRoGA7aojGAyFk9D3EsWFneTN9JeZYo3tmigKkcWyTirRZGxmbB2"
    )


def count_multi_occurrence_languages(word_lists_dict):
    # Create a Counter to store occurrences of words across different lists
    word_counter = Counter()

    # Create a defaultdict to store the lists in which each word occurs
    word_lists_indices = defaultdict(list)

    # Iterate over each language and its corresponding word list
    for language, word_list in word_lists_dict.items():
        # Update the counter with the words from the current list
        word_counter.update(word_list)

        # Update the word_lists_indices with the lists in which each word occurs
        for word in set(word_list):
            word_lists_indices[word].append(language)

    # Filter words that occurred more than once across different lists
    multi_occurrence_languages = Counter()
    for word, count in word_counter.items():
        if count > 1:
            language_combinations = combinations(word_lists_indices[word], 2)
            multi_occurrence_languages.update(language_combinations)

    return multi_occurrence_languages


# There is an overlap of 100 words between the English and the French wordlists
# These are sanity checks that we don't have further overlaps
def test_duplicates_in_wordlists():

    word_lists_dict = dict()
    for key in MNEMONIC_LANGUAGES:
        mnemo = initialize_mnemonic(key)
        word_lists_dict[key] = mnemo.wordlist

    multi_occurrence_languages = count_multi_occurrence_languages(word_lists_dict)
    # only EN-FR should be here
    assert len(multi_occurrence_languages) == 1
