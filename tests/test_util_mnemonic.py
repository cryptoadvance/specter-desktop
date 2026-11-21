import pytest
import unicodedata
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

# "abandon abandon ... about" with passphrase "pässword".
# Captured from the pre-NFKD Specter code path (embit, no normalization).
LEGACY_ROOT_XPRV = "xprv9s21ZrQH143K3U7U1GbZ9VyEBpAr68HX8WnsYC5qWv8wwA2XrrtaWDXUJh4t7rMHvtaeswQqbSxT5FdTzUQHym9StxbPAY4cUC8rz4btPpr"
# Same mnemonic and passphrase, normalized per BIP39 and cross-checked against
# the python-mnemonic reference implementation.
NFKD_ROOT_XPRV = "xprv9s21ZrQH143K4CD7VJ9DE5xYeKGUgxN8Hr94pJYcjrdLzFHUzTwjhzRDPfJM7towF42oZYmnvMppYC9jCwqpnjDmBkarrFwv2i1PtGuBNYC"


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


def test_default_seed_matches_bip39_reference_for_non_ascii_passphrase():
    """BIP39 requires NFKD normalization; the reference implementation agrees."""
    from mnemonic import Mnemonic

    phrase = "abandon " * 11 + "about"
    passphrase = "pässword"
    reference = Mnemonic("english").to_seed(phrase, passphrase=passphrase)
    assert mnemonic_to_seed(phrase, passphrase) == reference
    # NFKD is idempotent: an already decomposed passphrase derives the same seed.
    assert (
        mnemonic_to_seed(phrase, unicodedata.normalize("NFKD", passphrase)) == reference
    )


def test_default_root_is_nfkd_and_legacy_root_is_the_old_derivation():
    phrase = "abandon " * 11 + "about"
    passphrase = "pässword"
    assert mnemonic_to_root(phrase, passphrase).to_string() == NFKD_ROOT_XPRV
    assert (
        mnemonic_to_root(phrase, passphrase, legacy=True).to_string()
        == LEGACY_ROOT_XPRV
    )
    assert NFKD_ROOT_XPRV != LEGACY_ROOT_XPRV


def test_default_normalizes_precomposed_mnemonic():
    """A composed mnemonic must derive the same root as its NFKD spelling."""
    from mnemonic import Mnemonic

    composed = unicodedata.normalize("NFC", japanese)
    assert composed != japanese
    assert (
        mnemonic_to_root(composed, "").to_string()
        == mnemonic_to_root(japanese, "").to_string()
    )
    assert mnemonic_to_seed(composed, "") == Mnemonic("japanese").to_seed(
        composed, passphrase=""
    )
    assert validate_mnemonic(composed) == validate_mnemonic(japanese)


def test_wordlist_detection_receives_normalized_mnemonic(monkeypatch):
    from cryptoadvance.specter.util import mnemonic as module

    composed = unicodedata.normalize("NFC", japanese)
    original = module.get_wordlist
    detected = []

    def capture(phrase):
        detected.append(phrase)
        return original(phrase)

    monkeypatch.setattr(module, "get_wordlist", capture)
    module.mnemonic_to_seed(composed, "")
    assert detected == [japanese]


def test_ascii_passphrase_derivation_is_unchanged():
    """NFKD is a no-op for ASCII, so existing ASCII wallets keep their keys."""
    phrase = "abandon " * 11 + "about"
    assert (
        mnemonic_to_root(phrase, "correct horse").to_string()
        == mnemonic_to_root(phrase, "correct horse", legacy=True).to_string()
    )


def test_legacy_bitcoin_reproduces_pre_normalization_derivation():
    from embit import bip32, bip39

    phrase = "abandon " * 11 + "about"
    passphrase = "pässword"
    # Exactly what Specter derived before this change: no normalization, the
    # detected wordlist.
    old_seed = bip39.mnemonic_to_seed(phrase, passphrase, wordlist=get_wordlist(phrase))
    assert mnemonic_to_seed(phrase, passphrase, legacy=True) == old_seed
    assert (
        mnemonic_to_root(phrase, passphrase, legacy=True).to_string()
        == bip32.HDKey.from_seed(old_seed).to_string()
        == LEGACY_ROOT_XPRV
    )


def test_legacy_liquid_reproduces_pre_normalization_blinding_key():
    from embit import bip39
    from embit.liquid.slip77 import master_blinding_from_seed

    phrase = "abandon " * 11 + "about"
    passphrase = "pässword"
    # Exactly what Elements Core hot wallets derived before this change:
    # embit's default English wordlist and no Unicode normalization.
    old_seed = bip39.mnemonic_to_seed(phrase, passphrase)
    legacy_seed = mnemonic_to_seed(phrase, passphrase, legacy=True, liquid=True)
    assert legacy_seed == old_seed
    old_blinding = master_blinding_from_seed(old_seed)
    legacy_blinding = master_blinding_from_seed(legacy_seed)
    assert legacy_blinding.secret == old_blinding.secret
    assert legacy_blinding.wif() == old_blinding.wif()
    # The default Liquid path is normalized and must not reproduce the old key.
    default_liquid_seed = mnemonic_to_seed(phrase, passphrase, liquid=True)
    assert default_liquid_seed != old_seed
    assert master_blinding_from_seed(default_liquid_seed).secret != old_blinding.secret


def test_legacy_derivation_requires_explicit_opt_in():
    phrase = "abandon " * 11 + "about"
    passphrase = "pässword"
    assert mnemonic_to_seed(phrase, passphrase) == mnemonic_to_seed(
        phrase, passphrase, legacy=False
    )
    assert mnemonic_to_seed(phrase, passphrase) != mnemonic_to_seed(
        phrase, passphrase, legacy=True
    )
    # Liquid defaults to the normalized, detected-wordlist derivation too.
    assert mnemonic_to_seed(phrase, passphrase, liquid=True) == mnemonic_to_seed(
        phrase, passphrase
    )


def test_legacy_reproduces_old_failure_for_precomposed_mnemonic():
    """Boundary: the old code rejected precomposed non-English mnemonics.

    The legacy opt-in is an exact recovery of the old behaviour, including its
    failure modes. It is not a fallback: the default path normalizes instead.
    """
    from embit import bip39

    composed = unicodedata.normalize("NFC", japanese)
    with pytest.raises(ValueError):
        bip39.mnemonic_to_seed(composed, "", wordlist=get_wordlist(composed))
    with pytest.raises(ValueError):
        mnemonic_to_seed(composed, "", legacy=True)
    with pytest.raises(ValueError):
        mnemonic_to_seed(composed, "", legacy=True, liquid=True)
    assert mnemonic_to_seed(composed, "") == mnemonic_to_seed(japanese, "")


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
