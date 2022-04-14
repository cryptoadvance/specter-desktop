import logging
from mnemonic.mnemonic import ConfigurationError, Mnemonic
from embit import bip32, bip39, networks
from embit.wordlists.bip39 import WORDLIST

from cryptoadvance.specter.specter_error import SpecterError

logger = logging.getLogger(__name__)

MNEMONIC_LANGUAGES = {
    "en": "english",
    "es": "spanish",
    # "fr": "french", # Not supported, for details see: https://github.com/trezor/python-mnemonic/issues/98)
    "it": "italian",
    # "jp": "japanese",
    # "ko": korean",
    # "?": chinese_simplified",
    # "?": chinese_traditional",
}


def initialize_mnemonic(language_code: str) -> Mnemonic:
    if language_code not in MNEMONIC_LANGUAGES:
        # Fall back to English if Mnemonic doesn't support the current language
        logger.debug(
            f"Language code '{language_code}' not supported by python-mnemonic; using English"
        )
        language_code = "en"
    return Mnemonic(language=MNEMONIC_LANGUAGES[language_code])


def generate_mnemonic(strength=256, language_code="en") -> str:
    """returns a 24 wordlist by using the mnemonic library:
    "tomorrow question cook lend burden bone own junior stage square leaf father edge decrease pipe tired useful junior calm silver topple require rug clock"

    :param strength: 256 (default) will give you 24 words. 128 will result in 12 words
    :param language_code: only "en", "es", and "it" are supported. If you use an unsupported one, it'll fallback to English.
    """
    mnemo = initialize_mnemonic(language_code)
    return mnemo.generate(strength=strength)


def get_language(mnemonic: str) -> str:
    try:
        supported_language_found = False
        language = Mnemonic.detect_language(mnemonic)
        words_as_list = mnemonic.split()
        # If we get French as language we have to double check whether it is not really an English mnemonic because of overlaps in the wordlists
        if language == "french":
            count = 0
            for word in words_as_list:
                if word in WORDLIST:
                    count += 1
            if count == 12:
                language = "english"
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
    language = get_language(mnemonic)
    mnemo = Mnemonic(language)
    return mnemo.check(mnemonic)


def get_wordlist(mnemonic: str) -> list:
    language = get_language(mnemonic)
    mnemo = Mnemonic(language)
    wordlist = mnemo.wordlist
    return wordlist


def mnemonic_to_root(mnemonic: str, passphrase: str) -> bip32.HDKey:
    wordlist = get_wordlist(mnemonic)
    seed = bip39.mnemonic_to_seed(mnemonic, passphrase, wordlist=wordlist)
    root = bip32.HDKey.from_seed(seed)
    return root
