### bc-ur encoding stuff
CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

def bech32_polymod(values):
    """Internal function that computes the Bech32 checksum."""
    generator = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ value
        for i in range(5):
            chk ^= generator[i] if ((top >> i) & 1) else 0
    return chk

def bech32_hrp_expand(hrp):
    """Expand the HRP into values for checksum computation."""
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def bech32_verify_checksum(hrp, data):
    """Verify a checksum given HRP and converted data characters."""
    return bech32_polymod(bech32_hrp_expand(hrp) + data) == 1


def bech32_create_checksum(hrp, data):
    """Compute the checksum values given HRP and data."""
    values = bech32_hrp_expand(hrp) + data
    polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def bech32_encode(hrp, data):
    """Compute a Bech32 string given HRP and data values."""
    combined = data + bech32_create_checksum(hrp, data)
    return hrp + '1' + ''.join([CHARSET[d] for d in combined])


def bech32_decode(bech):
    """Validate a Bech32 string, and determine HRP and data."""
    if ((any(ord(x) < 33 or ord(x) > 126 for x in bech)) or
            (bech.lower() != bech and bech.upper() != bech)):
        return (None, None)
    bech = bech.lower()
    pos = bech.rfind('1')
    if pos < 1 or pos + 7 > len(bech) or len(bech) > 90:
        return (None, None)
    if not all(x in CHARSET for x in bech[pos+1:]):
        return (None, None)
    hrp = bech[:pos]
    data = [CHARSET.find(x) for x in bech[pos+1:]]
    if not bech32_verify_checksum(hrp, data):
        return (None, None)
    return (hrp, data[:-6])


def convertbits(data, frombits, tobits, pad=True):
    """General power-of-2 base conversion."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    max_acc = (1 << (frombits + tobits - 1)) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            return None
        acc = ((acc << frombits) | value) & max_acc
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        return None
    return ret


def decode(hrp, addr):
    """Decode a segwit address."""
    hrpgot, data = bech32_decode(addr)
    if hrpgot != hrp:
        return (None, None)
    decoded = convertbits(data[1:], 5, 8, False)
    if decoded is None or len(decoded) < 2 or len(decoded) > 40:
        return (None, None)
    if data[0] > 16:
        return (None, None)
    if data[0] == 0 and len(decoded) != 20 and len(decoded) != 32:
        return (None, None)
    return (data[0], decoded)


def encode(hrp, witver, witprog):
    """Encode a segwit address."""
    ret = bech32_encode(hrp, [witver] + convertbits(witprog, 8, 5))
    if decode(hrp, ret) == (None, None):
        return None
    return ret

def bc32encode(data:bytes)->str:
    """
    bc32 encoding 
    see https://github.com/BlockchainCommons/Research/blob/master/papers/bcr-2020-004-bc32.md
    """
    dd = convertbits(data, 8, 5)
    polymod = bech32_polymod([0] + dd + [0, 0, 0, 0, 0, 0]) ^ 0x3fffffff
    chk = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return ''.join([CHARSET[d] for d in dd+chk])

def bc32decode(bc32:str)->bytes:
    """
    bc32 decoding 
    see https://github.com/BlockchainCommons/Research/blob/master/papers/bcr-2020-004-bc32.md
    """
    if (bc32.lower() != bc32 and bc32.upper() != bc32):
        return None
    bc32 = bc32.lower()
    if not all([x in CHARSET for x in bc32]):
        return None
    res = [CHARSET.find(c) for c in bc32.lower()]
    if bech32_polymod([0] + res)!=0x3fffffff:
        return None
    return bytes(convertbits(res[:-6],5,8,False))

if __name__ == '__main__':
    from binascii import a2b_base64
    b64 = "cHNidP8BAHEBAAAAAfPQ5Rpeu5nH0TImK4Sbu9lxIOGEynRadywPxaPyhnTwAAAAAAD/////AkoRAAAAAAAAFgAUFCYoQzGSRmYVAuZNuXF0OrPg9jWIEwAAAAAAABYAFOZMlwM1sZGLivwOcOh77amAlvD5AAAAAAABAR+tKAAAAAAAABYAFM4u9V5WG+Fe9l3MefmYEX4ULWAWIgYDA+jO+oOuN37ABK67BA/+SuuR/57c7OkyfyR7hR34FDsYccBxUlQAAIAAAACAAAAAgAAAAAAFAAAAACICApJMZBvzWiavLN7nievKQoylwPoffLkXZUIgGHF4HgwaGHHAcVJUAACAAAAAgAAAAIABAAAACwAAAAAA"
    raw = a2b_base64(b64)
    enc = bc32encode(raw)
    testres = [
        "tyq3wurnvf607qgqwyqsqqqqq8eapeg6t6aen373xgnzhpymh0vhzg8psn98gknh9s8utgljse60qqqqqqqqpllllllsyjs3qqqqqqqqqqtqq9q5yc5yxvvjgenp2qhxfkuhzap6k0s0vdvgzvqqqqqqqqqpvqq5uexfwqe4kxgchzhupecws7ld4xqfdu8eqqqqqqqq",
        "qyq3ltfgqqqqqqqqqqtqq9xw9m64u4smu900vhwv08uesyt7zskkq93zqcps86xwl2p6udm7cqz2awcyplly46u3l70dem8fxfljg7u9rhupgwccw8q8z5j5qqqgqqqqqzqqqqqqsqqqqqqqq5qqqqqqygpq9yjvvsdlxk3x4ukdaeufa09y9r99crap7l9ezaj5ygqc",
        "w9upurq6rpcuqu2j2sqqpqqqqqqgqqqqqzqqzqqqqq9sqqqqqqqqmkdau4"
    ]
    print(raw.hex())
    print(bc32decode("".join(testres)).hex())
# wpekya8lqyq8zqgqqqqqru7su5d9awueclgnyf3tsjdmhkt3yrscfjn5tfmjcr7950egva8sqqqqqqqqllllllczfggsqqqqqqqqq9sqzs2zv2zrxxfyves4qtnymwt3wsat8c8kxkypxqqqqqqqqqqkqq2wvnyhqv6mryvt3t7quu8g00k6nqyk7rusqqqqqqqqzqgl455qqqqqqqqqq9sqzn8zaa272cd7zhhkthx8n7vcz9lpgttqzc3qvqcrar804qawxalvqp9whvzqllj2awgll8kuan5nyley0wz3m7q58vv8rsr32f2qqqyqqqqqpqqqqqqgqqqqqqqq2qqqqqqzyqszjfxxgxlntgn27tx7u7y7hjjz3jjup7sl0ju3we2zyqv8z7q7psdpsuwqw9f9gqqqsqqqqqyqqqqqpqqpqqqqqzcqqqqqqqq0s6h0x
# ur:bytes/1of3/hlwjxjx550k4nnfdl5py2tn3vnh6g60slnw5dmld6ktrkkz200as49spg5/tyq3wurnvf607qgqwyqsqqqqq8eapeg6t6aen373xgnzhpymh0vhzg8psn98gknh9s8utgljse60qqqqqqqqpllllllsyjs3qqqqqqqqqqtqq9q5yc5yxvvjgenp2qhxfkuhzap6k0s0vdvgzvqqqqqqqqqpvqq5uexfwqe4kxgchzhupecws7ld4xqfdu8eqqqqqqqq