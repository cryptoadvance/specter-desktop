import collections
import hashlib
import json
import logging
import os
import subprocess
import sys
from collections import OrderedDict

import six

try:
    collectionsAbc = collections.abc
except:
    collectionsAbc = collections

def deep_update(d, u):
    for k, v in six.iteritems(u):
        dv = d.get(k, {})
        if not isinstance(dv, collectionsAbc.Mapping):
            d[k] = v
        elif isinstance(v, collectionsAbc.Mapping):
            d[k] = deep_update(dv, v)
        else:
            d[k] = v
    return d

def load_jsons(folder, key=None):
    files = [f for f in os.listdir(folder) if f.endswith(".json")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)))
    dd = OrderedDict()
    for fname in files:
        with open(os.path.join(folder, fname)) as f:
            d = json.loads(f.read())
        if key is None:
            dd[fname[:-5]] = d
        else:
            d["fullpath"] = os.path.join(folder, fname)
            d["alias"] = fname[:-5]
            dd[d[key]] = d
    return dd

BASE58_ALPHABET = b'123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

VALID_PREFIXES = {
    b"\x04\x35\x87\xcf": {   # testnet
        b"\x04\x35\x87\xcf": None, # unknown, maybe pkh
        b"\x04\x4a\x52\x62": "sh-wpkh",
        b"\x04\x5f\x1c\xf6": "wpkh",
        b"\x02\x42\x89\xef": "sh-wsh",
        b"\x02\x57\x54\x83": "wsh",
    },
    b"\x04\x88\xb2\x1e": {   # mainnet
        b"\x04\x88\xb2\x1e": None, #unknown, maybe pkh
        b"\x04\x9d\x7c\xb2": "sh-wpkh",
        b"\x04\xb2\x47\x46": "wpkh",
        b"\x02\x95\xb4\x3f": "sh-wsh",
        b"\x02\xaa\x7e\xd3": "wsh",
    }
}

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
    prefix = b'1' * count
    # convert from binary to hex, then hex to integer
    num = int.from_bytes(s, 'big')
    result = bytearray()
    while num > 0:
        num, mod = divmod(num, 58)
        result.insert(0, BASE58_ALPHABET[mod])

    return prefix + bytes(result)

def encode_base58_checksum(s):
    return encode_base58(s + double_sha256(s)[:4]).decode('ascii')

def decode_base58(s, num_bytes=82, strip_leading_zeros=False):
    num = 0
    for c in s.encode('ascii'):
        num *= 58
        num += BASE58_ALPHABET.index(c)
    combined = num.to_bytes(num_bytes, byteorder='big')
    if strip_leading_zeros:
        while combined[0] == 0:
            combined = combined[1:]
    checksum = combined[-4:]
    if double_sha256(combined[:-4])[:4] != checksum:
        raise ValueError('bad address: {} {}'.format(
            checksum, double_sha256(combined)[:4]))
    return combined[:-4]

def convert_xpub_prefix(xpub, prefix_bytes):
    # Update xpub to specified prefix and re-encode
    b = decode_base58(xpub)
    return encode_base58_checksum(prefix_bytes + b[4:])

def parse_xpub(xpub):
    r = {"derivation": None}
    derivation = None
    arr = xpub.strip().split("]")
    r["original"] = arr[-1]
    if len(arr) > 1:
        derivation = arr[0].replace("'","h").lower()
        xpub = arr[1]
    if derivation is not None:
        if derivation[0]!="[":
            raise Exception("Missing leading [")
        arr = derivation[1:].split("/")
        try: 
            fng = bytes.fromhex(arr[0].replace("-","")) # coldcard has hexstrings like 7c-2c-8e-1b
        except:
            raise Exception("Fingerprint is not hex")
        if len(fng) != 4:
            raise Exception("Incorrect fingerprint length")
        r["fingerprint"] = arr[0]
        for der in arr[1:]:
            if der[-1] == "h":
                der = der[:-1]
            try:
                i = int(der)
            except:
                print("index")
                raise Exception("Incorrect index")
            arr[0] = "m"
            r["derivation"] = "/".join(arr)
    # checking xpub prefix and defining key type
    b = decode_base58(xpub, num_bytes=82)
    prefix = b[:4]
    is_valid = False
    key_type = None
    for k in VALID_PREFIXES:
        if prefix in VALID_PREFIXES[k].keys():
            key_type = VALID_PREFIXES[k][prefix]
            prefix = k
            is_valid = True
            break
    if not is_valid:
        raise Exception("Invalid xpub prefix: %s", prefix.hex())

    # defining key type from derivation
    if r["derivation"] is not None and key_type is None:
        arr = r["derivation"].split("/")
        purpose = arr[1]
        if purpose == "44h":
            key_type = "pkh"
        elif purpose == "49h":
            key_type = "sh-wpkh"
        elif purpose == "84h":
            key_type = "wpkh"
        elif purpose == "45h":
            key_type = "sh"
        elif purpose == "48h":
            if len(arr)>=5:
                if arr[4] == "1h":
                    key_type = "sh-wsh"
                elif arr[4] == "2h":
                    key_type = "wsh"
    r["type"] = key_type

    b = prefix + b[4:]
    r["xpub"] = encode_base58_checksum(b)
    return r

def normalize_xpubs(xpubs):
    xpubs = xpubs
    lines = [l.strip() for l in xpubs.split("\n") if len(l) > 0]
    parsed = []
    failed = []
    normalized = []
    for line in lines:
        try:
            x = parse_xpub(line)
            normalized.append(x)
            parsed.append(line)
        except Exception as e:
            failed.append(line + "\n" + str(e))
    return (normalized, parsed, failed)


def which(program):
    ''' mimics the "which" command in bash but even for stuff not on the path.
        Also has implicit pyinstaller support 
        Place your executables like --add-binary '.env/bin/hwi:.'
        ... and they will be found.
        returns a full path of the executable and if a full path is passed,
        it will simply return it if found and executable
        will raise an Exception if not found
    '''
    
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    if getattr(sys, 'frozen', False):
        # Best understood with the snippet below this section:
        # https://pyinstaller.readthedocs.io/en/v3.3.1/runtime-information.html#using-sys-executable-and-sys-argv-0
        exec_location = os.path.join(sys._MEIPASS, program)
        if is_exe(exec_location):
            logging.info("Found %s executable in %s" % (program, exec_location))
            return exec_location

    fpath, program_name = os.path.split(program)
    if fpath:
        if is_exe(program):
            logging.info("Found %s executable in %s" % (program, program))
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                logging.info("Found %s executable in %s" % (program, path))
                return exe_file
    raise Exception("Couldn't find executable %s" % program)

# should work in all python versions
def run_shell(cmd):
    """
    Runs a shell command. 
    Example: run(["ls", "-a"])
    Returns: dict({"code": returncode, "out": stdout, "err": stderr})
    """
    try:
        proc = subprocess.Popen(cmd,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
        )
        stdout, stderr = proc.communicate()
        return { "code": proc.returncode, "out": stdout, "err": stderr }
    except:
        return { "code": 0xf00dbabe, "out": b"", "err": b"Can't run subprocess" }
