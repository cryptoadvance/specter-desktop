import binascii, collections, copy, hashlib, hmac, json, logging, os, six, subprocess, sys
from collections import OrderedDict
from mnemonic import Mnemonic
from hwilib.descriptor import AddChecksum
from hwilib.serializations import PSBT, CTransaction
from .bcur import bcur_decode
import threading
from io import BytesIO
import re

logger = logging.getLogger(__name__)

# use this for all fs operations
fslock = threading.Lock()

def locked(customlock=fslock):
    """
    @locked(lock) decorator.
    Make sure you are not calling 
    @locked function from another @locked function
    with the same lock argument.
    """
    def wrapper(fn):
        def wrapper_fn(*args, **kwargs):
            with customlock:
                return fn(*args, **kwargs)
        return wrapper_fn
    return wrapper

try:
    collectionsAbc = collections.abc
except:
    collectionsAbc = collections


def alias(name):
    name = name.replace(" ", "_")
    return "".join(x for x in name if x.isalnum() or x=="_").lower()


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
        with fslock:
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


def double_sha256(s):
    return hashlib.sha256(hashlib.sha256(s).digest()).digest()


def hash160(d):
    return hashlib.new('ripemd160', hashlib.sha256(d).digest()).digest()


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


def get_xpub_fingerprint(xpub):
    b = decode_base58(xpub)
    return hash160(b[-33:])[:4]


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
            logger.debug("Found %s executable in %s" % (program, exec_location))
            return exec_location

    fpath, program_name = os.path.split(program)
    if fpath:
        if is_exe(program):
            logger.debug("Found %s executable in %s" % (program, program))
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                logger.debug("Found %s executable in %s" % (program, path))
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


def set_loglevel(app, loglevel_string):
    logger.info("Setting Loglevel to %s" % loglevel_string)
    loglevels = {
        "WARN": logging.WARN,
        "INFO": logging.INFO,
        "DEBUG" : logging.DEBUG
    }
    app.logger.setLevel(loglevels[loglevel_string])
    logger.setLevel(loglevels[loglevel_string])


def get_loglevel(app):
    loglevels = {
        logging.WARN : "WARN",
        logging.INFO : "INFO",
        logging.DEBUG : "DEBUG"
    }
    return loglevels[app.logger.getEffectiveLevel()]


def get_version_info():
    ''' Returns a triple of the current version (of the pip-package cryptoadvance.specter and 
        the latest version and whether you should upgrade 
    '''
    name="cryptoadvance.specter"
    try:
        # fail right away if it's a binary
        if getattr(sys, 'frozen', False):
            raise RuntimeError("Using frozen binary, verision unavailable")
        latest_version = str(subprocess.run([sys.executable, '-m', 'pip', 'install', '{}==random'.format(name)], capture_output=True, text=True))
        latest_version = latest_version[latest_version.find('(from versions:')+15:]
        latest_version = latest_version[:latest_version.find(')')]
        latest_version = latest_version.replace(' ','').split(',')[-1]

        current_version = str(subprocess.run([sys.executable, '-m', 'pip', 'show', '{}'.format(name)], capture_output=True, text=True))
        current_version = current_version[current_version.find('Version:')+8:]
        current_version = current_version[:current_version.find('\\n')].replace(' ','')
        # master?
        if not re.search(r"v([\d+]).([\d+]).([\d+]).*", current_version):
            return current_version, latest_version, False
        return current_version, latest_version, latest_version != current_version
    except:
        # if pip is not installed or we are using python3.6 or below
        # we just don't show the version
        return "Unknown version", "Unknown version", False


def get_users_json(specter):
    users = [
        {
            'id': 'admin',
            'username': 'admin',
            'password': hash_password('admin'),
            'is_admin': True
        }
    ]

    # if users.json file exists - load from it
    if os.path.isfile(os.path.join(specter.data_folder, "users.json")):
        with fslock:
            with open(os.path.join(specter.data_folder, "users.json"), "r") as f:
                users = json.loads(f.read())
    # otherwise - create one and assign unique id
    else:
        save_users_json(specter, users)
    return users


def save_users_json(specter, users):
    with fslock:
        with open(os.path.join(specter.data_folder, 'users.json'), "w") as f:
            f.write(json.dumps(users, indent=4))


def hwi_get_config(specter):
    config = {
        'whitelisted_domains': 'http://127.0.0.1:25441/'
    }
    # if hwi_bridge_config.json file exists - load from it
    if os.path.isfile(os.path.join(specter.data_folder, "hwi_bridge_config.json")):
        with fslock:
            with open(os.path.join(specter.data_folder, "hwi_bridge_config.json"), "r") as f:
                file_config = json.loads(f.read())
                deep_update(config, file_config)
    # otherwise - create one and assign unique id
    else:
        save_hwi_bridge_config(specter, config)
    return config


def save_hwi_bridge_config(specter, config):
    if 'whitelisted_domains' in config:
        whitelisted_domains = ''
        for url in config['whitelisted_domains'].split():
            if not url.endswith("/") and url != '*':
                # make sure the url end with a "/"
                url += "/"
            whitelisted_domains += url.strip() + '\n'
        config['whitelisted_domains'] = whitelisted_domains
    with fslock:
        with open(os.path.join(specter.data_folder, 'hwi_bridge_config.json'), "w") as f:
            f.write(json.dumps(config, indent=4))


def der_to_bytes(derivation):
    items = derivation.split("/")
    if len(items) == 0:
        return b''
    if items[0] == 'm':
        items = items[1:]
    if items[-1] == '':
        items = items[:-1]
    res = b''
    for item in items:
        index = 0
        if item[-1] == 'h' or item[-1] == "'":
            index += 0x80000000
            item = item[:-1]
        index += int(item)
        res += index.to_bytes(4,'little')
    return res


def get_devices_with_keys_by_type(app, cosigners, wallet_type):
    devices = []
    prefix = "tpub"
    if app.specter.chain == "main":
        prefix = "xpub"
    for cosigner in cosigners:
        device = copy.deepcopy(cosigner)
        allowed_types = ['', wallet_type]
        device.keys = [key for key in device.keys if key.xpub.startswith(prefix) and key.key_type in allowed_types]
        devices.append(device)
    return devices


def sort_descriptor(cli, descriptor, index=None, change=False):
    descriptor = descriptor.replace("sortedmulti", "multi")
    if index is not None:
        descriptor = descriptor.replace("*", f"{index}")
    # remove checksum
    descriptor = descriptor.split("#")[0]
    # get address (should be already imported to the wallet)
    address = cli.deriveaddresses(AddChecksum(descriptor), change=change)[0]

    # get pubkeys involved
    address_info = cli.getaddressinfo(address)
    if 'pubkeys' in address_info:
        pubkeys = address_info["pubkeys"]
    elif 'embedded' in address_info and 'pubkeys' in address_info['embedded']:
        pubkeys = address_info["embedded"]["pubkeys"]
    else:
        raise Exception("Could not find 'pubkeys' in address info:\n%s" % json.dumps(address_info, indent=2))

    # get xpubs from the descriptor
    arr = descriptor.split("(multi(")[1].split(")")[0].split(",")

    # getting [wsh] or [sh, wsh]
    prefix = descriptor.split("(multi(")[0].split("(")
    sigs_required = arr[0]
    keys = arr[1:]

    # sort them according to sortedmulti
    z = sorted(zip(pubkeys,keys), key=lambda x: x[0])
    keys = [zz[1] for zz in z]
    inner = f"{sigs_required},"+",".join(keys)
    desc = f"multi({inner})"

    # Write from the inside out
    prefix.reverse()
    for p in prefix:
        desc = f"{p}({desc})"

    return AddChecksum(desc)


def hash_password(password):
    """Hash a password for storing."""
    salt = binascii.b2a_base64(hashlib.sha256(os.urandom(60)).digest()).strip()
    pwdhash = binascii.b2a_base64(hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 10000)).strip().decode()
    return { 'salt': salt.decode(), 'pwdhash': pwdhash }


def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    pwdhash = hashlib.pbkdf2_hmac('sha256', 
                                  provided_password.encode('utf-8'), 
                                  stored_password['salt'].encode(), 
                                  10000)
    return pwdhash == binascii.a2b_base64(stored_password['pwdhash'])


def clean_psbt(b64psbt):
    psbt = PSBT()
    psbt.deserialize(b64psbt)
    for inp in psbt.inputs:
        if inp.witness_utxo is not None and inp.non_witness_utxo is not None:
            inp.non_witness_utxo = None
    return psbt.serialize()


def bcur2base64(encoded):
    raw = bcur_decode(encoded.split("/")[-1])
    return binascii.b2a_base64(raw).strip()


def get_txid(tx):
    b = BytesIO(bytes.fromhex(tx))
    t = CTransaction()
    t.deserialize(b)
    for inp in t.vin:
        inp.scriptSig = b""
    t.rehash()
    return t.hash


def get_startblock_by_chain(specter):
    if specter.info['chain'] == "main":
        if not specter.info['pruned'] or specter.info['pruneheight'] < 481824:
            startblock = 481824
        else:
            startblock = specter.info['pruneheight']
    else:
        if not specter.info['pruned']:
            startblock = 0
        else:
            startblock = specter.info['pruneheight']
    return startblock


# Hot wallet helpers
def generate_mnemonic(strength=256):
        # Generate words list
        mnemo = Mnemonic("english")
        words = mnemo.generate(strength=strength)
        return words


# Transaction processing helpers
def parse_utxo(wallet, utxo):
    for tx in utxo:
        tx_data = wallet.cli.gettransaction(tx['txid'])
        tx['time'] = tx_data['time']
        if (len(tx_data['details']) > 1):
            for details in tx_data['details']:
                if details['category'] != 'send':
                    tx['category'] = details['category']
                    break
        else:    
            tx['category'] = tx_data['details'][0]['category']
        if 'confirmations' in tx_data:
            tx['confirmations'] = tx_data['confirmations']
        else:
            tx['confirmations'] = 0
    return utxo
