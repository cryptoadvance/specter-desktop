import logging
import re
from embit import bip32, ec, networks, script
from embit.liquid.networks import get_network
from cryptoadvance.specter.key import Key
from cryptoadvance.specter.specter_error import SpecterError

# Based on hwilib by achow101: https://github.com/bitcoin-core/HWI/blob/1.2.1/hwilib/descriptor.py which is from
# https://github.com/bitcoin/bitcoin/blob/0.21/src/script/descriptor.cpp


def PolyMod(c, val):
    c0 = c >> 35
    c = ((c & 0x7FFFFFFFF) << 5) ^ val
    if c0 & 1:
        c ^= 0xF5DEE51989
    if c0 & 2:
        c ^= 0xA9FDCA3312
    if c0 & 4:
        c ^= 0x1BAB10E32D
    if c0 & 8:
        c ^= 0x3706B1677A
    if c0 & 16:
        c ^= 0x644D626FFD
    return c


def DescriptorChecksum(desc):
    INPUT_CHARSET = "0123456789()[],'/*abcdefgh@:$%{}IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~ijklmnopqrstuvwxyzABCDEFGH`#\"\\ "
    CHECKSUM_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"

    c = 1
    cls = 0
    clscount = 0
    for ch in desc:
        pos = INPUT_CHARSET.find(ch)
        if pos == -1:
            return ""
        c = PolyMod(c, pos & 31)
        cls = cls * 3 + (pos >> 5)
        clscount += 1
        if clscount == 3:
            c = PolyMod(c, cls)
            cls = 0
            clscount = 0
    if clscount > 0:
        c = PolyMod(c, cls)
    for j in range(0, 8):
        c = PolyMod(c, 0)
    c ^= 1

    ret = [None] * 8
    for j in range(0, 8):
        ret[j] = CHECKSUM_CHARSET[(c >> (5 * (7 - j))) & 31]
    return "".join(ret)


def AddChecksum(desc):
    return desc + "#" + DescriptorChecksum(desc)


# Not in hwilib
def derive_pubkey(key, path_suffix=None, idx=None):
    # if SEC pubkey - just return it
    if key[:2] in ["02", "03", "04"]:
        return ec.PublicKey.parse(bytes.fromhex(key))
    # otherwise - xpub or xprv
    hd = bip32.HDKey.from_base58(key)
    if hd.is_private:
        hd = hd.to_public()
    # if we have path suffix
    path = "m" + (path_suffix or "")
    if idx is not None:
        path = path.replace("*", str(idx))
    return hd.derive(path).key


class Descriptor:
    def __init__(
        self,
        origin_fingerprint,
        origin_path,
        base_key,
        path_suffix,
        testnet,
        sh_wpkh=None,
        wpkh=None,
        sh=None,
        sh_wsh=None,
        wsh=None,
        multisig_M=None,
        multisig_N=None,
        sort_keys=True,
    ):
        self.origin_fingerprint = origin_fingerprint
        self.origin_path = origin_path
        self.path_suffix = path_suffix
        self.base_key = base_key
        self.testnet = testnet
        self.sh_wpkh = sh_wpkh
        self.wpkh = wpkh
        self.sh = sh
        self.sh_wsh = sh_wsh
        self.wsh = wsh
        self.multisig_M = multisig_M
        self.multisig_N = multisig_N
        self.m_path = None
        self.sort_keys = sort_keys

        if origin_path and not isinstance(origin_path, list):
            self.m_path_base = "m" + origin_path
            self.m_path = "m" + origin_path + (path_suffix or "")
        elif isinstance(origin_path, list):
            self.m_path_base = []
            self.m_path = []
            for i in range(0, len(origin_path)):
                if origin_path[i]:
                    self.m_path_base.append("m" + origin_path[i])
                    self.m_path.append("m" + origin_path[i] + (path_suffix[i] or ""))
                else:
                    self.m_path_base.append(None)
                    self.m_path.append(None)

    @classmethod
    def parse(cls, desc, testnet=False):
        sh_wpkh = None
        wpkh = None
        sh = None
        sh_wsh = None
        wsh = None
        origin_fingerprint = None
        origin_path = None
        base_key_and_path_match = None
        base_key = None
        path_suffix = None
        multisig_M = None
        multisig_N = None
        sort_keys = True

        # Check the checksum
        check_split = desc.split("#")
        # Multiple # in desc
        if len(check_split) > 2:
            raise SpecterError(
                f"Too many separators in the descriptor. Check if there are multiple # in {desc}."
            )
        if len(check_split) == 2:
            # Empty checkusm
            if len(check_split[1]) == 0:
                raise SpecterError("Checksum is empty.")
            # Incorrect length
            elif len(check_split[1]) != 8:
                raise SpecterError(
                    f"Checksum {check_split[1]} doesn't have the correct length. Should be 8 characters not {len(check_split[1])}."
                )
            checksum = DescriptorChecksum(check_split[0])
            # Check of checksum calc
            if checksum.strip() == "":
                raise SpecterError(f"Checksum calculation went wrong.")
            # Wrong checksum
            if checksum != check_split[1]:
                raise SpecterError(
                    f"{check_split[1]} is the wrong checkum should be {checksum}."
                )
        desc = check_split[0]

        if desc.startswith("sh(wpkh("):
            sh_wpkh = True
        elif desc.startswith("wpkh("):
            wpkh = True
        elif desc.startswith("sh(wsh("):
            sh_wsh = True
        elif desc.startswith("wsh("):
            wsh = True
        elif desc.startswith("sh("):
            sh = True

        if sh or sh_wsh or wsh:
            if "multi(" not in desc:
                # only multisig scripts are supported
                return None
            # get the list of keys only
            keys = desc.split(",", 1)[1].split(")", 1)[0].split(",")
            sort_keys = "sortedmulti" in desc
            if "sortedmulti" in desc:
                # sorting makes sense only if individual pubkeys are provided
                base_keys = [x if "]" not in x else x.split("]")[1] for x in keys]
                bare_pubkeys = [k for k in base_keys if k[:2] in ["02", "03", "04"]]
                if len(bare_pubkeys) == len(keys):
                    keys.sort(key=lambda x: x if "]" not in x else x.split("]")[1])
            multisig_M = desc.split(",")[0].split("(")[-1]
            multisig_N = len(keys)
            if int(multisig_M) > multisig_N:
                raise SpecterError(
                    f"Multisig threshold cannot be larger than the number of keys. Threshold is {int(multisig_M)} but only {multisig_N} keys specified."
                )
        else:
            keys = [desc.split("(")[-1].split(")", 1)[0]]

        descriptors = []
        for key in keys:
            origin_fingerprint = None
            origin_path = None
            base_key = None
            path_suffix = None
            origin_match = re.search(r"\[(.*)\]", key)
            if origin_match:
                origin = origin_match.group(1)
                match = re.search(r"^([0-9a-fA-F]{8})(\/.*)", origin)
                if match:
                    origin_fingerprint = match.group(1)
                    origin_path = match.group(2)
                    # Replace h with '
                    origin_path = origin_path.replace("h", "'")
                else:
                    origin_fingerprint = origin
                    origin_path = ""

                base_key_and_path_match = re.search(r"\[.*\](\w+)([\d'\/\*]*)", key)
            else:
                base_key_and_path_match = re.search(r"(\w+)([\d'\/\*]*)", key)

            if base_key_and_path_match:
                base_key = base_key_and_path_match.group(1)
                path_suffix = base_key_and_path_match.group(2)
                if path_suffix == "":
                    path_suffix = None
            else:
                if origin_match is None:
                    return None

            descriptors.append(
                cls(
                    origin_fingerprint,
                    origin_path,
                    base_key,
                    path_suffix,
                    testnet,
                    sh_wpkh,
                    wpkh,
                    sh,
                    sh_wsh,
                    wsh,
                    sort_keys,
                )
            )

        if len(descriptors) == 1:
            return descriptors[0]
        else:
            # for multisig scripts save as lists all keypaths fields
            return cls(
                [descriptor.origin_fingerprint for descriptor in descriptors],
                [descriptor.origin_path for descriptor in descriptors],
                [descriptor.base_key for descriptor in descriptors],
                [descriptor.path_suffix for descriptor in descriptors],
                testnet,
                sh_wpkh,
                wpkh,
                sh,
                sh_wsh,
                wsh,
                multisig_M,
                multisig_N,
                sort_keys,
            )

    @property
    def is_multisig(self):
        return bool(self.multisig_N)

    @property
    def address_type(self):
        if self.wpkh:
            return "wpkh"
        elif self.wsh:
            return "wsh"
        elif self.sh_wpkh:
            return "sh-wpkh"
        elif self.sh_wsh:
            return "sh-wsh"
        elif self.sh:
            return "sh"
        else:
            return "pkh"

    def derive(self, idx, keep_xpubs=False):
        """
        Derives a descriptor with index idx up to the pubkeys.
        If keep_xpubs is False all xpubs will be replaced by pubkeys
        so [fgp/path]xpub/suffix changes to [fgp/path/suffix]pubkey
        Otherwise xpubs will be sorted according to pubkeys
        but remain in the descriptor
        """
        if self.is_multisig:
            keys = []
            for i, key in enumerate(self.base_key):
                keys.append(
                    (
                        derive_pubkey(key, self.path_suffix[i], idx),
                        key,
                        self.origin_fingerprint[i],
                        self.origin_path[i],
                        self.path_suffix[i],
                    )
                )
            if self.sort_keys:
                keys = sorted(keys, key=lambda k: k[0])
            origin_fingerprint = [k[2] for k in keys]
            if keep_xpubs:
                base_key = [k[1] for k in keys]
                origin_path = [k[3] for k in keys]
                path_suffix = [(k[4] or "") for k in keys]
                path_suffix = [(p.replace("*", str(idx)) or None) for p in path_suffix]
            else:
                base_key = [k[0].sec().hex() for k in keys]
                origin_path = [(k[3] or "") + (k[4] or "") for k in keys]
                origin_path = [(p.replace("*", str(idx)) or None) for p in origin_path]
                path_suffix = [None for k in keys]
        else:
            origin_fingerprint = self.origin_fingerprint
            if keep_xpubs:
                base_key = self.base_key
                origin_path = self.origin_path
                path_suffix = self.path_suffix
                path_suffix = (
                    path_suffix.replace("*", str(idx)) if path_suffix else None
                )
            else:
                base_key = (
                    derive_pubkey(self.base_key, self.path_suffix, idx).sec().hex()
                )
                origin_path = (self.origin_path or "") + (self.path_suffix or "")
                origin_path = origin_path.replace("*", str(idx)) or None
                path_suffix = None
        return Descriptor(
            origin_fingerprint,
            origin_path,
            base_key,
            path_suffix,
            self.testnet,
            self.sh_wpkh,
            self.wpkh,
            self.sh,
            self.sh_wsh,
            self.wsh,
            self.multisig_M,
            self.multisig_N,
            self.sort_keys,
        )

    def scriptpubkey(self, idx=None):
        if idx is None and "*" in self.serialize():
            raise RuntimeError("Index is required")
        if self.is_multisig:
            keys = []
            for i, key in enumerate(self.base_key):
                keys.append(derive_pubkey(key, self.path_suffix[i], idx))
            if self.sort_keys:
                keys = sorted(keys)
            sc = script.multisig(int(self.multisig_M), keys)
            if self.sh:
                return script.p2sh(sc)
            elif self.sh_wsh:
                return script.p2sh(script.p2wsh(sc))
            elif self.wsh:
                return script.p2wsh(sc)
        else:
            key = derive_pubkey(self.base_key, self.path_suffix, idx)
            if self.wpkh:
                return script.p2wpkh(key)
            elif self.sh_wpkh:
                return script.p2sh(script.p2wpkh(key))
            else:
                return script.p2pkh(key)

    def address(self, idx=None, network=None):
        if network is None:
            net = get_network("test" if self.testnet else "main")
        else:
            net = get_network(network)
        return self.scriptpubkey(idx).address(net)

    def serialize(self):
        descriptor_open = "pkh("
        descriptor_close = ")"

        if self.wpkh:
            descriptor_open = "wpkh("
        elif self.sh_wpkh:
            descriptor_open = "sh(wpkh("
            descriptor_close = "))"
        elif self.sh:
            descriptor_open = "sh("
            descriptor_close = ")"
        elif self.sh_wsh:
            descriptor_open = "sh(wsh("
            descriptor_close = "))"
        elif self.wsh:
            descriptor_open = "wsh("
            descriptor_close = ")"

        if self.is_multisig:
            multi = "sortedmulti" if self.sort_keys else "multi"
            base_open = f"{multi}({self.multisig_M},"
            base_close = ")"
            origins = []
            for i in range(self.multisig_N):
                path_suffix = ""
                origin = ""
                if self.origin_fingerprint[i] and self.origin_path[i]:
                    origin = (
                        "[" + self.origin_fingerprint[i] + self.origin_path[i] + "]"
                    )

                if self.path_suffix[i]:
                    path_suffix = self.path_suffix[i]

                origins.append(origin + self.base_key[i] + path_suffix)

            base = base_open + ",".join(origins) + base_close
        else:
            origin = ""
            path_suffix = ""
            if self.origin_fingerprint and self.origin_path:
                origin = "[" + self.origin_fingerprint + self.origin_path + "]"

            if self.path_suffix:
                path_suffix = self.path_suffix

            base = origin + self.base_key + path_suffix

        return AddChecksum(descriptor_open + base + descriptor_close)

    def parse_signers(self, devices, cosigners_types):
        keys = []
        cosigners = []
        unknown_cosigners = []
        unknown_cosigners_types = []

        if self.multisig_N == None:
            self.multisig_N = 1
            self.multisig_M = 1
            self.origin_fingerprint = [self.origin_fingerprint]
            self.origin_path = [self.origin_path]
            self.base_key = [self.base_key]
        for i in range(self.multisig_N):
            cosigner_found = False
            for device in devices:
                cosigner = devices[device]
                if self.origin_fingerprint[i] is None:
                    self.origin_fingerprint[i] = ""
                if self.origin_path[i] is None:
                    self.origin_path[i] = self.origin_fingerprint[i]
                for key in cosigner.keys:
                    if key.fingerprint + key.derivation.replace(
                        "m", ""
                    ) == self.origin_fingerprint[i] + self.origin_path[i].replace(
                        "'", "h"
                    ):
                        keys.append(key)
                        cosigners.append(cosigner)
                        cosigner_found = True
                        break
                if cosigner_found:
                    break
            if not cosigner_found:
                desc_key = Key.parse_xpub(
                    "[{}{}]{}".format(
                        self.origin_fingerprint[i],
                        self.origin_path[i],
                        self.base_key[i],
                    )
                )
                if len(cosigners_types) > i:
                    unknown_cosigners.append((desc_key, cosigners_types[i]["label"]))
                else:
                    unknown_cosigners.append((desc_key, None))
                if len(unknown_cosigners) > len(cosigners_types):
                    unknown_cosigners_types.append("other")
                else:
                    unknown_cosigners_types.append(cosigners_types[i]["type"])

        return (keys, cosigners, unknown_cosigners, unknown_cosigners_types)


def sort_descriptor(descriptor, index=None):
    """
    Sorts descriptor to maintain compatibility with Core 19
    as it doesn't support sortedmulti.
    Returns a derived multi() descriptor with sorted xpubs inside.
    """
    desc = Descriptor.parse(descriptor)
    desc.sort_keys = True
    sorted_desc = desc.derive(index, keep_xpubs=True)
    sorted_desc.sort_keys = False
    return sorted_desc.serialize()
