from collections import OrderedDict
from binascii import hexlify
from embit import base58
from .util.xpub import get_xpub_fingerprint


purposes = OrderedDict(
    {
        "": "General",
        "wpkh": "Single (Segwit)",
        "sh-wpkh": "Single (Nested)",
        "wsh": "Multisig (Segwit)",
        "sh-wsh": "Multisig (Nested)",
    }
)

VALID_PREFIXES = {
    b"\x04\x35\x87\xcf": {  # testnet
        b"\x04\x35\x87\xcf": "",  # unknown, maybe pkh
        b"\x04\x4a\x52\x62": "sh-wpkh",
        b"\x04\x5f\x1c\xf6": "wpkh",
        b"\x02\x42\x89\xef": "sh-wsh",
        b"\x02\x57\x54\x83": "wsh",
    },
    b"\x04\x88\xb2\x1e": {  # mainnet
        b"\x04\x88\xb2\x1e": "",  # unknown, maybe pkh
        b"\x04\x9d\x7c\xb2": "sh-wpkh",
        b"\x04\xb2\x47\x46": "wpkh",
        b"\x02\x95\xb4\x3f": "sh-wsh",
        b"\x02\xaa\x7e\xd3": "wsh",
    },
}


class Key:
    def __init__(self, original, fingerprint, derivation, key_type, purpose, xpub):
        if key_type is None:
            key_type = ""
        if fingerprint is None or fingerprint == "":
            fingerprint = get_xpub_fingerprint(original).hex()
        if derivation is None:
            derivation = ""
        if key_type not in purposes:
            key_type = ""
        if not purpose:
            purpose = purposes.get(key_type, "General")
        self.original = original
        self.fingerprint = fingerprint
        self.derivation = derivation
        self.key_type = key_type
        self.purpose = purpose
        self.xpub = xpub

    @classmethod
    def from_json(cls, key_dict):
        original = key_dict.get("original", "")
        fingerprint = key_dict.get("fingerprint", "")
        derivation = key_dict.get("derivation", "")
        key_type = key_dict.get("type", "")
        purpose = key_dict.get("purpose", "")
        xpub = key_dict.get("xpub", "")
        return cls(original, fingerprint, derivation, key_type, purpose, xpub)

    @classmethod
    def parse_xpub(cls, xpub, purpose=""):
        derivation = ""
        arr = xpub.strip().split("]")
        original = arr[-1]
        if len(arr) > 1:
            derivation = arr[0].replace("'", "h").lower()
            xpub = arr[1]

        fingerprint = ""
        # just to be sure fgp/1h/2/3/ is also parsed correctly
        # because we have free-form inputs
        derivation = derivation.rstrip("/")
        if derivation != "":
            if derivation[0] != "[":
                raise Exception("Missing leading [")
            derivation_path = derivation[1:].split("/")
            try:
                fng = bytes.fromhex(
                    derivation_path[0].replace("-", "")
                )  # coldcard has hexstrings like 7c-2c-8e-1b
            except Exception:
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
                derivation = ""

        # checking xpub prefix and defining key type
        xpub_bytes = base58.decode_check(xpub)
        prefix = xpub_bytes[:4]
        is_valid = False
        key_type = ""
        for k in VALID_PREFIXES:
            if prefix in VALID_PREFIXES[k].keys():
                key_type = VALID_PREFIXES[k][prefix]
                prefix = k
                is_valid = True
                break
        if not is_valid:
            raise Exception("Invalid xpub prefix: %s", prefix.hex())

        xpub_bytes = prefix + xpub_bytes[4:]
        xpub = base58.encode_check(xpub_bytes)

        # defining key type from derivation
        if derivation != "" and key_type == "":
            derivation_path = derivation.split("/")
            derivation_type = derivation_path[1]
            if derivation_type == "49h":
                key_type = "sh-wpkh"
            elif derivation_type == "84h":
                key_type = "wpkh"
            elif derivation_type == "48h":
                if len(derivation_path) >= 5:
                    if derivation_path[4] == "1h":
                        key_type = "sh-wsh"
                    elif derivation_path[4] == "2h":
                        key_type = "wsh"

        # infer fingerprint and derivation if depth == 0 or depth == 1
        xpub_bytes = base58.decode_check(xpub)
        depth = xpub_bytes[4]
        if depth == 0:
            fingerprint = hexlify(get_xpub_fingerprint(xpub)).decode()
            derivation = "m"
        elif depth == 1:
            fingerprint = hexlify(xpub_bytes[5:9]).decode()
            index = int.from_bytes(xpub_bytes[9:13], "big")
            is_hardened = bool(index & 0x8000_0000)
            derivation = "m/%d%s" % (index & 0x7FFF_FFFF, "h" if is_hardened else "")

        return cls(original, fingerprint, derivation, key_type, purpose, xpub)

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
            metadata["combined"] = "[%s%s]%s" % (
                self.fingerprint,
                self.derivation[1:],
                self.xpub,
            )
        else:
            metadata["combined"] = self.xpub
        return metadata

    @property
    def is_testnet(self):
        return not self.xpub.startswith("xpub")

    @property
    def json(self):
        return {
            "original": self.original,
            "fingerprint": self.fingerprint,
            "derivation": self.derivation,
            "type": self.key_type,
            "purpose": self.purpose,
            "xpub": self.xpub,
        }

    def to_string(self, slip132=True):
        if self.derivation and self.fingerprint:
            path_str = f"/{self.derivation[2:]}" if self.derivation != "m" else ""
            return f"[{self.fingerprint}{path_str}]{self.original if slip132 else self.xpub}"
        else:
            return self.original if slip132 else self.xpub

    def __str__(self):
        return self.to_string()

    def __eq__(self, other):
        return self.original == other.original

    def __hash__(self):
        return hash(self.original)
