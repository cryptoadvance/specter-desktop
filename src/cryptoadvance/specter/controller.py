import sys, json, os, time, base64
import requests
import random, copy
from collections import OrderedDict
from threading import Thread


from functools import wraps
from flask import g, request, redirect, url_for

from flask import Flask, Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, login_user, logout_user, current_user
from flask_login.config import EXEMPT_METHODS
from flask_qrcode import QRcode


from .helpers import normalize_xpubs, run_shell
from .descriptor import AddChecksum
from .rpc import BitcoinCLI, RPC_PORTS

from .logic import Specter, purposes, addrtypes, get_cli
from datetime import datetime
import urllib

from pathlib import Path
env_path = Path('.') / '.flaskenv'
from dotenv import load_dotenv
load_dotenv(env_path)

DEBUG = True

from flask import current_app as app
rand = random.randint(0, 1e32) # to force style refresh


################ routes ####################

@app.route('/combine/', methods=['GET', 'POST'])
@login_required
def combine():
    if request.method == 'POST': # FIXME: ugly...
        d = request.json
        psbt0 = d['psbt0'] # request.args.get('psbt0')
        psbt1 = d['psbt1'] # request.args.get('psbt1')
        psbt = app.specter.combine([psbt0, psbt1])
        raw = app.specter.finalize(psbt)
        if "hex" in raw:
            app.specter.broadcast(raw["hex"])
        return json.dumps(raw)
    return 'meh'

@app.route('/')
@login_required
def index():
    app.specter.check()
    if len(app.specter.wallets) > 0:
        return redirect("/wallets/%s" % app.specter.wallets[app.specter.wallets.names()[0]]["alias"])

    # TODO: add onboarding process
    if not app.specter.devices:
        # For now: can't do anything until a device is registered
        return redirect("/new_device/")

    return render_template("base.html", specter=app.specter, rand=rand)

@app.route('/login', methods=['GET', 'POST'])
def login():
    ''' login '''
    app.specter.check()
    if request.method == 'POST': 
        # ToDo: check the password via RPC-call
        if app.specter.cli is None:
            flash("We could not check your password, maybe Bitcoin Core is not running or not configured?","error")
            app.logger.info("AUDIT: Failed to check password")
            return render_template('login.html', specter=app.specter, data={'controller':'controller.login'}), 401
        cli = app.specter.cli.clone()
        print("Loggning in with"+request.form['password'])
        cli.passwd = request.form['password']
        if cli.test_connection():
            app.login()
            app.logger.info("AUDIT: Successfull Login via RPC-credentials")
            flash('Logged in successfully.',"info")
            if request.form.get('next') and request.form.get('next').startswith("http"):
                response = redirect(request.form['next'])
            else:
                response = redirect(url_for('index'))
            return response
        else:
            flash('Invalid username or password', "error")
            app.logger.info("AUDIT: Invalid password login attempt")
            return render_template('login.html', specter=app.specter, data={'controller':'controller.login'}), 401
    else:
        if app.config.get('LOGIN_DISABLED'):
            return redirect('/')
        return render_template('login.html', specter=app.specter, data={'next':request.args.get('next')})

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    flash('You were logged out',"info")
    return redirect("/login") 

@app.route('/settings/', methods=['GET', 'POST'])
@login_required
def settings():
    app.specter.check()
    rpc = app.specter.config['rpc']
    user = rpc['user']
    passwd = rpc['password']
    port = rpc['port']
    host = rpc['host']
    protocol = 'http'
    auth = app.specter.config["auth"]
    if "protocol" in rpc:
        protocol = rpc["protocol"]
    test = None
    if request.method == 'POST':
        user = request.form['username']
        passwd = request.form['password']
        port = request.form['port']
        host = request.form['host']
        auth = request.form['auth']
        action = request.form['action']
        # protocol://host
        if "://" in host:
            arr = host.split("://")
            protocol = arr[0]
            host = arr[1]

        if action == "test":
            test = app.specter.test_rpc(user=user,
                                        password=passwd,
                                        port=port,
                                        host=host,
                                        protocol=protocol,
                                        autodetect=False
                                        )
        if action == "save":
            app.specter.update_rpc( user=user,
                                    password=passwd,
                                    port=port,
                                    host=host,
                                    protocol=protocol,
                                    autodetect=False
                                    )
            app.specter.update_auth(auth)
            if auth == "rpcpasswordaspin":
                app.config['LOGIN_DISABLED'] = False
            else:
                app.config['LOGIN_DISABLED'] = True
            app.specter.check()
            return redirect("/")
    else:
        pass
    return render_template("settings.html",
                            test=test,
                            username=user,
                            password=passwd,
                            port=port,
                            host=host,
                            protocol=protocol,
                            auth=auth,
                            specter=app.specter,
                            rand=rand)

################# wallet management #####################

@app.route('/new_wallet/')
@login_required
def new_wallet():
    app.specter.check()
    err = None
    if app.specter.chain is None:
        err = "Configure Bitcoin Core to create wallets"
        return render_template("base.html", error=err, specter=app.specter, rand=rand)
    return render_template("new_wallet.html", specter=app.specter, rand=rand)

@app.route('/new_wallet/simple/', methods=['GET', 'POST'])
@login_required
def new_wallet_simple():
    app.specter.check()
    name = "Simple"
    wallet_name = name
    i = 2
    err = None
    while wallet_name in app.specter.wallets.names():
        wallet_name = "%s %d" % (name, i)
        i+=1
    device = None
    if request.method == 'POST':
        action = request.form['action']
        wallet_name = request.form['wallet_name']
        if wallet_name in app.specter.wallets.names():
            err = "Wallet already exists"
        if "device" not in request.form:
            err = "Select the device"
        else:
            device_name = request.form['device']
        wallet_type = request.form['type']
        if action == 'device' and err is None:
            dev = copy.deepcopy(app.specter.devices[device_name])
            prefix = "tpub"
            if app.specter.chain == "main":
                prefix = "xpub"
            allowed_types = [None, wallet_type]
            dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and k["type"] in allowed_types]
            pur = {
                None: "General",
                "wpkh": "Segwit (bech32)",
                "sh-wpkh": "Nested Segwit",
                "pkh": "Legacy",
            }
            return render_template("new_simple_keys.html", purposes=pur, wallet_type=wallet_type, wallet_name=wallet_name, device=dev, error=err, specter=app.specter, rand=rand)
        if action == 'key' and err is None:
            original_xpub = request.form['key']
            device = app.specter.devices[device_name]
            key = None
            for k in device["keys"]:
                if k["original"] == original_xpub:
                    key = k
                    break
            if key is None:
                return render_template("base.html", error="Key not found", specter=app.specter, rand=rand)
            # create a wallet here
            wallet = app.specter.wallets.create_simple(wallet_name, wallet_type, key, device)
            return redirect("/wallets/%s/" % wallet["alias"])
    return render_template("new_simple.html", wallet_name=wallet_name, device=device, error=err, specter=app.specter, rand=rand)

@app.route('/new_wallet/multisig/', methods=['GET', 'POST'])
@login_required
def new_wallet_multi():
    app.specter.check()
    name = "Multisig"
    wallet_type = "wsh"
    wallet_name = name
    i = 2
    err = None
    while wallet_name in app.specter.wallets.names():
        wallet_name = "%s %d" % (name, i)
        i+=1

    sigs_total = len(app.specter.devices)
    if sigs_total < 2:
        err = "You need more devices to do multisig"
        return render_template("base.html", specter=app.specter, rand=rand)
    sigs_required = sigs_total*2//3
    if sigs_required < 2:
        sigs_required = 2
    cosigners = []
    keys = []

    if request.method == 'POST':
        action = request.form['action']
        wallet_name = request.form['wallet_name']
        sigs_required = int(request.form['sigs_required'])
        sigs_total = int(request.form['sigs_total'])
        if wallet_name in app.specter.wallets.names():
            err = "Wallet already exists"
        wallet_type = request.form['type']
        pur = {
            None: "General",
            "wsh": "Segwit (bech32)",
            "sh-wsh": "Nested Segwit",
            "sh": "Legacy",
        }
        if action == 'device' and err is None:
            cosigners = request.form.getlist('devices')
            if len(cosigners) != sigs_total:
                err = "Select all the cosigners"
            else:
                devs = []
                prefix = "tpub"
                if app.specter.chain == "main":
                    prefix = "xpub"
                for k in cosigners:
                    dev = copy.deepcopy(app.specter.devices[k])
                    dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and (k["type"] is None or k["type"] == wallet_type)]
                    if len(dev["keys"]) == 0:
                        err = "Device %s doesn't have keys matching this wallet type" % dev["name"]
                    devs.append(dev)
                return render_template("new_simple_keys.html", purposes=pur, 
                    wallet_type=wallet_type, wallet_name=wallet_name, 
                    cosigners=devs, keys=keys, sigs_required=sigs_required, 
                    sigs_total=sigs_total, 
                    error=err, specter=app.specter, rand=rand)
        if action == 'key' and err is None:
            cosigners = []
            devs = []
            for i in range(sigs_total):
                try:
                    key = request.form['key%d' % i]
                    cosigner_name = request.form['cosigner%d' % i]
                    cosigner = app.specter.devices[cosigner_name]
                    cosigners.append(cosigner)
                    for k in cosigner["keys"]:
                        if k["original"] == key:
                            keys.append(k)
                            break
                except:
                    pass
            print(keys, cosigners)
            if len(keys) != sigs_total or len(cosigners) != sigs_total:
                prefix = "tpub"
                if app.specter.chain == "main":
                    prefix = "xpub"
                for k in cosigners:
                    dev = copy.deepcopy(k)
                    dev["keys"] = [k for k in dev["keys"] if k["xpub"].startswith(prefix) and (k["type"] is None or k["type"] == wallet_type)]
                    devs.append(dev)
                err="Did you select all the keys?"
                return render_template("new_simple_keys.html", purposes=pur, 
                    wallet_type=wallet_type, wallet_name=wallet_name, 
                    cosigners=devs, keys=keys, sigs_required=sigs_required, 
                    sigs_total=sigs_total, 
                    error=err, specter=app.specter, rand=rand)
            # create a wallet here
            wallet = app.specter.wallets.create_multi(wallet_name, sigs_required, wallet_type, keys, cosigners)
            return redirect("/wallets/%s/" % wallet["alias"])
    return render_template("new_simple.html", cosigners=cosigners, wallet_type=wallet_type, wallet_name=wallet_name, error=err, sigs_required=sigs_required, sigs_total=sigs_total, specter=app.specter, rand=rand)

@app.route('/wallets/<wallet_alias>/')
@login_required
def wallet(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=app.specter, rand=rand)
    if wallet.balance["untrusted_pending"] + wallet.balance["trusted"] == 0:
        return redirect("/wallets/%s/receive/" % wallet_alias)
    else:
        return redirect("/wallets/%s/tx/" % wallet_alias)

@app.route('/wallets/<wallet_alias>/tx/')
@login_required
def wallet_tx(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=app.specter, rand=rand)
    return render_template("wallet_tx.html", wallet_alias=wallet_alias, wallet=wallet, specter=app.specter, rand=rand)

@app.route('/wallets/<wallet_alias>/receive/', methods=['GET', 'POST'])
@login_required
def wallet_receive(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == "newaddress":
            wallet.getnewaddress()
    return render_template("wallet_receive.html", wallet_alias=wallet_alias, wallet=wallet, specter=app.specter, rand=rand)

@app.route('/get_fee/<blocks>')
@login_required
def fees(blocks):
    res = app.specter.estimatesmartfee(int(blocks))
    return res

@app.route('/wallets/<wallet_alias>/send/', methods=['GET', 'POST'])
@login_required
def wallet_send(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallets.get_by_alias(wallet_alias)
    except Exception as e:
        print(e)
        return render_template("base.html", error="Wallet not found", specter=app.specter, rand=rand)
    psbt = None
    address = ""
    amount = 0
    fee_rate = 0.0
    err = None
    if request.method == "POST":
        action = request.form['action']
        if action == "createpsbt":
            address = request.form['address']
            amount = float(request.form['amount'])
            subtract = bool(request.form.get("subtract", False))
            fee_unit = request.form.get('fee_unit')

            if 'dynamic' in request.form.get('fee_options'):
                fee_rate = float(request.form.get('fee_rate_dynamic'))
            else:
                if request.form.get('fee_rate'):
                    fee_rate = float(request.form.get('fee_rate'))

            try:
                psbt = wallet.createpsbt(address, amount, subtract=subtract, fee_rate=fee_rate, fee_unit=fee_unit)
                if psbt is None:
                    err = "Probably you don't have enough funds, or something else..."
                else:
                    # calculate new amount if we need to subtract
                    if subtract:
                        for v in psbt["tx"]["vout"]:
                            if address in v["scriptPubKey"]["addresses"]:
                                amount = v["value"]
            except Exception as e:
                err = "%r" % e
    return render_template("wallet_send.html", psbt=psbt, address=address, amount=amount, 
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter, rand=rand, error=err)

@app.route('/wallets/<wallet_alias>/settings/', methods=['GET','POST'])
@login_required
def wallet_settings(wallet_alias):
    app.specter.check()
    error = None
    try:
        wallet = app.specter.wallets.get_by_alias(wallet_alias)
    except:
        return render_template("base.html", error="Wallet not found", specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == "rescanblockchain":
            startblock = int(request.form['startblock'])
            try:
                res = wallet.cli.rescanblockchain(startblock, timeout=1)
                print(res)
            except requests.exceptions.ReadTimeout:
                pass
            except Exception as e:
                print(e)
                error = "%r" % e
            wallet.getdata()
        elif action == "abortrescan":
            res = wallet.cli.abortrescan()
            if not res:
                error="Failed to abort rescan. Maybe already complete?"
            wallet.getdata()
        elif action == "keypoolrefill":
            delta = int(request.form['keypooladd'])
            wallet.keypoolrefill(wallet["keypool"], wallet["keypool"]+delta)
            wallet.keypoolrefill(wallet["change_keypool"], wallet["change_keypool"]+delta, change=True)
            wallet.getdata()

    cc_file = None
    qr_text = wallet["name"]+"&"+descr(wallet)
    if wallet.is_multisig:
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
        return render_template("wallet_settings.html", 
                            cc_file=urllib.parse.quote(cc_file), 
                            wallet_alias=wallet_alias, wallet=wallet, 
                            specter=app.specter, rand=rand, 
                            error=error,
                            qr_text=qr_text)
    else:
        return render_template("wallet_settings.html", 
                            wallet_alias=wallet_alias, wallet=wallet, 
                            specter=app.specter, rand=rand, 
                            error=error,
                            qr_text=qr_text)

################# devices management #####################

@app.route('/new_device/')
@login_required
def new_device():
    app.specter.check()
    return render_template("new_device.html", specter=app.specter, rand=rand)

@app.route('/new_device/<device_type>/', methods=['GET', 'POST'])
@login_required
def new_device_xpubs(device_type):
    err = None
    app.specter.check()
    # get default new name
    name = device_type.capitalize()
    device_name = name
    i = 2
    while device_name in app.specter.devices.names():
        device_name = "%s %d" % (name, i)
        i+=1

    xpubs = ""
    if request.method == 'POST':
        device_name = request.form['device_name']
        if device_name in app.specter.devices.names():
            err = "Device with this name already exists"
        xpubs = request.form['xpubs']
        normalized, parsed, failed = normalize_xpubs(xpubs)
        if len(failed) > 0:
            err = "Failed to parse these xpubs:\n" + "\n".join(failed)
        if err is None:
            dev = app.specter.devices.add(name=device_name, device_type=device_type, keys=normalized)
            return redirect("/devices/%s/" % dev["alias"])
    return render_template("new_device_xpubs.html", device_type=device_type, device_name=device_name, xpubs=xpubs, error=err, specter=app.specter, rand=rand)


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
@login_required
def device(device_alias):
    app.specter.check()
    try:
        device = app.specter.devices.get_by_alias(device_alias)
    except:
        return render_template("base.html", error="Device not found", specter=app.specter, rand=rand)
    if request.method == 'POST':
        action = request.form['action']
        if action == "forget":
            app.specter.devices.remove(device)
            return redirect("/")
        if action == "delete_key":
            key = request.form['key']
            device.remove_key(key)
        if action == "add_keys":
            return render_template("new_device_xpubs.html", device_alias=device_alias, device=device, device_type=device["type"], specter=app.specter, rand=rand)
        if action == "morekeys":
            # refactor to fn
            xpubs = request.form['xpubs']
            normalized, parsed, failed = normalize_xpubs(xpubs)
            err = None
            if len(failed) > 0:
                err = "Failed to parse these xpubs:\n" + "\n".join(failed)
                return render_template("new_device_xpubs.html", device_alias=device_alias, device=device, xpubs=xpubs, device_type=device["type"], error=err, specter=app.specter, rand=rand)
            if err is None:
                device.add_keys(normalized)
    device = copy.deepcopy(device)
    device["keys"] = [get_key_meta(key) for key in device["keys"]]
    device["keys"].sort(key=lambda x: x["chain"]+x["purpose"], reverse=True)
    return render_template("device.html", device_alias=device_alias, device=device, purposes=purposes, specter=app.specter, rand=rand)



############### filters ##################

@app.template_filter('datetime')
def timedatetime(s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")

@app.template_filter('derivation')
def derivation(wallet):
    s = "address=m/0/{}\n".format(wallet['address_index'])
    if wallet.is_multisig:
        s += "type={}".format(MSIG_TYPES[wallet['address_type']])
        for k in wallet['keys']:
            s += "\n{}{}".format(k['fingerprint'], k['derivation'][1:])
    else:
        s += "type={}".format(SINGLE_TYPES[wallet['address_type']])
        k = wallet['key']
        s += "\n{}{}".format(k['fingerprint'], k['derivation'][1:])
    return s

@app.template_filter('txonaddr')
def txonaddr(wallet):
    addr = wallet["address"]
    txlist = [tx for tx in wallet.transactions if tx["address"] == addr]
    return len(txlist)

@app.template_filter('prettyjson')
def txonaddr(obj):
    return json.dumps(obj, indent=4)

@app.template_filter('descriptor')
def descr(wallet):
    # we always use sortedmulti even though it is not in Bitcoin Core yet
    return wallet['recv_descriptor'].split("#")[0].replace("/0/*", "").replace("multi", "sortedmulti")


    