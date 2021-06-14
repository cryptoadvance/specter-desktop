import hashlib

BASE58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def double_sha256(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()


def encode_base58(s):
    # determine how many 0 bytes (b'\x00') s starts with
    count = 0
    for c in s:
        if c == 0:
            count += 1
        else:
            break
    prefix = b"1" * count
    # convert from binary to hex, then hex to integer
    num = int.from_bytes(s, "big")
    result = bytearray()
    while num > 0:
        num, mod = divmod(num, 58)
        result.insert(0, BASE58_ALPHABET[mod])

    return prefix + bytes(result)


def encode_base58_checksum(s):
    """Adds the checksum and then encodes to base58"""
    return encode_base58(s + double_sha256(s)[:4]).decode("ascii")


def decode_base58(s, num_bytes=82, strip_leading_zeros=False):
    """Decodes a base58 encoded string with a checksum at the end, does not support legacy
    addresses due to their prefixes (0 bytes), returns WITHOUT
    checksum, strip_leading_zeros has to be set to True to avoid
    raising a ValueError"""
    num = 0
    for c in s.encode("ascii"):
        num *= 58
        num += BASE58_ALPHABET.index(c)
    combined = num.to_bytes(num_bytes, byteorder="big")
    if strip_leading_zeros:
        while combined[0] == 0:
            combined = combined[1:]
    checksum = combined[-4:]
    if double_sha256(combined[:-4])[:4] != checksum:
        raise ValueError(
            "bad address: {} {}".format(checksum, double_sha256(combined)[:4])
        )
    return combined[:-4]
