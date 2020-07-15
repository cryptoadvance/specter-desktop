from binascii import hexlify, unhexlify, b2a_base64, a2b_base64
from typing import List
from .generic import GenericDevice

class Electrum(GenericDevice):
    def __init__(self, name, alias, device_type, keys, fullpath, manager):
        super().__init__(name, alias, 'electrum', keys, fullpath, manager)
        self.sd_card_support = True
        self.qr_code_support = True

    def create_psbts(self, base64_psbt, wallet):
        psbts = {
            'qrcode': b43_encode(a2b_base64(base64_psbt)),
            'sdcard': base64_psbt,
        }
        return psbts

########### base43 encodings ###############

BASE43_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ$*+-./:"

def b43_encode(b: bytes) -> str:
    """Encode bytes to a base58-encoded string"""

    # Convert big-endian bytes to integer
    n: int = int('0x0' + hexlify(b).decode('utf8'), 16)

    # Divide that integer into base58
    temp: List[str] = []
    while n > 0:
        n, r = divmod(n, 43)
        temp.append(BASE43_CHARS[r])
    res: str = ''.join(temp[::-1])

    # Encode leading zeros as base58 zeros
    czero: int = 0
    pad: int = 0
    for c in b:
        if c == czero:
            pad += 1
        else:
            break
    return BASE43_CHARS[0] * pad + res

def b43_decode(s: str) -> bytes:
    """Decode a base58-encoding string, returning bytes"""
    if not s:
        return b''

    # Convert the string to an integer
    n: int = 0
    for c in s:
        n *= 43
        if c not in BASE43_CHARS:
            raise ValueError('Character %r is not a valid base43 character' % c)
        digit = BASE43_CHARS.index(c)
        n += digit

    # Convert the integer to bytes
    h: str = '%x' % n
    if len(h) % 2:
        h = '0' + h
    res = unhexlify(h.encode('utf8'))

    # Add padding back.
    pad = 0
    for c in s[:-1]:
        if c == BASE43_CHARS[0]:
            pad += 1
        else:
            break
    return b'\x00' * pad + res
