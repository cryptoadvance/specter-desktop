from collections import OrderedDict
from binascii import hexlify
from .helpers import decode_base58, encode_base58_checksum, get_xpub_fingerprint


purposes = OrderedDict({
    '': "General",
    "wpkh": "Single (Segwit)",
    "sh-wpkh": "Single (Nested)",
    "pkh": "Single (Legacy)",
    "wsh": "Multisig (Segwit)",
    "sh-wsh": "Multisig (Nested)",
    "sh": "Multisig (Legacy)",
})

VALID_PREFIXES = {
    b"\x04\x35\x87\xcf": {   # testnet
        b"\x04\x35\x87\xcf": '', # unknown, maybe pkh
        b"\x04\x4a\x52\x62": "sh-wpkh",
        b"\x04\x5f\x1c\xf6": "wpkh",
        b"\x02\x42\x89\xef": "sh-wsh",
        b"\x02\x57\x54\x83": "wsh",
    },
    b"\x04\x88\xb2\x1e": {   # mainnet
        b"\x04\x88\xb2\x1e": '', # unknown, maybe pkh
        b"\x04\x9d\x7c\xb2": "sh-wpkh",
        b"\x04\xb2\x47\x46": "wpkh",
        b"\x02\x95\xb4\x3f": "sh-wsh",
        b"\x02\xaa\x7e\xd3": "wsh",
    }
}

class Key:
    def __init__(self, original, fingerprint, derivation, key_type, xpub):
        if key_type is None:
            key_type = ""
        if fingerprint is None or fingerprint == '':
            fingerprint = get_xpub_fingerprint(original).hex()
        if derivation is None:
            derivation = ''
        if key_type not in purposes:
            raise Exception('Invalid key type specified: {}.')
        self.original = original
        self.fingerprint = fingerprint
        self.derivation = derivation
        self.key_type = key_type
        self.xpub = xpub

    @classmethod
    def from_json(cls, key_dict):
        original = key_dict['original'] if 'original' in key_dict else ''
        fingerprint = key_dict['fingerprint'] if 'fingerprint' in key_dict else ''
        derivation = key_dict['derivation'] if 'derivation' in key_dict else ''
        key_type = key_dict['type'] if 'type' in key_dict else ''
        xpub = key_dict['xpub'] if 'xpub' in key_dict else ''
        return cls(original, fingerprint, derivation, key_type, xpub)

    @classmethod
    def parse_xpub(cls, xpub):
        derivation = ''
        arr = xpub.strip().split("]")
        original = arr[-1]
        if len(arr) > 1:
            derivation = arr[0].replace("'","h").lower()
            xpub = arr[1]

        fingerprint = ''
        if derivation != '':
            if derivation[0] != "[":
                raise Exception("Missing leading [")
            derivation_path = derivation[1:].split("/")
            try: 
                fng = bytes.fromhex(derivation_path[0].replace("-","")) # coldcard has hexstrings like 7c-2c-8e-1b
            except:
                raise Exception("Fingerprint is not hex")
            if len(fng) != 4:
                raise Exception("Incorrect fingerprint length")
            fingerprint = derivation_path[0]
            if len(derivation_path) > 1:
                for path in derivation_path[1:]:
                    if path[-1] == "h":
                        path = path[:-1]
                    try:
                        i = int(path)
                    except:
                        raise Exception("Incorrect index")
                    derivation_path[0] = "m"
                    derivation = "/".join(derivation_path)
            else:
                derivation = ''

        # checking xpub prefix and defining key type
        xpub_bytes = decode_base58(xpub, num_bytes=82)
        prefix = xpub_bytes[:4]
        is_valid = False
        key_type = ''
        for k in VALID_PREFIXES:
            if prefix in VALID_PREFIXES[k].keys():
                key_type = VALID_PREFIXES[k][prefix]
                prefix = k
                is_valid = True
                break
        if not is_valid:
            raise Exception("Invalid xpub prefix: %s", prefix.hex())

        xpub_bytes = prefix + xpub_bytes[4:]
        xpub = encode_base58_checksum(xpub_bytes)

        # defining key type from derivation
        if derivation != '' and key_type == '':
            derivation_path = derivation.split("/")
            purpose = derivation_path[1]
            if purpose == "44h":
                key_type = "pkh"
            elif purpose == "49h":
                key_type = "sh-wpkh"
            elif purpose == "84h":
                key_type = "wpkh"
            elif purpose == "45h":
                key_type = "sh"
            elif purpose == "48h":
                if len(derivation_path) >= 5:
                    if derivation_path[4] == "1h":
                        key_type = "sh-wsh"
                    elif derivation_path[4] == "2h":
                        key_type = "wsh"

        # infer fingerprint and derivation if depth == 0 or depth == 1
        xpub_bytes = decode_base58(xpub)
        depth = xpub_bytes[4]
        if depth == 0:
            fingerprint = hexlify(get_xpub_fingerprint(xpub)).decode()
            derivation = "m"
        elif depth == 1:
            fingerprint = hexlify(xpub_bytes[5:9]).decode()
            index = int.from_bytes(xpub_bytes[9:13], "big")
            is_hardened = bool(index & 0x8000_0000)
            derivation = "m/%d%s" % (index & 0x7fff_ffff, "h" if is_hardened else "")

        return cls(original, fingerprint, derivation, key_type, xpub)

    @classmethod
    def parse_xpubs(cls, xpubs):
        xpubs = xpubs
        lines = [l.strip() for l in xpubs.split("\n") if len(l) > 0]
        failed = []
        keys = []
        for line in lines:
            try:
                keys.append(Key.parse_xpub(line))
            except Exception as e:
                failed.append(line + "\n" + str(e))
        return keys, failed


    @property
    def metadata(self):
        metadata = {}
        metadata["chain"] = "Mainnet" if self.xpub.startswith("xpub") else "Testnet"
        metadata["purpose"] = self.purpose
        if self.derivation is not None:
            metadata["combined"] = "[%s%s]%s" % (self.fingerprint, self.derivation[1:], self.xpub)
        else:
            metadata["combined"] = self.xpub
        return metadata

    @property
    def is_testnet(self):
        return not self.xpub.startswith("xpub")

    @property
    def json(self):
        return {
            'original': self.original,
            'fingerprint': self.fingerprint,
            'derivation': self.derivation,
            'type': self.key_type,
            'xpub': self.xpub
        }

    @property
    def purpose(self):
        return purposes[self.key_type]

    def __str__(self):
        if self.derivation and self.fingerprint:
            path_str = f"/{self.derivation[2:]}" if self.derivation != "m" else ""
            return f"[{self.fingerprint}{path_str}]{self.original}"
        else:
            return self.original

    def __eq__(self, other):
        return self.original == other.original

    def __hash__(self):
        return hash(self.original)
