import hashlib
from embit import base58
from embit.hashes import hash160


def convert_xpub_prefix(xpub, prefix_bytes):
    # Update xpub to specified prefix and re-encode
    b = base58.decode_check(xpub)
    return base58.encode_check(prefix_bytes + b[4:])


def get_xpub_fingerprint(xpub):
    """
    Retuns fingerprint of the XPUB itself.
    IMPORTANT! NOT parent fingerprint, but hash160(pubkey) itself!
    """
    b = base58.decode_check(xpub)
    return hash160(b[-33:])[:4]
