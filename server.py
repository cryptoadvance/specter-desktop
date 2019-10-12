import sys, json, os, time, base64
import requests
import random, copy
from collections import OrderedDict
from threading import Thread

from flask import Flask, render_template, request, redirect
from flask_qrcode import QRcode

from helpers import normalize_xpubs, run_shell
from descriptor import AddChecksum
from rpc import BitcoinCLI, RPC_PORTS

from specter import Specter, purposes, addrtypes
from datetime import datetime
import urllib

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)
QRcode(app) # enable qr codes generation

DATA_FOLDER = "~/.specter"

rand = random.randint(0, 1e32) # to force style refresh

MSIG_TYPES = {
    "legacy": "P2SH",
    "p2sh-segwit": "P2SH_P2WSH",
    "bech32": "P2WSH"
}
SINGLE_TYPES = {
    "legacy": "P2PKH",
    "p2sh-segwit": "P2SH_P2WPKH",
    "bech32": "P2WPKH"
}


################ routes ####################

@app.route('/combine/', methods=['GET', 'POST'])
def combine():
    if request.method == 'POST': # FIXME: ugly...
        d = request.json
        psbt0 = d['psbt0'] # request.args.get('psbt0')
        psbt1 = d['psbt1'] # request.args.get('psbt1')
        psbt = specter.combine([psbt0, psbt1])
        raw = specter.finalize(psbt)
        if "hex" in raw:
            specter.broadcast(raw["hex"])
        return json.dumps(raw)
    return 'meh'

@app.route('/')
def index():
    specter.check()
    if len(specter.wallets) > 0:
        return redirect("/wallets/%s" % specter.wallets[specter.wallets.names()[0]]["alias"])
    # TODO: add onboarding process
    return render_template("base.html", specter=specter, rand=rand)

@app.route('/settings/', methods=['GET', 'POST'])
def settings():
    specter.check()
    rpc = specter.config["rpc"]
    user = rpc["user"]
    passwd = rpc["password"]
    port = rpc["port"]
    host = rpc["host"]
    test = None
    if request.method == 'POST':
        user = request.form['username']
        passwd = request.form['password']
        port = request.form['port']
        host = request.form["host"]
        action = request.form['action']

        if action == "test":
            test = specter.test_rpc(user=user, password=passwd, port=port, host=host, autodetect=False)
        if action == "save":
            specter.update_rpc(user=user, password=passwd, port=port, host=host, autodetect=False)
            specter.check()
            return redirect("/")
    else:
        pass
    return render_template("settings.html", test=test, username=user, password=passwd, port=port, host=host, specter=specter, rand=rand)

################# wallet management #####################

@app.route('/new_wallet/')
def new_wallet():
    specter.check()
    err = None
    if specter.chain is None:
        err = "Configure Bitcoin Core to create wallets"
        return render_template("base.html", error=err, specter=specter, rand=rand)
    return render_template("new_wallet.html", specter=specter, rand=rand)

@app.route('/new_wallet/simple/', methods=['GET', 'POST'])
def new_wallet_simple():
    specter.check()
    name = "Simple"
    wallet_name = name
    i = 2
    err = None
    while wallet_name in specter.wallets.names():
        wallet_name = "%s %d" % (name, i)
        i+=1
    device = None
    if request.method == 'POST':
        action = request.form['action']
        wallet_name = request.form['wallet_name']
        if wallet_name in specter.wallets.names():
            err = "Wallet already exists"
        if "device" not in request.form:
            err = "Select the device"
        else:
            device_name = request.form['device']
        wallet_type = request.form['type']
        if action == 'device' and err is None:
            dev = copy.deepcopy(specter.devices[device_name])
            prefix = "tpub"
            if specter.chain == "main":
                prefix = "xpub"
            allowed_types = [None, wallet_type]
            dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and k["type"] in allowed_types]
            pur = {
                None: "General",
                "wpkh": "Segwit (bech32)",
                "sh-wpkh": "Nested Segwit",
                "pkh": "Legacy",
            }
            return render_template("new_simple_keys.html", purposes=pur, wallet_type=wallet_type, wallet_name=wallet_name, device=dev, error=err, specter=specter, rand=rand)
        if action == 'key' and err is None:
            original_xpub = request.form['key']
            device = specter.devices[device_name]
            key = None
            for k in device["keys"]:
                if k["original"] == original_xpub:
                    key = k
                    break
            if key is None:
                return render_template("base.html", error="Key not found", specter=specter, rand=rand)
            # create a wallet here
            wallet = specter.wallets.create_simple(wallet_name, wallet_type, key, device)
            return redirect("/wallets/%s/" % wallet["alias"])
    return render_template("new_simple.html", wallet_name=wallet_name, device=device, error=err, specter=specter, rand=rand)

@app.route('/new_wallet/multisig/', methods=['GET', 'POST'])
def new_wallet_multi():
    specter.check()
    name = "Multisig"
    wallet_type = "wsh"
    wallet_name = name
    i = 2
    err = None
    while wallet_name in specter.wallets.names():
        wallet_name = "%s %d" % (name, i)
        i+=1
    device = None

    sigs_total = len(specter.devices)
    if sigs_total < 2:
        err = "You need more devices to do multisig"
        return render_template("base.html", specter=specter, rand=rand)
    sigs_required = sigs_total*2//3
    if sigs_required < 2:
        sigs_required = 2
    cosigner_index = 0
    cosigners = []
    keys = []

    if request.method == 'POST':
        print(request.form)
        action = request.form['action']
        wallet_name = request.form['wallet_name']
        cosigner_index = int(request.form['cosigner_index'])
        sigs_required = int(request.form['sigs_required'])
        sigs_total = int(request.form['sigs_total'])
        if wallet_name in specter.wallets.names():
            err = "Wallet already exists"
        wallet_type = request.form['type']
        for i in range(0, cosigner_index):
            cosigners.append(request.form['cosigner%d' % i])
        pur = {
            None: "General",
            "wsh": "Segwit (bech32)",
            "sh-wsh": "Nested Segwit",
            "sh": "Legacy",
        }
        if action == 'device' and err is None:
            if "device" not in request.form:
                err = "Select the device"
            else:
                device_name = request.form['device']
            if err is None:
                cosigner_index += 1
                cosigners.append(request.form["device"])
            print(cosigners, len(cosigners), sigs_required)
            if len(cosigners) == sigs_total:
                devs = []
                prefix = "tpub"
                if specter.chain == "main":
                    prefix = "xpub"
                for k in cosigners:
                    dev = copy.deepcopy(specter.devices[k])
                    dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and (k["type"] is None or k["type"] == wallet_type)]
                    if len(dev["keys"]) == 0:
                        err = "Device %s doesn't have keys matching this wallet type" % dev["name"]
                    devs.append(dev)
                return render_template("new_simple_keys.html", purposes=pur, 
                    wallet_type=wallet_type, wallet_name=wallet_name, 
                    cosigners=devs, keys=keys, sigs_required=sigs_required, 
                    sigs_total=sigs_total, cosigner_index=cosigner_index, 
                    error=err, specter=specter, rand=rand)
        if action == 'key' and err is None:
            cosigners = [specter.devices[k] for k in cosigners]
            for i in range(0, cosigner_index):
                try:
                    key = request.form['key%d' % i]
                    for k in cosigners[i]["keys"]:
                        if k["original"] == key:
                            keys.append(k)
                            break
                except:
                    pass
                devs = []
            if len(keys) != sigs_total or len(cosigners) != sigs_total:
                prefix = "tpub"
                if specter.chain == "main":
                    prefix = "xpub"
                for k in cosigners:
                    dev = copy.deepcopy(k)
                    dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and (k["type"] is None or k["type"] == wallet_type)]
                    devs.append(dev)
                err="Did you select all the keys?"
                return render_template("new_simple_keys.html", purposes=pur, 
                    wallet_type=wallet_type, wallet_name=wallet_name, 
                    cosigners=devs, keys=keys, sigs_required=sigs_required, 
                    sigs_total=sigs_total, cosigner_index=cosigner_index, 
                    error=err, specter=specter, rand=rand)
            # create a wallet here
            wallet = specter.wallets.create_multi(wallet_name, sigs_required, wallet_type, keys, cosigners)
            return redirect("/wallets/%s/" % wallet["alias"])
    return render_template("new_simple.html", cosigners=cosigners, wallet_type=wallet_type, wallet_name=wallet_name, device=device, error=err, sigs_required=sigs_required, sigs_total=sigs_total, cosigner_index=cosigner_index, specter=specter, rand=rand)

@app.route('/wallets/<wallet_alias>/')
def wallet(wallet_alias):
    specter.check()
    try:
        wallet = specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=specter, rand=rand)
    print(wallet.balance["untrusted_pending"] + wallet.balance["trusted"])
    if wallet.balance["untrusted_pending"] + wallet.balance["trusted"] == 0:
        return redirect("/wallets/%s/receive/" % wallet_alias)
    else:
        return redirect("/wallets/%s/tx/" % wallet_alias)

@app.route('/wallets/<wallet_alias>/tx/')
def wallet_tx(wallet_alias):
    specter.check()
    try:
        wallet = specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=specter, rand=rand)
    return render_template("wallet_tx.html", wallet_alias=wallet_alias, wallet=wallet, specter=specter, rand=rand)

@app.route('/wallets/<wallet_alias>/receive/', methods=['GET', 'POST'])
def wallet_receive(wallet_alias):
    specter.check()
    try:
        wallet = specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == "newaddress":
            wallet.getnewaddress()
    return render_template("wallet_receive.html", wallet_alias=wallet_alias, wallet=wallet, specter=specter, rand=rand)

@app.route('/wallets/<wallet_alias>/send/', methods=['GET', 'POST'])
def wallet_send(wallet_alias):
    specter.check()
    try:
        wallet = specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=specter, rand=rand)
    psbt = None
    address = ""
    amount = 0
    err = None
    if request.method == "POST":
        action = request.form['action']
        if action == "createpsbt":
            address = request.form['address']
            amount = float(request.form['amount'])
            # try:
            psbt = wallet.createpsbt(address, amount)
            if psbt is None:
                err = "Probably you don't have enough funds, or something else..."
            # except Exception as e:
            #     print(e)
            #     err = wallet.geterror()
            #     if err is None:
            #         err = "Unknown error"
            #     print(err, e)
    return render_template("wallet_send.html", psbt=psbt, address=address, amount=amount, wallet_alias=wallet_alias, wallet=wallet, specter=specter, rand=rand)

@app.route('/wallets/<wallet_alias>/settings/')
def wallet_settings(wallet_alias):
    specter.check()
    try:
        wallet = specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=specter, rand=rand)
    cc_file = None
    if wallet.is_multisig():
        CC_TYPES = {
        'legacy': 'BIP45',
        'p2sh-segwit': 'P2WSH-P2SH',
        'bech32': 'P2WSH'
        }
        cc_file = """# Coldcard Multisig setup file (created on Specter Desktop)
#
Name: {}
Policy: {} of {}
Derivation: {}
Format: {}
""".format(wallet['name'], wallet['sigs_required'], 
            len(wallet['keys']), wallet['keys'][0]["derivation"].replace("h","'"),
            CC_TYPES[wallet['address_type']]
            )
        for k in wallet['keys']:
            cc_file += "{}: {}\n".format(k['fingerprint'].upper(), k['xpub'])
        qr_text = "name={}\ntype={}\nm={}\nn={}".format(wallet["name"], MSIG_TYPES[wallet['address_type']], wallet['sigs_required'], len(wallet['keys']))
        for k in wallet['keys']:
            qr_text += "\n[{}{}]{}".format(k['fingerprint'], k['derivation'][1:], k['xpub'])
        return render_template("wallet_settings.html", 
                            cc_file=urllib.parse.quote(cc_file), 
                            wallet_alias=wallet_alias, wallet=wallet, 
                            specter=specter, rand=rand, 
                            qr_text=qr_text)
    else:
        qr_text = "name={}\ntype={}".format(wallet["name"], SINGLE_TYPES[wallet['address_type']])
        k = wallet["key"]
        qr_text += "\n[{}{}]{}".format(k['fingerprint'], k['derivation'][1:], k['xpub'])
        return render_template("wallet_settings.html", 
                            wallet_alias=wallet_alias, wallet=wallet, 
                            specter=specter, rand=rand, 
                            qr_text=qr_text)

################# devices management #####################

@app.route('/new_device/')
def new_device():
    specter.check()
    return render_template("new_device.html", specter=specter, rand=rand)

@app.route('/new_device/<device_type>/', methods=['GET', 'POST'])
def new_device_xpubs(device_type):
    err = None
    specter.check()
    # get default new name
    name = device_type.capitalize()
    device_name = name
    i = 2
    while device_name in specter.devices.names():
        device_name = "%s %d" % (name, i)
        i+=1

    xpubs = ""
    if request.method == 'POST':
        device_name = request.form['device_name']
        if device_name in specter.devices.names():
            err = "Device with this name already exists"
        xpubs = request.form['xpubs']
        normalized, parsed, failed = normalize_xpubs(xpubs)
        if len(failed) > 0:
            err = "Failed to parse these xpubs:\n" + "\n".join(failed)
        if err is None:
            dev = specter.devices.add(name=device_name, device_type=device_type, keys=normalized)
            return redirect("/devices/%s/" % dev["alias"])
    return render_template("new_device_xpubs.html", device_type=device_type, device_name=device_name, xpubs=xpubs, error=err, specter=specter, rand=rand)

def get_key_meta(key):
    k = copy.deepcopy(key)
    k["chain"] = "Mainnet" if k["xpub"].startswith("xpub") else "Testnet"
    k["purpose"] = purposes[k["type"]]
    if k["derivation"] is not None:
        k["combined"] = "[%s%s]%s" % (k["fingerprint"], k["derivation"][1:], k["xpub"])
    else:
        k["combined"] = k["xpub"]
    return k

@app.route('/devices/<device_alias>/', methods=['GET', 'POST'])
def device(device_alias):
    specter.check()
    try:
        device = specter.devices.get_by_alias(device_alias)
    except:
        return render_template("base.html", error="Device not found", specter=specter, rand=rand)
    if request.method == 'POST':
        action = request.form['action']
        if action == "forget":
            specter.devices.remove(device)
            return redirect("/")
        if action == "delete_key":
            key = request.form['key']
            device.remove_key(key)
        if action == "add_keys":
            return render_template("new_device_xpubs.html", device_alias=device_alias, device=device, device_type=device["type"], specter=specter, rand=rand)
        if action == "morekeys":
            # refactor to fn
            xpubs = request.form['xpubs']
            normalized, parsed, failed = normalize_xpubs(xpubs)
            err = None
            if len(failed) > 0:
                err = "Failed to parse these xpubs:\n" + "\n".join(failed)
                return render_template("new_device_xpubs.html", device_alias=device_alias, device=device, xpubs=xpubs, device_type=device["type"], error=err, specter=specter, rand=rand)
            if err is None:
                device.add_keys(normalized)
    device = copy.deepcopy(device)
    device["keys"] = [get_key_meta(key) for key in device["keys"]]
    device["keys"].sort(key=lambda x: x["chain"]+x["purpose"], reverse=True)
    return render_template("device.html", device_alias=device_alias, device=device, purposes=purposes, specter=specter, rand=rand)

############### filters ##################

@app.template_filter('datetime')
def timedatetime(s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")

@app.template_filter('derivation')
def derivation(wallet):
    s = "address=m/0/{}\n".format(wallet['address_index'])
    if wallet.is_multisig():
        s += "type={}".format(MSIG_TYPES[wallet['address_type']])
        for k in wallet['keys']:
            s += "\n{}{}".format(k['fingerprint'], k['derivation'][1:])
    else:
        s += "type={}".format(SINGLE_TYPES[wallet['address_type']])
        k = wallet['key']
        s += "\n{}{}".format(k['fingerprint'], k['derivation'][1:])
    return s
    # d = wallet["recv_descriptor"].split("#")[0].replace("*",str(wallet["address_index"]))
    # if wallet.is_multisig():
    #     for k in wallet["keys"]:
    #         d = d.replace(k["xpub"],"m")
    # else:
    #     d = d.replace(wallet["key"]["xpub"],"m")
    #     pass
    # return d

@app.template_filter('txonaddr')
def txonaddr(wallet):
    addr = wallet["address"]
    txlist = [tx for tx in wallet.transactions if tx["address"] == addr]
    return len(txlist)

@app.template_filter('prettyjson')
def txonaddr(obj):
    return json.dumps(obj, indent=4)


############### startup ##################

if __name__ == '__main__':
    debug = False
    specter = Specter(DATA_FOLDER)
    specter.check()

    # watch templates folder to reload when something changes
    extra_dirs = ['templates']
    extra_files = extra_dirs[:]
    for extra_dir in extra_dirs:
        for dirname, dirs, files in os.walk(extra_dir):
            for filename in files:
                filename = os.path.join(dirname, filename)
                if os.path.isfile(filename):
                    extra_files.append(filename)

    app.run(port=25441, debug=debug, extra_files=extra_files)
