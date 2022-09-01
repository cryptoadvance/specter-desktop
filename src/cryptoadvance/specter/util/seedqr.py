import logging
import re
from embit import bip39
from embit.wordlists.bip39 import WORDLIST
from typing import List

logger = logging.getLogger(__name__)


"""
    SeedQR specification:
    https://github.com/SeedSigner/seedsigner/blob/dev/docs/seed_qr/README.md
"""


def parse_standard_seedqr(
    digitstream: str, wordlist: List[str] = WORDLIST
) -> List[str]:
    """
    Reads a Standard SeedQR digitstream and returns its associated mnemonic
    """
    # The digitstream should be either:
    #   * 48 digits (12-word mnemonic)
    #   * 96 digits (24-word mnemonic)
    if not re.search("^[0-9]{48}$|^[0-9]{96}$", digitstream):
        logger.warn(f"Invalid Standard SeedQR datastream: {digitstream}")
        return None

    # Parse the digitstream, 4 digits at a time
    mnemonic = []
    for i in range(0, int(len(digitstream) / 4)):
        wordlist_index = int(digitstream[i * 4 : i * 4 + 4])
        mnemonic.append(WORDLIST[wordlist_index])

    return mnemonic


def parse_compact_seedqr(bytestream: str, wordlist: List[str] = WORDLIST) -> List[str]:
    """
    Reads a Compact SeedQR bytestream and returns its associated mnemonic
    """
    print(bytestream)

    # The bytestream should be either:
    #   * 16 bytes (12-word mnemonic)
    #   * 32 bytes (24-word mnemonic)
    if len(bytestream) not in [16, 32]:
        logger.warn(f"Invalid Compact SeedQR bytestream: {len(bytestream)} bytes")
        return None

    # The bytestream is directly fed into embit
    return bip39.mnemonic_from_bytes(entropy=bytestream, wordlist=wordlist)
