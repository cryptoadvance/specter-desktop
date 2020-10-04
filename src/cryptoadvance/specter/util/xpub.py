import hashlib
from .base58 import decode_base58, encode_base58_checksum


def hash160(d):
    return hashlib.new("ripemd160", hashlib.sha256(d).digest()).digest()


def convert_xpub_prefix(xpub, prefix_bytes):
    # Update xpub to specified prefix and re-encode
    b = decode_base58(xpub)
    return encode_base58_checksum(prefix_bytes + b[4:])


def get_xpub_fingerprint(xpub):
    """
    Retuns fingerprint of the XPUB itself.
    IMPORTANT! NOT parent fingerprint, but hash160(pubkey) itself!
    """
    b = decode_base58(xpub)
    return hash160(b[-33:])[:4]
