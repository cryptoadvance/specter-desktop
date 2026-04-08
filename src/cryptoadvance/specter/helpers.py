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
from embit.script import Script
from embit.psbt import PSBT
from embit.transaction import Transaction
from embit.liquid.pset import PSET
from embit.liquid.transaction import LTransaction
from embit.liquid.networks import NETWORKS
from .persistence import read_json_file, write_json_file
from .util.bcur import bcur_decode
import threading
from io import BytesIO
import re

logger = logging.getLogger(__name__)

# default lock for @locked()
defaultlock = threading.Lock()

EMOJIS = "😀😃😄😁😆😅😂🤣😊😇🙂🙃😉😌😍😘😗😙😚😋😜😝😛🤑🤗🤓😎🤡🤠😏😒😞😔😟😕🙁😣😖😫😩😤😠😡😶😐😑😯😦😧😮😲😵😳😱😨😰😢😥🤤😭😓😪😴🙄🤔🤥😬🤐🤢🤧😷🤒🤕😈👿👹👺💩👻💀☠️👽👾🤖🎃😺😸😹😻😼😽🙀😿😾👐🙌👏🙏🤝👍👎👊✊🤛🤜🤞✌️🤘👌👈👉👆👇☝️✋🤚🖐🖖👋🤙💪🖕✍️🤳💅🖖💄💋👄👅👂👃👣👁👀🗣👤👥👶👦👧👨👩👱👴👵👲👳👮👷💂🕵️👩‍⚕️👨‍⚕️👩‍🌾👨‍🌾👩‍🍳👨‍🍳👩‍🎓👨‍🎓👩‍🎤👨‍🎤👩‍🏫👨‍🏫👩‍🏭👨‍🏭👩‍💻👨‍💻👩‍💼👨‍💼👩‍🔧👨‍🔧👩‍🔬👨‍🔬👩‍🎨👨‍🎨👩‍🚒👨‍🚒👩‍✈️👨‍✈️👩‍🚀👨‍🚀👩‍⚖️👨‍⚖️🤶🎅👸🤴👰🤵👼🤰🙇💁🙅🙆🙋🙎🙍💇💆🕴💃🕺👯🚶🏃👫👭👬💑👩‍❤️‍👩👨‍❤️‍👨💏👩‍❤️‍💋‍👩👨‍❤️‍💋‍👨👪👨‍👩‍👧👨‍👩‍👧‍👦👨‍👩‍👦‍👦👨‍👩‍👧‍👧👩‍👩‍👦👩‍👩‍👧👩‍👩‍👧‍👦👩‍👩‍👦‍👦👩‍👩‍👧‍👧👨‍👨‍👦👨‍👨‍👧👨‍👨‍👧‍👦👨‍👨‍👦‍👦👨‍👨‍👧‍👧👩‍👦👩‍👧👩‍👧‍👦👩‍👦‍👦👩‍👧‍👧👨‍👦👨‍👧👨‍👧‍👦👨‍👦‍👦👨‍👧‍👧👚👕👖👔👗👙👘👠👡👢👞👟👒🎩🎓👑⛑🎒👝👛👜💼👓🕶🌂☂️🐶🐱🐭🐹🐰🦊🐻🐼🐨🐯🦁🐮🐷🐽🐸🐵🙊🙉🙊🐒🐔🐧🐦🐤🐣🐥🦆🦅🦉🦇🐺🐗🐴🦄🐝🐛🦋🐌🐚🐞🐜🕷🕸🐢🐍🦎🦂🦀🦑🐙🦐🐠🐟🐡🐬🦈🐳🐋🐊🐆🐅🐃🐂🐄🦌🐪🐫🐘🦏🦍🐎🐖🐐🐏🐑🐕🐩🐈🐓🦃🕊🐇🐁🐀🐿🐾🐉🐲🌵🎄🌲🌳🌴🌱🌿☘️🍀🎍🎋🍃🍂🍁🍄🌾💐🌷🌹🥀🌻🌼🌸🌺🌎🌍🌏🌕🌖🌗🌘🌑🌒🌓🌔🌚🌝🌞🌛🌜🌙💫⭐️🌟✨⚡️🔥💥☄️☀️🌤⛅️🌥🌦🌈☁️🌧⛈🌩🌨☃️⛄️❄️🌬💨🌪🌫🌊💧💦☔️🍏🍎🍐🍊🍋🍌🍉🍇🍓🍈🍒🍑🍍🥝🥑🍅🍆🥒🥕🌽🌶🥔🍠🌰🥜🍯🥐🍞🥖🧀🥚🍳🥓🥞🍤🍗🍖🍕🌭🍔🍟🥙🌮🌯🥗🥘🍝🍜🍲🍥🍣🍱🍛🍚🍙🍘🍢🍡🍧🍨🍦🍰🎂🍮🍭🍬🍫🍿🍩🍪🥛🍼☕️🍵🍶🍺🍻🥂🍷🥃🍸🍹🍾🥄🍴🍽⚽️🏀🏈⚾️🎾🏐🏉🎱🏓🏸🥅🏒🏑🏏⛳️🏹🎣🥊🥋⛸🎿⛷🏂🏋️🤺⛹️🏌️🏄🏊🚣🏇🚴🚵🎽🏅🎖🥇🥈🥉🏆🏵🎗🎫🎟🎪🎭🎨🎬🎤🎧🎼🎹🥁🎷🎺🎸🎻🎲🎯🎳🎮🎰🚗🚕🚙🚌🚎🏎🚓🚑🚒🚐🚚🚛🚜🛴🚲🛵🏍🚨🚔🚍🚘🚖🚡🚠🚟🚃🚋🚞🚝🚄🚅🚈🚂🚆🚇🚊🚉🚁🛩✈️🛫🛬🚀🛰💺🛶⛵️🛥🚤🛳⛴🚢⚓️🚧⛽️🚏🚦🚥🗺🗿🗽⛲️🗼🏰🏯🏟🎡🎢🎠⛱🏖🏝⛰🏔🗻🌋🏜🏕⛺️🛤🛣🏗🏭🏠🏡🏘🏚🏢🏬🏣🏤🏥🏦🏨🏪🏫🏩💒🏛⛪️🕌🕍🕋⛩🗾🎑🏞🌅🌄🌠🎇🎆🌇🌆🏙🌃🌌🌉🌁⌚️📱📲💻⌨️🖥🖨🖱🖲🕹🗜💽💾💿📀📼📷📸📹🎥📽🎞📞☎️📟📠📺📻🎙🎚🎛⏱⏲⏰🕰⌛️⏳📡🔋🔌💡🔦🕯🗑🛢💸💵💴💶💷💰💳💎⚖️🔧🔨⚒🛠⛏🔩⚙️⛓🔫💣🔪🗡⚔️🛡🚬⚰️⚱️🏺🔮📿💈⚗️🔭🔬🕳💊💉🌡🚽🚰🚿🛁🛀🛎🔑🗝🚪🛋🛏🛌🖼🛍🛒🎁🎈🎏🎀🎊🎉🎎🏮🎐✉️📩📨📧💌📥📤📦🏷📪📫📬📭📮📯📜📃📄📑📊📈📉🗒🗓📆📅📇🗃🗳🗄📋📁📂🗂🗞📰📓📔📒📕📗📘📙📚📖🔖🔗📎🖇📐📏📌📍📌🎌🏳️🏴🏁🏳️‍🌈✂️🖊🖋✒️🖌🖍📝✏️🔍🔎🔏🔐🔒🔓❤️💛💚💙💜🖤💔❣️💕💞💓💗💖💘💝🔈🔇🔉🔊🔔🔕📣📢👁‍🗨💬"


def get_asset_label(asset, known_assets={}):
    # TODO: lookup in the registry
    if asset in [None, "00" * 32, "ff" * 32]:
        return "???"
    if asset == "bitcoin":
        return "LBTC"
    if asset in known_assets:
        return known_assets[asset]
    icon = ""
    try:
        n = int.from_bytes(bytes.fromhex(asset), "little") % len(EMOJIS)
        icon = EMOJIS[n : n + 1]
    except:
        pass
    if len(asset) > 16:
        return f"{icon}"
    return asset


def add_dicts(target, item):
    for k, v in item.items():
        if isinstance(v, dict):
            target[k] = add_dicts(target.get(k, {}), v)
        else:
            # this will add ints, floats, strings etc
            target[k] = target.get(k, type(v)()) + v
    return target


def is_testnet(chain):
    return chain not in ["main", "liquidv1", "None", "none", None, ""]


def is_liquid(chain):
    return chain in ["liquidv1", "liquidtestnet", "elementsregtest", "elreg"]


def normalize_address(addr: str) -> str:
    """
    Normalized address to canonical form.
    Upper bech32 -> lower bech32, but doesn't touch base58 addresses.
    """
    # bitcoin hrps
    hrps = {net["bech32"] + "1" for net in NETWORKS.values()}
    # liquid hrps
    # Blech32 addresses are intended for confidential assets
    hrps = hrps.union(
        {net["blech32"] + "1" for net in NETWORKS.values() if "blech32" in net}
    )
    if addr.lower().startswith(tuple(hrps)):
        return addr.lower()
    return addr


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
    # ascii characters have codes from 0 to 127
    # but 127 is "delete" and we don't want it
    return "".join([c for c in name if ord(c) < 127])[:20]


def create_unique_id(name):
    """
    Create a filesystem-friendly unique ID from a string.
    Leading and trailing whitespaces are removed.
    Replaces space(s) and hyphen(s) with one underscore.
    Keeps only alphanumeric chars and returns in lowercase.
    """
    name = name.strip().replace(" ", "_").replace("-", "_")
    while "__" in name:
        name = name.replace("__", "_")
    return "".join(x for x in name if x.isalnum() or x == "_").lower()


def fullpath(data_folder, name):
    """Quick way to get a fullpath which usually"""
    return os.path.join(data_folder, f"{create_unique_id(name)}.json")


def calc_fullpath(data_folder, name):
    """Get a fullpath for a Businessobject with a name quickly"""
    return os.path.join(data_folder, f"{create_unique_id(name)}.json")


def deep_update(d, u):
    """updates the dict d with the dict u
    in short: second argument wins
    """
    for k, v in six.iteritems(u):
        dv = d.get(k, {})
        if not isinstance(dv, collections.abc.Mapping):
            d[k] = v
        elif isinstance(v, collections.abc.Mapping):
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
            logger.error(
                f"Exception while loading json file {os.path.join(folder, fname)}"
            )
            logger.exception(e)
    return dd


def set_loglevel(app, loglevel_string):
    logger.info(
        "Setting Loglevel to %s (Check the next log-line(s) whether it's effective here)"
        % loglevel_string
    )
    loglevels = {"WARN": logging.WARN, "INFO": logging.INFO, "DEBUG": logging.DEBUG}
    logging.getLogger("cryptoadvance").setLevel(loglevels[loglevel_string])
    logger.warning("Loglevel-Test: This is a warn-message!")
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
    if not is_testnet(app.specter.chain):
        prefix = "xpub"
    for cosigner in cosigners:
        device = copy.deepcopy(cosigner)
        allowed_types = ["", wallet_type]
        if wallet_type == "simple":
            allowed_types += ["sh-wpkh", "wpkh", "tr"]
        elif wallet_type == "multisig":
            allowed_types += ["sh-wsh", "wsh"]
        device.keys = sorted(
            [
                key
                for key in device.keys
                if key.xpub.startswith(prefix)
                and (key.key_type in allowed_types or wallet_type == "*")
            ],
            key=lambda k: k.original == k.xpub,
        )
        devices.append(device)
    return devices


def clean_psbt(b64psbt):
    try:
        psbt = PSBT.from_string(b64psbt)
    except:
        psbt = PSET.from_string(b64psbt)
    for inp in psbt.inputs:
        if inp.witness_utxo is not None and inp.non_witness_utxo is not None:
            inp.non_witness_utxo = None
    return psbt.to_string()


def bcur2base64(encoded):
    raw = bcur_decode(encoded.split("/")[-1])
    return binascii.b2a_base64(raw).strip()


def get_txid(tx):
    try:
        t = Transaction.from_string(tx)
    except:
        t = LTransaction.from_string(tx)
    for inp in t.vin:
        inp.scriptSig = Script(b"")
    return t.txid().hex()


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


def notify_upgrade(app, flash):
    """If a new version is available, notifies the user via flash
    that there is an upgrade to specter.desktop
    :return the current version
    """
    if app.specter.version.upgrade:
        flash(
            f"Upgrade notification: new version {app.specter.version.latest} is available.",
            "info",
        )
    return app.specter.version.current


def is_ip_private(ip):
    # https://en.wikipedia.org/wiki/Private_network
    priv_lo = re.compile(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_24 = re.compile(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    priv_20 = re.compile(r"^192\.168\.\d{1,3}.\d{1,3}$")
    priv_16 = re.compile(r"^172.(1[6-9]|2[0-9]|3[0-1]).[0-9]{1,3}.[0-9]{1,3}$")

    res = (
        ip == "localhost"
        or priv_lo.match(ip)
        or priv_24.match(ip)
        or priv_20.match(ip)
        or priv_16.match(ip)
    )
    return res is not None


def get_address_from_dict(data_dict):
    # TODO: Remove this helper function in favor of simple ["address"]
    # when support for Bitcoin Core version < 22 is dropped
    addr = data_dict.get("addresses")
    if not addr:
        addr = data_dict.get("scriptPubKey", {}).get("addresses")
    if addr:
        addr = addr[0]
    if not addr:
        addr = data_dict.get("address")
    if addr and addr != "Fee":
        return addr
    raise RuntimeError(f"Missing address info in object {data_dict}")


def is_relative_url(url):
    # Decode percent-encoded characters so encoded control/whitespace cannot
    # bypass validation, e.g. /%09/baidu.com -> "/\t/baidu.com".
    from urllib.parse import unquote

    normalized = unquote(url)

    if not normalized or not normalized.startswith("/"):
        return False
    # Reject protocol-relative URLs after decoding.
    if normalized.startswith("//"):
        return False
    # Reject any decoded control characters or whitespace anywhere in the URL,
    # including ASCII DEL (0x7f), since browsers may normalize them in unsafe
    # ways.
    if any(ord(c) < 32 or ord(c) == 127 or c.isspace() for c in normalized):
        return False
    # Reject backslashes to avoid alternate path separator confusion.
    if "\\" in normalized:
        return False

    return True
