import ast, sys, json, os, time, base64
import requests
import random, copy
from collections import OrderedDict
from threading import Thread
from .key import Key

from functools import wraps
from flask import g, request, redirect, url_for

from flask import Flask, Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, login_user, logout_user, current_user
from flask_login.config import EXEMPT_METHODS


from .helpers import (alias, get_devices_with_keys_by_type, hash_password, 
                      get_loglevel, get_version_info, run_shell, set_loglevel, 
                      verify_password, bcur2base64)
from .specter import Specter
from .specter_error import SpecterError
from .wallet_manager import purposes
from .rpc import RpcError
from .user import User
from datetime import datetime
import urllib

from pathlib import Path
env_path = Path('.') / '.flaskenv'
from dotenv import load_dotenv
load_dotenv(env_path)

from flask import current_app as app
rand = random.randint(0, 1e32) # to force style refresh

@app.before_request
def selfcheck():
    """check status before every request"""
    if app.config.get('LOGIN_DISABLED'):
        app.login('admin')

########## template injections #############
@app.context_processor
def inject_debug():
    ''' Can be used in all jinja2 templates '''
    return dict(debug=app.config['DEBUG'])

################ routes ####################
@app.route('/wallets/<wallet_alias>/combine/', methods=['GET', 'POST'])
@login_required
def combine(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while combine: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == 'POST': # FIXME: ugly...
        psbt0 = request.form.get('psbt0') # request.args.get('psbt0')
        psbt1 = request.form.get('psbt1') # request.args.get('psbt1')
        if "UR:BYTES/" in psbt0:
            psbt0 = bcur2base64(psbt0)
        if "UR:BYTES/" in psbt1:
            psbt1 = bcur2base64(psbt1)
        txid = request.form.get('txid')

        try:
            psbt = app.specter.combine([psbt0, psbt1])
            raw = app.specter.finalize(psbt)
            if "psbt" not in raw:
                raw["psbt"] = psbt
        except RpcError as e:
            return e.error_msg, e.status_code
        except Exception as e:
            return "Unknown error: %r" % e, 500
        psbt = wallet.update_pending_psbt(psbt, txid, raw)
        devices = []
        # we get names, but need aliases
        if "devices_signed" in psbt:
            devices = [dev.alias for dev in wallet.devices if dev.name in psbt["devices_signed"]]
        raw["devices"] = devices
        return json.dumps(raw)
    return 'meh'

@app.route('/wallets/<wallet_alias>/broadcast/', methods=['GET', 'POST'])
@login_required
def broadcast(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while broadcast: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == 'POST':
        tx = request.form.get('tx')
        res = wallet.cli.testmempoolaccept([tx])[0]
        if res['allowed']:
            app.specter.broadcast(tx)
            wallet.delete_pending_psbt(wallet.cli.decoderawtransaction(tx)['txid'])
            return jsonify(success=True)
        else:
            return jsonify(success=False, error="Failed to broadcast transaction: transaction is invalid\n%s" % res["reject-reason"])
    return jsonify(success=False, error="broadcast tx request must use POST")

@app.route('/')
@login_required
def index():
    notify_upgrade()
    app.specter.check()
    if len(app.specter.wallet_manager.wallets) > 0:
        return redirect("/wallets/%s" % app.specter.wallet_manager.wallets[app.specter.wallet_manager.wallets_names[0]].alias)

    # TODO: add onboarding process
    if len(app.specter.device_manager.devices) == 0:
        # For now: can't do anything until a device is registered
        return redirect("/new_device/")

    return render_template("base.jinja", specter=app.specter, rand=rand)

@app.route('/login', methods=['GET', 'POST'])
def login():
    ''' login '''
    app.specter.check()
    if request.method == 'POST':
        if app.specter.config['auth'] == 'none':
            app.login('admin')
            app.logger.info("AUDIT: Successfull Login no credentials")
            return redirect_login(request)
        if app.specter.config['auth'] == 'rpcpasswordaspin':
            # TODO: check the password via RPC-call
            if app.specter.cli is None:
                flash("We could not check your password, maybe Bitcoin Core is not running or not configured?","error")
                app.logger.info("AUDIT: Failed to check password")
                return render_template('login.jinja', specter=app.specter, data={'controller':'controller.login'}), 401
            cli = app.specter.cli.clone()
            cli.passwd = request.form['password']
            if cli.test_connection():
                app.login('admin')
                app.logger.info("AUDIT: Successfull Login via RPC-credentials")
                return redirect_login(request)
        elif app.specter.config['auth'] == 'usernamepassword':
            # TODO: This way both "User" and "user" will pass as usernames, should there be strict check on that here? Or should we keep it like this?
            username = request.form['username']
            password = request.form['password']
            user = User.get_user_by_name(app.specter, username)
            if user:
                if verify_password(user.password, password):
                    app.login(user.id)
                    return redirect_login(request)
        # Either invalid method or incorrect credentials
        flash('Invalid username or password', "error")
        app.logger.info("AUDIT: Invalid password login attempt")
        return render_template('login.jinja', specter=app.specter, data={'controller':'controller.login'}), 401
    else:
        if app.config.get('LOGIN_DISABLED'):
            app.login('admin')
            return redirect('/')
        return render_template('login.jinja', specter=app.specter, data={'next':request.args.get('next')})

def redirect_login(request):
    flash('Logged in successfully.',"info")
    if request.form.get('next') and request.form.get('next').startswith("http"):
        response = redirect(request.form['next'])
    else:
        response = redirect(url_for('index'))
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    ''' register '''
    app.specter.check()
    if request.method == 'POST':
        username = request.form['username']
        password = hash_password(request.form['password'])
        otp = request.form['otp']
        user_id = alias(username)
        if User.get_user(app.specter, user_id) or User.get_user_by_name(app.specter, username):
            flash('Username is already taken, please choose another one', "error")
            return redirect('/register?otp={}'.format(otp))
        if app.specter.burn_new_user_otp(otp):
            config = {
                "explorers": {
                    "main": "",
                    "test": "",
                    "regtest": "",
                    "signet": "",
                },
                "hwi_bridge_url": "/hwi/api/",
            }
            user = User(user_id, username, password, config)
            user.save_info(app.specter)
            return redirect('/login')
        else:
            flash('Invalid registration link, please request a new link from the node operator.', 'error')
            return redirect('/register?otp={}'.format(otp))
    return render_template('register.jinja', specter=app.specter)

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    logout_user()
    flash('You were logged out',"info")
    app.specter.clear_user_session()
    return redirect("/login") 

@app.route('/settings/', methods=['GET'])
@login_required
def settings():
    if current_user.is_admin:
        return redirect("/settings/bitcoin_core")
    else:
        return redirect("/settings/general")

@app.route('/settings/hwi', methods=['GET'])
@login_required
def hwi_settings():
    current_version = notify_upgrade()
    app.specter.check()
    return render_template(
        "settings/hwi_settings.jinja",
        specter=app.specter,
        current_version=current_version,
        rand=rand
    )

@app.route('/settings/general', methods=['GET', 'POST'])
@login_required
def general_settings():
    current_version = notify_upgrade()
    app.specter.check()
    explorer = app.specter.explorer
    hwi_bridge_url = app.specter.hwi_bridge_url
    loglevel = get_loglevel(app)
    if request.method == 'POST':
        action = request.form['action']
        explorer = request.form['explorer']
        hwi_bridge_url = request.form['hwi_bridge_url']
        if current_user.is_admin:
            loglevel = request.form['loglevel']
        
        if action == "save":
            if current_user.is_admin:
                set_loglevel(app,loglevel)

            app.specter.update_explorer(explorer, current_user)
            app.specter.update_hwi_bridge_url(hwi_bridge_url, current_user)
            app.specter.check()
    return render_template(
        "settings/general_settings.jinja",
        explorer=explorer,
        hwi_bridge_url=hwi_bridge_url,
        loglevel=loglevel,
        specter=app.specter,
        current_version=current_version,
        rand=rand
    )

@app.route('/settings/bitcoin_core', methods=['GET', 'POST'])
@login_required
def bitcoin_core_settings():
    current_version = notify_upgrade()
    app.specter.check()
    if not current_user.is_admin:
        flash('Only an admin is allowed to access this page.', 'error')
        return redirect("/")
    rpc = app.specter.config['rpc']
    user = rpc['user']
    passwd = rpc['password']
    port = rpc['port']
    host = rpc['host']
    protocol = 'http'
    if "protocol" in rpc:
        protocol = rpc["protocol"]
    test = None
    if request.method == 'POST':
        action = request.form['action']
        if current_user.is_admin:
            user = request.form['username']
            passwd = request.form['password']
            port = request.form['port']
            host = request.form['host']
            
        # protocol://host
        if "://" in host:
            arr = host.split("://")
            protocol = arr[0]
            host = arr[1]

        if action == "test":
            test = app.specter.test_rpc(
                user=user,
                password=passwd,
                port=port,
                host=host,
                protocol=protocol,
                autodetect=False
            )
        elif action == "save":
            if current_user.is_admin:
                app.specter.update_rpc(
                    user=user,
                    password=passwd,
                    port=port,
                    host=host,
                    protocol=protocol,
                    autodetect=False
                )
            app.specter.check()

    return render_template(
        "settings/bitcoin_core_settings.jinja",
        test=test,
        username=user,
        password=passwd,
        port=port,
        host=host,
        protocol=protocol,
        specter=app.specter,
        current_version=current_version,
        rand=rand
    )

@app.route('/settings/auth', methods=['GET', 'POST'])
@login_required
def auth_settings():
    current_version = notify_upgrade()
    app.specter.check()
    auth = app.specter.config['auth']
    new_otp = -1
    users = None
    if current_user.is_admin and auth == "usernamepassword":
        users = [user for user in User.get_all_users(app.specter) if not user.is_admin]
    if request.method == 'POST':
        action = request.form['action']

        if action == "save":
            if 'specter_username' in request.form:
                specter_username = request.form['specter_username']
                specter_password = request.form['specter_password']
            else:
                specter_username = None
                specter_password = None
            if current_user.is_admin:
                auth = request.form['auth']
            if specter_username:
                if current_user.username != specter_username:
                    if User.get_user_by_name(app.specter, specter_username):
                        flash('Username is already taken, please choose another one', "error")
                        return render_template(
                            "settings/auth_settings.jinja",
                            auth=auth,
                            new_otp=new_otp,
                            users=users,
                            specter=app.specter,
                            current_version=current_version,
                            rand=rand
                        )
                current_user.username = specter_username
                if specter_password:
                    current_user.password = hash_password(specter_password)
                current_user.save_info(app.specter)
            if current_user.is_admin:
                app.specter.update_auth(auth)
                if auth == "rpcpasswordaspin" or auth == "usernamepassword":
                    app.config['LOGIN_DISABLED'] = False
                else:
                    app.config['LOGIN_DISABLED'] = True

            app.specter.check()
        elif action == "adduser":
            if current_user.is_admin:
                new_otp = random.randint(100000, 999999)
                app.specter.add_new_user_otp({ 'otp': new_otp, 'created_at': time.time() })
                flash('New user link generated successfully: {}register?otp={}'.format(request.url_root, new_otp), 'info')
            else:
                flash('Error: Only the admin account can issue new registration links.', 'error')
        elif action == "deleteuser":
            delete_user = request.form['deleteuser']
            if current_user.is_admin:
                user = User.get_user(app.specter, delete_user)
                if user:
                    user.delete(app.specter)
                    users = [user for user in User.get_all_users(app.specter) if not user.is_admin]
                    flash('User {} was deleted successfully'.format(user.username), 'info')
                else:
                    flash('Error: failed to delete user, invalid user ID was given', 'error')
            else:
                flash('Error: Only the admin account can delete users', 'error')
    return render_template(
        "settings/auth_settings.jinja",
        auth=auth,
        new_otp=new_otp,
        users=users,
        specter=app.specter,
        current_version=current_version,
        rand=rand
    )


################# wallet management #####################

@app.route('/new_wallet/')
@login_required
def new_wallet_type():
    app.specter.check()
    err = None
    if app.specter.chain is None:
        err = "Configure Bitcoin Core to create wallets"
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    return render_template("wallet/new_wallet/new_wallet_type.jinja", specter=app.specter, rand=rand)


@app.route('/new_wallet/<wallet_type>/', methods=['GET', 'POST'])
@login_required
def new_wallet(wallet_type):
    wallet_types = ['simple', 'multisig']
    if wallet_type not in wallet_types:
        err = "Unknown wallet type requested"
        return render_template("base.jinja", specter=app.specter, rand=rand)
    app.specter.check()
    name = wallet_type.title()
    wallet_name = name
    i = 2
    err = None
    while wallet_name in app.specter.wallet_manager.wallets_names:
        wallet_name = "%s %d" % (name, i)
        i += 1

    if wallet_type == "multisig":
        sigs_total = len(app.specter.device_manager.devices)
        if sigs_total < 2:
            err = "You need more devices to do multisig"
            return render_template("base.jinja", specter=app.specter, rand=rand)
        sigs_required = sigs_total*2//3
        if sigs_required < 2:
            sigs_required = 2
    else:
        sigs_total = 1
        sigs_required = 1

    if request.method == 'POST':
        action = request.form['action']
        wallet_name = request.form['wallet_name']
        if wallet_name in app.specter.wallet_manager.wallets_names:
            err = "Wallet already exists"
        address_type = request.form['type']
        pur = {
            '': "General",
            "wpkh": "Segwit (bech32)",
            "sh-wpkh": "Nested Segwit",
            "pkh": "Legacy",
            "wsh": "Segwit (bech32)",
            "sh-wsh": "Nested Segwit",
            "sh": "Legacy",
        }
        sigs_total = int(request.form.get('sigs_total', 1))
        sigs_required = int(request.form.get('sigs_required', 1))
        if action == 'device' and err is None:
            cosigners = [app.specter.device_manager.get_by_alias(alias) for alias in request.form.getlist('devices')]
            if len(cosigners) != sigs_total:
                err = "Select the device" if sigs_total == 1 else "Select all the cosigners"
                return render_template(
                    "wallet/new_wallet/new_wallet.jinja",
                    wallet_type=wallet_type,
                    wallet_name=wallet_name,
                    sigs_required=sigs_required,
                    sigs_total=sigs_total,
                    error=err,
                    specter=app.specter,
                    rand=rand
                )
            devices = get_devices_with_keys_by_type(app, cosigners, address_type)
            for device in devices:
                if len(device.keys) == 0:
                        err = "Device %s doesn't have keys matching this wallet type" % device.name
                        break
            return render_template(
                "wallet/new_wallet/new_wallet_keys.jinja",
                purposes=pur, 
                wallet_type=address_type,
                wallet_name=wallet_name, 
                cosigners=devices,
                sigs_required=sigs_required, 
                sigs_total=sigs_total, 
                error=err,
                specter=app.specter,
                rand=rand
            )
        if action == 'key' and err is None:
            keys = []
            cosigners = []
            devices = []
            for i in range(sigs_total):
                try:
                    key = request.form['key%d' % i]
                    cosigner_name = request.form['cosigner%d' % i]
                    cosigner = app.specter.device_manager.get_by_alias(cosigner_name)
                    cosigners.append(cosigner)
                    for k in cosigner.keys:
                        if k.original == key:
                            keys.append(k)
                            break
                except:
                    pass
            if len(keys) != sigs_total or len(cosigners) != sigs_total:
                devices = get_devices_with_keys_by_type(app, cosigners, address_type)
                err = "Did you select enough keys?"
                return render_template(
                    "wallet/new_wallet/new_wallet_keys.jinja",
                    purposes=pur, 
                    wallet_type=address_type,
                    wallet_name=wallet_name, 
                    cosigners=devices,
                    sigs_required=sigs_required, 
                    sigs_total=sigs_total, 
                    error=err,
                    specter=app.specter,
                    rand=rand
                )
            # create a wallet here
            wallet = app.specter.wallet_manager.create_wallet(wallet_name, sigs_required, address_type, keys, cosigners)
            app.logger.info("Created Wallet %s" % wallet_name)
            rescan_blockchain = 'rescanblockchain' in request.form
            if rescan_blockchain:
                app.logger.info("Rescanning Blockchain ...")
                if app.specter.info['chain'] == "main":
                    if not app.specter.info['pruned'] or app.specter.info['pruneheight'] < 481824:
                        startblock = 481824
                    else:
                        startblock = app.specter.info['pruneheight']
                else:
                    if not app.specter.info['pruned']:
                        startblock = 0
                    else:
                        startblock = app.specter.info['pruneheight']
                try:
                    wallet.cli.rescanblockchain(startblock, timeout=1)
                except requests.exceptions.ReadTimeout:
                    # this is normal behavior in our usecase
                    pass
                except Exception as e:
                    app.logger.error("Exception while rescanning blockchain: %e" % e)
                    err = "%r" % e
                wallet.getdata()
            return redirect("/wallets/%s/" % wallet.alias)
    
    return render_template(
        "wallet/new_wallet/new_wallet.jinja",
        wallet_type=wallet_type,
        wallet_name=wallet_name,
        sigs_required=sigs_required,
        sigs_total=sigs_total,
        error=err,
        specter=app.specter,
        rand=rand
    )

@app.route('/wallets/<wallet_alias>/')
@login_required
def wallet(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if wallet.balance["untrusted_pending"] + wallet.balance["trusted"] == 0:
        return redirect("/wallets/%s/receive/" % wallet_alias)
    else:
        return redirect("/wallets/%s/tx/" % wallet_alias)

@app.route('/wallets/<wallet_alias>/tx/')
@login_required
def wallet_tx(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_tx: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    return render_template("wallet/history/txs/wallet_tx.jinja", wallet_alias=wallet_alias, wallet=wallet, specter=app.specter, rand=rand)

@app.route('/wallets/<wallet_alias>/addresses/', methods=['GET', 'POST'])
@login_required
def wallet_addresses(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_addresses: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    viewtype = 'address' if request.args.get('view') != 'label' else 'label'
    if request.method == "POST":
        action = request.form['action']
        if action == "updatelabel":
            label = request.form['label']
            account = request.form['account']
            if viewtype == 'address':
                wallet.setlabel(account, label)
            else:
                for address in wallet.addresses_on_label(account):
                    wallet.setlabel(address, label)
                wallet.getdata()
    alladdresses = True if request.args.get('all') != 'False' else False
    return render_template("wallet/history/addresses/wallet_addresses.jinja", wallet_alias=wallet_alias, wallet=wallet, alladdresses=alladdresses, viewtype=viewtype, specter=app.specter, rand=rand)

@app.route('/wallets/<wallet_alias>/receive/', methods=['GET', 'POST'])
@login_required
def wallet_receive(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == "newaddress":
            wallet.getnewaddress()
        elif action == "updatelabel":
            label = request.form['label']
            wallet.setlabel(wallet.address, label)
    if wallet.tx_on_current_address > 0:
        wallet.getnewaddress()
    return render_template("wallet/receive/wallet_receive.jinja", wallet_alias=wallet_alias, wallet=wallet, specter=app.specter, rand=rand)

@app.route('/get_fee/<blocks>')
@login_required
def fees(blocks):
    res = app.specter.estimatesmartfee(int(blocks))
    return res

@app.route('/wallets/<wallet_alias>/send/new', methods=['GET', 'POST'])
@login_required
def wallet_send(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    psbt = None
    address = ""
    label = ""
    amount = 0
    fee_rate = 0.0
    err = None
    if request.method == "POST":
        action = request.form['action']
        if action == "createpsbt":
            address = request.form['address']
            label = request.form['label']
            if request.form['label'] != "":
                wallet.setlabel(address, label)
            amount = float(request.form['btc_amount'])
            subtract = bool(request.form.get("subtract", False))
            fee_unit = request.form.get('fee_unit')
            selected_coins = request.form.getlist('coinselect')
            app.logger.info("selected coins: {}".format(selected_coins))
            if 'dynamic' in request.form.get('fee_options'):
                fee_rate = float(request.form.get('fee_rate_dynamic'))
            else:
                if request.form.get('fee_rate'):
                    fee_rate = float(request.form.get('fee_rate'))

            try:
                psbt = wallet.createpsbt(address, amount, subtract=subtract, fee_rate=fee_rate, fee_unit=fee_unit, selected_coins=selected_coins)
                if psbt is None:
                    err = "Probably you don't have enough funds, or something else..."
                else:
                    # calculate new amount if we need to subtract
                    if subtract:
                        for v in psbt["tx"]["vout"]:
                            if address in v["scriptPubKey"]["addresses"]:
                                amount = v["value"]
            except Exception as e:
                err = e
            if err is None:
                return render_template("wallet/send/sign/wallet_send_sign_psbt.jinja", psbt=psbt, label=label, 
                                                    wallet_alias=wallet_alias, wallet=wallet, 
                                                    specter=app.specter, rand=rand)
        elif action == "importpsbt":
            try:
                b64psbt = request.form["rawpsbt"]
                psbt = wallet.importpsbt(b64psbt)
            except Exception as e:
                flash("Could not import PSBT: %s" % e, "error")
                return redirect(url_for('wallet_importpsbt', wallet_alias=wallet_alias))
            return render_template("wallet/send/sign/wallet_send_sign_psbt.jinja", psbt=psbt, label=label, 
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter, rand=rand)
        elif action == "openpsbt":
            psbt = ast.literal_eval(request.form["pending_psbt"])
            return render_template("wallet/send/sign/wallet_send_sign_psbt.jinja", psbt=psbt, label=label, 
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter, rand=rand)
        elif action == 'deletepsbt':
            try:
                wallet.delete_pending_psbt(ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"])
            except Exception as e:
                flash("Could not delete Pending PSBT!", "error")
    return render_template("wallet/send/new/wallet_send.jinja", psbt=psbt, label=label, 
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter, rand=rand, error=err)

@app.route('/wallets/<wallet_alias>/send/import')
@login_required
def wallet_importpsbt(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    err = None
    return render_template("wallet/send/import/wallet_importpsbt.jinja", 
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter, rand=rand, error=err)

@app.route('/wallets/<wallet_alias>/send/pending/', methods=['GET', 'POST'])
@login_required
def wallet_sendpending(wallet_alias):
    app.specter.check()
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_sendpending: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == 'deletepsbt':
            try:
                wallet.delete_pending_psbt(ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"])
            except Exception as e:
                app.logger.error("Could not delete Pending PSBT: %s" % e)
                flash("Could not delete Pending PSBT!", "error")
    pending_psbts = wallet.pending_psbts
    return render_template("wallet/send/pending/wallet_sendpending.jinja", pending_psbts=pending_psbts,
                                                wallet_alias=wallet_alias, wallet=wallet, 
                                                specter=app.specter) 


@app.route('/wallets/<wallet_alias>/settings/', methods=['GET','POST'])
@login_required
def wallet_settings(wallet_alias):
    app.specter.check()
    error = None
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form['action']
        if action == "rescanblockchain":
            startblock = int(request.form['startblock'])
            try:
                res = wallet.cli.rescanblockchain(startblock, timeout=1)
            except requests.exceptions.ReadTimeout:
                # this is normal behaviour in our usecase
                pass
            except Exception as e:
                app.logger.error("%s while rescanblockchain" % e)
                error = "%r" % e
            wallet.getdata()
        elif action == "abortrescan":
            res = wallet.cli.abortrescan()
            if not res:
                error="Failed to abort rescan. Maybe already complete?"
            wallet.getdata()
        elif action == "keypoolrefill":
            delta = int(request.form['keypooladd'])
            wallet.keypoolrefill(wallet.keypool, wallet.keypool + delta)
            wallet.keypoolrefill(wallet.change_keypool, wallet.change_keypool + delta, change=True)
            wallet.getdata()
        elif action == "rebuildcache":
            wallet.cli.cache.rebuild_cache()
        elif action == "deletewallet":
            app.specter.wallet_manager.delete_wallet(wallet)
            response = redirect(url_for('index'))
            return response
        elif action == "rename":
            wallet_name = request.form['newtitle']
            if wallet_name in app.specter.wallet_manager.wallets_names:
                error = "Wallet already exists"
            else:
                app.specter.wallet_manager.rename_wallet(wallet, wallet_name)

        return render_template("wallet/settings/wallet_settings.jinja", 
            wallet_alias=wallet_alias,
            wallet=wallet, 
            specter=app.specter,
            rand=rand, 
            error=error
        )
    else:
        return render_template(
            "wallet/settings/wallet_settings.jinja", 
            wallet_alias=wallet_alias,
            wallet=wallet, 
            specter=app.specter,
            rand=rand, 
            error=error
        )

################# devices management #####################

@app.route('/new_device/', methods=['GET', 'POST'])
@login_required
def new_device():
    app.specter.check()
    err = None
    device_type = "other"
    device_name = ""
    xpubs = ""
    if request.method == 'POST':
        device_type = request.form['device_type']
        device_name = request.form['device_name']
        if not device_name:
            err = "Device name must not be empty"
        elif device_name in app.specter.device_manager.devices_names:
            err = "Device with this name already exists"
        xpubs = request.form['xpubs']
        if not xpubs:
            err = "xpubs name must not be empty"
        keys, failed = Key.parse_xpubs(xpubs)
        if len(failed) > 0:
            err = "Failed to parse these xpubs:\n" + "\n".join(failed)
        if err is None:
            device = app.specter.device_manager.add_device(name=device_name, device_type=device_type, keys=keys)
            return redirect("/devices/%s/" % device.alias)
    return render_template("device/new_device.jinja", device_type=device_type, device_name=device_name, xpubs=xpubs, error=err, specter=app.specter, rand=rand)

@app.route('/devices/<device_alias>/', methods=['GET', 'POST'])
@login_required
def device(device_alias):
    app.specter.check()
    err = None
    try:
        device = app.specter.device_manager.get_by_alias(device_alias)
    except:
        return render_template("base.jinja", error="Device not found", specter=app.specter, rand=rand)
    wallets = device.wallets(app.specter.wallet_manager)
    if request.method == 'POST':
        action = request.form['action']
        if action == "forget":
            if len(wallets) != 0:
                err = "Device could not be removed since it is used in wallets: {}.\nYou must delete those wallets before you can remove this device.".format([wallet.name for wallet in wallets])
            else:
                app.specter.device_manager.remove_device(device)
                return redirect("/")
        elif action == "delete_key":
            key = request.form['key']
            device.remove_key(Key.from_json({ 'original': key }))
        elif action == "add_keys":
            return render_template("device/new_device.jinja", 
                    device=device, device_alias=device_alias, specter=app.specter, rand=rand)
        elif action == "morekeys":
            # refactor to fn
            xpubs = request.form['xpubs']
            keys, failed = Key.parse_xpubs(xpubs)
            err = None
            if len(failed) > 0:
                err = "Failed to parse these xpubs:\n" + "\n".join(failed)
                return render_template("device/new_device.jinja", 
                        device=device, device_alias=device_alias, xpubs=xpubs, error=err, specter=app.specter, rand=rand)
            if err is None:
                device.add_keys(keys)
        elif action == "settype":
            device_type = request.form['device_type']
            device.set_type(device_type)
    device = copy.deepcopy(device)
    device.keys.sort(key=lambda k: k.metadata["chain"] + k.metadata["purpose"], reverse=True)
    return render_template("device/device.jinja", 
            device=device, device_alias=device_alias, purposes=purposes, wallets=wallets, error=err, specter=app.specter, rand=rand)



############### filters ##################

@app.template_filter('datetime')
def timedatetime(s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")

@app.template_filter('btcamount')
def btcamount(value):
    value = float(value)
    return "{:.8f}".format(value).rstrip("0").rstrip(".")

def notify_upgrade():
    ''' If a new version is available, notifies the user via flash 
        that there is an upgrade to specter.desktop
        :return the current version
    '''
    version_info={}
    version_info["current"], version_info["latest"], version_info["upgrade"] = get_version_info()
    app.logger.info("Upgrade? {}".format(version_info["upgrade"]))
    if version_info["upgrade"]:
        flash("There is a new version available. Consider strongly to upgrade to the new version {} with \"pip3 install cryptoadvance.specter --upgrade\"".format(version_info["latest"]), "info")
    return version_info["current"]
