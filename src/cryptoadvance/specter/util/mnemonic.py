import logging
from mnemonic import Mnemonic

logger = logging.getLogger(__name__)

MNEMONIC_LANGUAGES = {
    "en": "english",
    "es": "spanish",
    "fr": "french",
    "it": "italian",
    # "jp": "japanese",
    # "ko": korean",
    # "?": chinese_simplified",
    # "?": chinese_traditional",
}


def initialize_mnemonic(language_code) -> Mnemonic:
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
    :param language_code: only "en", "es", "fr" and "it" are supported. If you use an unsupported one, it'll fallback to english
    """
    mnemo = initialize_mnemonic(language_code)
    return mnemo.generate(strength=strength)


def validate_mnemonic(words):
    # We cannot assume the mnemonic will be in the same language currently active
    #   in the UI (e.g. a Spanish user is likely to have an English mnemonic).
    mnemo = initialize_mnemonic(Mnemonic.detect_language(words))
    return mnemo.check(words)
