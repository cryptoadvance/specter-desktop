import logging
import unicodedata
from mnemonic.mnemonic import ConfigurationError, Mnemonic
from embit import bip32, bip39, networks
from embit.wordlists.bip39 import WORDLIST
from cryptoadvance.specter.specter_error import SpecterError

logger = logging.getLogger(__name__)


""" This module is using two libraries: Trezor's python-mnemonic (https://github.com/trezor/python-mnemonic) 
and embit (https://github.com/diybitcoinhardware/embit)"""


MNEMONIC_LANGUAGES = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "it": "italian",
    "jp": "japanese",
    "cz": "czech",
    "pt": "portuguese",
    # "ko": "korean", requires special characters
    # "ru": "russian", requires special characters
    # "tr": "turkish", has a lot of overlapping words with other languages
    # "?": chinese_simplified",
    # "?": chinese_traditional",
}


def initialize_mnemonic(language_code: str) -> Mnemonic:
    """Returns a language specific Mnemonic instance. If the language code is not supported, English is used."""
    if language_code not in MNEMONIC_LANGUAGES:
        logger.debug(
            f"Language code '{language_code}' not supported by python-mnemonic; using English"
        )
        language_code = "en"
    return Mnemonic(language=MNEMONIC_LANGUAGES[language_code])


def generate_mnemonic(strength=256, language_code="en") -> str:
    """returns a 24 wordlist:
    "tomorrow question cook lend burden bone own junior stage square leaf father edge decrease pipe tired useful junior calm silver topple require rug clock"

    :param strength: 256 (default) will give you 24 words. 128 will result in 12 words
    :param language_code: "en", "es", "fr", "it", "jp", "cz" and "pt" are supported. If you use an unsupported one, it'll fallback to English.
    """
    mnemo = initialize_mnemonic(language_code)
    return mnemo.generate(strength=strength)


def get_language(mnemonic: str) -> str:
    """Returns the language based on the mnemonic provided, errors are raised if a language is not supported or not properly detected"""
    try:
        supported_language_found = False
        language = Mnemonic.detect_language(unicodedata.normalize("NFKD", mnemonic))
        words_as_list = mnemonic.split()
        for key, value in MNEMONIC_LANGUAGES.items():
            if value == language:
                supported_language_found = True
                return language
        if supported_language_found == False:
            raise SpecterError(
                f"The language {language.capitalize()} is not supported."
            )
    except ConfigurationError as ce:
        raise SpecterError(str(ce))


def validate_mnemonic(mnemonic: str) -> bool:
    """Returns true if the length and the checksum of the mnemonic are correct"""
    mnemonic = unicodedata.normalize("NFKD", mnemonic)
    language = get_language(mnemonic)
    mnemo = Mnemonic(language)
    return mnemo.check(mnemonic)


def get_wordlist(mnemonic: str) -> list:
    """Returns a language specific wordlist"""
    language = get_language(mnemonic)
    mnemo = Mnemonic(language)
    wordlist = mnemo.wordlist
    return wordlist


def legacy_bip39_requested(form) -> bool:
    """Whether the user explicitly opted into pre-NFKD (legacy) BIP39 derivation.

    An HTML checkbox submits its value only when checked, so the literal string
    "1" is the single accepted opt-in. Absent, empty or any other value keeps
    the standards-compliant default: legacy derivation is never a fallback.
    """
    return form.get("legacy_bip39") == "1"


def mnemonic_to_seed(
    mnemonic: str, passphrase: str, legacy: bool = False, liquid: bool = False
) -> bytes:
    """Derive the BIP39 seed, or explicitly recover a pre-NFKD Specter seed.

    BIP39 requires NFKD normalization of both the mnemonic and the passphrase.
    Specter used to pass them through unchanged, which derives a different
    wallet for non-ASCII passphrases (and for precomposed mnemonics). The
    default path below is standards-compliant; ``legacy=True`` reproduces the
    old derivation and must only be requested explicitly by the user.

    Legacy Liquid used embit's default English wordlist rather than the
    detected wordlist used for Bitcoin. Preserve that distinction for exact
    recovery.
    """
    if legacy and liquid:
        return bip39.mnemonic_to_seed(mnemonic, passphrase)
    if legacy:
        return bip39.mnemonic_to_seed(
            mnemonic, passphrase, wordlist=get_wordlist(mnemonic)
        )
    normalized_mnemonic = unicodedata.normalize("NFKD", mnemonic)
    return bip39.mnemonic_to_seed(
        normalized_mnemonic,
        unicodedata.normalize("NFKD", passphrase),
        wordlist=get_wordlist(normalized_mnemonic),
    )


def existing_device_root_matches(keys, mnemonic, passphrase, legacy=False) -> bool:
    """Accept an existing root only when a key carries its master origin.

    Devices can contain keys from multiple roots; a match against any known
    master origin is sufficient. An xpub without an origin has only its own
    fingerprint, not a trustworthy master fingerprint.
    """
    root = mnemonic_to_root(mnemonic, passphrase, legacy=legacy)
    fingerprint = root.child(0).fingerprint.hex()
    return any(
        key.derivation and key.fingerprint.lower() == fingerprint for key in keys
    )


def mnemonic_to_root(
    mnemonic: str, passphrase: str, legacy: bool = False
) -> bip32.HDKey:
    """Returns an embit BIP32 root key class"""
    seed = mnemonic_to_seed(mnemonic, passphrase, legacy=legacy)
    root = bip32.HDKey.from_seed(seed)
    return root
