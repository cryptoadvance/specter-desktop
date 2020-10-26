import binascii
import collections
import copy
import hashlib
import hmac
import json
import logging
import os
import six
import subprocess
import sys
from collections import OrderedDict
from mnemonic import Mnemonic
from hwilib.serializations import PSBT, CTransaction
from .persistence import read_json_file, write_json_file
from .util.descriptor import AddChecksum
from .util.bcur import bcur_decode
import threading
from io import BytesIO
import re

logger = logging.getLogger(__name__)

# default lock for @locked()
defaultlock = threading.Lock()


def locked(customlock=defaultlock):
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


def to_ascii20(name: str) -> str:
    """
    Converts the name to max 20 ascii-only characters.
    """
    return "".join([c for c in name if c.isascii()])[:20]


def alias(name):
    """
    Create a filesystem-friendly alias from a string.
    Replaces space with _ and keeps only alphanumeric chars.
    """
    name = name.replace(" ", "_")
    return "".join(x for x in name if x.isalnum() or x == "_").lower()


def deep_update(d, u):
    for k, v in six.iteritems(u):
        dv = d.get(k, {})
        if not isinstance(dv, collections.Mapping):
            d[k] = v
        elif isinstance(v, collections.Mapping):
            d[k] = deep_update(dv, v)
        else:
            d[k] = v
    return d


def load_jsons(folder, key=None):
    # get all json files (not hidden)
    files = [
        f for f in os.listdir(folder) if f.endswith(".json") and not f.startswith(".")
    ]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(folder, x)))
    dd = OrderedDict()
    for fname in files:
        try:
            d = read_json_file(os.path.join(folder, fname))
            if key is None:
                dd[fname[:-5]] = d
            else:
                d["fullpath"] = os.path.join(folder, fname)
                d["alias"] = fname[:-5]
                dd[d[key]] = d
        except Exception as e:
            logger.error(f"Can't load json file {fname} at path {folder} because {e}")
    return dd


def set_loglevel(app, loglevel_string):
    logger.info(
        "Setting Loglevel to %s (Check the next log-line(s) whether it's effective here)"
        % loglevel_string
    )
    loglevels = {"WARN": logging.WARN, "INFO": logging.INFO, "DEBUG": logging.DEBUG}
    logging.getLogger().setLevel(loglevels[loglevel_string])
    logger.warn("Loglevel-Test: This is a warn-message!")
    logger.info("Loglevel-Test: This is an info-message!")
    logger.debug("Loglevel-Test: This is an debug-message!")


def get_loglevel(app):
    loglevels = {logging.WARN: "WARN", logging.INFO: "INFO", logging.DEBUG: "DEBUG"}
    return loglevels[app.logger.getEffectiveLevel()]


def hwi_get_config(specter):
    config = {"whitelisted_domains": "http://127.0.0.1:25441/"}
    # if hwi_bridge_config.json file exists - load from it
    if os.path.isfile(os.path.join(specter.data_folder, "hwi_bridge_config.json")):
        fname = os.path.join(specter.data_folder, "hwi_bridge_config.json")
        file_config = read_json_file(fname)
        deep_update(config, file_config)
    # otherwise - create one and assign unique id
    else:
        save_hwi_bridge_config(specter, config)
    return config


def save_hwi_bridge_config(specter, config):
    if "whitelisted_domains" in config:
        whitelisted_domains = ""
        for url in config["whitelisted_domains"].split():
            if not url.endswith("/") and url != "*":
                # make sure the url end with a "/"
                url += "/"
            whitelisted_domains += url.strip() + "\n"
        config["whitelisted_domains"] = whitelisted_domains
    fname = os.path.join(specter.data_folder, "hwi_bridge_config.json")
    write_json_file(config, fname)


def der_to_bytes(derivation):
    items = derivation.split("/")
    if len(items) == 0:
        return b""
    if items[0] == "m":
        items = items[1:]
    if len(items) > 0 and items[-1] == "":
        items = items[:-1]
    res = b""
    for item in items:
        index = 0
        if item[-1] == "h" or item[-1] == "'":
            index += 0x80000000
            item = item[:-1]
        index += int(item)
        res += index.to_bytes(4, "little")
    return res


def get_devices_with_keys_by_type(app, cosigners, wallet_type):
    devices = []
    prefix = "tpub"
    if app.specter.chain == "main":
        prefix = "xpub"
    for cosigner in cosigners:
        device = copy.deepcopy(cosigner)
        allowed_types = ["", wallet_type]
        device.keys = [
            key
            for key in device.keys
            if key.xpub.startswith(prefix) and key.key_type in allowed_types
        ]
        devices.append(device)
    return devices


def sort_descriptor(rpc, descriptor, index=None, change=False):
    descriptor = descriptor.replace("sortedmulti", "multi")
    if index is not None:
        descriptor = descriptor.replace("*", f"{index}")
    # remove checksum
    descriptor = descriptor.split("#")[0]
    # get address (should be already imported to the wallet)
    address = rpc.deriveaddresses(AddChecksum(descriptor), change=change)[0]

    # get pubkeys involved
    address_info = rpc.getaddressinfo(address)
    if "pubkeys" in address_info:
        pubkeys = address_info["pubkeys"]
    elif "embedded" in address_info and "pubkeys" in address_info["embedded"]:
        pubkeys = address_info["embedded"]["pubkeys"]
    else:
        raise Exception(
            "Could not find 'pubkeys' in address info:\n%s"
            % json.dumps(address_info, indent=2)
        )

    # get xpubs from the descriptor
    arr = descriptor.split("(multi(")[1].split(")")[0].split(",")

    # getting [wsh] or [sh, wsh]
    prefix = descriptor.split("(multi(")[0].split("(")
    sigs_required = arr[0]
    keys = arr[1:]

    # sort them according to sortedmulti
    z = sorted(zip(pubkeys, keys), key=lambda x: x[0])
    keys = [zz[1] for zz in z]
    inner = f"{sigs_required}," + ",".join(keys)
    desc = f"multi({inner})"

    # Write from the inside out
    prefix.reverse()
    for p in prefix:
        desc = f"{p}({desc})"

    return AddChecksum(desc)


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
    if specter.info["chain"] == "main":
        if not specter.info["pruned"] or specter.info["pruneheight"] < 481824:
            startblock = 481824
        else:
            startblock = specter.info["pruneheight"]
    else:
        if not specter.info["pruned"]:
            startblock = 0
        else:
            startblock = specter.info["pruneheight"]
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
        tx_data = wallet.rpc.gettransaction(tx["txid"])
        tx["time"] = tx_data["time"]
        if len(tx_data["details"]) > 1:
            for details in tx_data["details"]:
                if details["category"] != "send":
                    tx["category"] = details["category"]
                    break
        else:
            tx["category"] = tx_data["details"][0]["category"]
        if "confirmations" in tx_data:
            tx["confirmations"] = tx_data["confirmations"]
        else:
            tx["confirmations"] = 0
    return utxo
