import re

# From: https://github.com/bitcoin/bitcoin/blob/master/src/script/descriptor.cpp


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

        if origin_path and not isinstance(origin_path, list):
            self.m_path_base = "m" + origin_path
            self.m_path = "m" + origin_path + (path_suffix or "")

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

        # Check the checksum
        check_split = desc.split("#")
        if len(check_split) > 2:
            return None
        if len(check_split) == 2:
            if len(check_split[1]) != 8:
                return None
            checksum = DescriptorChecksum(check_split[0])
            if not checksum.strip():
                return None
            if checksum != check_split[1]:
                return None
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
            if "sortedmulti" in desc:
                keys.sort(key=lambda x: x if "]" not in x else x.split("]")[1])
            multisig_M = desc.split(",")[0].split("(")[-1]
            multisig_N = len(keys)
        else:
            keys = [desc.split("(")[-1].split(")", 1)[0]]

        descriptors = []
        for key in keys:
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
            )

    def serialize(self):
        descriptor_open = "pkh("
        descriptor_close = ")"
        origin = ""
        path_suffix = ""

        if self.wpkh:
            descriptor_open = "wpkh("
        elif self.sh_wpkh:
            descriptor_open = "sh(wpkh("
            descriptor_close = "))"
        elif self.sh or self.sh_wsh or self.wsh:
            # serialize multisig descriptor is not supported yet.
            return None

        if self.origin_fingerprint and self.origin_path:
            origin = "[" + self.origin_fingerprint + self.origin_path + "]"

        if self.path_suffix:
            path_suffix = self.path_suffix

        return AddChecksum(
            descriptor_open + origin + self.base_key + path_suffix + descriptor_close
        )
