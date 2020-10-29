import ast, sys, json, os, time, base64
import requests
import random, copy
from collections import OrderedDict
from .util.descriptor import AddChecksum, Descriptor
from mnemonic import Mnemonic
from threading import Thread
from .key import Key
from .device_manager import get_device_class

from functools import wraps
from flask import g, request, redirect, url_for

from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    send_file,
)
from flask_login import login_required, login_user, logout_user, current_user
from flask_login.config import EXEMPT_METHODS
from .helpers import (
    alias,
    get_devices_with_keys_by_type,
    get_loglevel,
    set_loglevel,
    bcur2base64,
    get_txid,
    generate_mnemonic,
    get_startblock_by_chain,
    to_ascii20,
)
from .util.shell import run_shell
from .specter import Specter
from .specter_error import SpecterError
from .wallet_manager import purposes
from .persistence import write_devices, write_wallet
from .rpc import RpcError
from .user import User, hash_password, verify_password
from datetime import datetime
import urllib
from io import BytesIO
import traceback
from binascii import b2a_base64
from .util.base43 import b43_decode
from .util.tor import start_hidden_service, stop_hidden_services
from stem.control import Controller

from pathlib import Path

env_path = Path(".") / ".flaskenv"
from dotenv import load_dotenv

load_dotenv(env_path)

from flask import current_app as app

rand = random.randint(0, 1e32)  # to force style refresh

########## exception handler ##############
@app.errorhandler(Exception)
def server_error(e):
    # if rpc is not available
    if app.specter.rpc is None or not app.specter.rpc.test_connection():
        # make sure specter knows that rpc is not there
        app.specter.check()
    app.logger.error("Uncaught exception: %s" % e)
    trace = traceback.format_exc()
    app.logger.error(trace)
    return render_template("500.jinja", error=e, traceback=trace), 500


########## on every request ###############
@app.before_request
def selfcheck():
    """check status before every request"""
    if app.specter.rpc is not None:
        type(app.specter.rpc).counter = 0
    if app.config.get("LOGIN_DISABLED"):
        app.login("admin")


########## template injections #############
@app.context_processor
def inject_debug():
    """ Can be used in all jinja2 templates """
    return dict(debug=app.config["DEBUG"])


@app.context_processor
def inject_tor():
    if app.config["DEBUG"]:
        return dict(tor_service_id="", tor_enabled=False)
    if (
        request.args.get("action", "") == "stoptor"
        or request.args.get("action", "") == "starttor"
    ):
        if hasattr(current_user, "is_admin") and current_user.is_admin:
            try:
                current_hidden_services = (
                    app.controller.list_ephemeral_hidden_services()
                )
            except Exception:
                current_hidden_services = []
            if (
                request.args.get("action", "") == "stoptor"
                and len(current_hidden_services) != 0
            ):
                stop_hidden_services(app)
            if (
                request.args.get("action", "") == "starttor"
                and len(current_hidden_services) == 0
            ):
                try:
                    start_hidden_service(app)
                except Exception as e:
                    flash(
                        "Failed to start Tor hidden service.\
Make sure you have Tor running with ControlPort configured and try again.\
Error returned: {}".format(
                            e
                        ),
                        "error",
                    )
                    return dict(tor_service_id="", tor_enabled=False)
    return dict(tor_service_id=app.tor_service_id, tor_enabled=app.tor_enabled)


################ routes ####################
@app.route("/wallets/<wallet_alias>/combine/", methods=["GET", "POST"])
@login_required
def combine(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while combine: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        # FIXME: ugly...
        txid = request.form.get("txid")
        psbts = [request.form.get("psbt0").strip(), request.form.get("psbt1").strip()]
        raw = {}
        combined = None

        for i, psbt in enumerate(psbts):
            if "UR:BYTES/" in psbt.upper():
                psbt = bcur2base64(psbt).decode()

            # if electrum then it's base43
            try:
                decoded = b43_decode(psbt)
                if decoded.startswith(b"psbt\xff"):
                    psbt = b2a_base64(decoded).decode()
                else:
                    psbt = decoded.hex()
            except:
                pass

            psbts[i] = psbt
            # psbt should start with cHNi
            # if not - maybe finalized hex tx
            if not psbt.startswith("cHNi"):
                raw["hex"] = psbt
                combined = psbts[1 - i]

        # try converting to bytes
        if "hex" in raw:
            raw["complete"] = True
            raw["psbt"] = combined
            try:
                bytes.fromhex(raw["hex"])
            except:
                return "Invalid transaction format", 500

        else:
            try:
                combined = app.specter.combine(psbts)
                raw = app.specter.finalize(combined)
                if "psbt" not in raw:
                    raw["psbt"] = combined
                psbt = wallet.update_pending_psbt(combined, txid, raw)
            except RpcError as e:
                return e.error_msg, e.status_code
            except Exception as e:
                return "Unknown error: %r" % e, 500
        devices = []
        raw["devices"] = psbt["devices_signed"]
        return json.dumps(raw)
    return "meh"


@app.route("/wallets/<wallet_alias>/broadcast/", methods=["GET", "POST"])
@login_required
def broadcast(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while broadcast: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        tx = request.form.get("tx")
        res = wallet.rpc.testmempoolaccept([tx])[0]
        if res["allowed"]:
            app.specter.broadcast(tx)
            wallet.delete_pending_psbt(get_txid(tx))
            return jsonify(success=True)
        else:
            return jsonify(
                success=False,
                error="Failed to broadcast transaction: transaction is invalid\n%s"
                % res["reject-reason"],
            )
    return jsonify(success=False, error="broadcast tx request must use POST")


@app.route("/")
@login_required
def index():
    notify_upgrade()
    if len(app.specter.wallet_manager.wallets) > 0:
        return redirect(
            url_for(
                "wallet",
                wallet_alias=app.specter.wallet_manager.wallets[
                    app.specter.wallet_manager.wallets_names[0]
                ].alias,
            )
        )

    return redirect("about")


@app.route("/about")
@login_required
def about():
    notify_upgrade()

    return render_template("base.jinja", specter=app.specter, rand=rand)


@app.route("/login", methods=["GET", "POST"])
def login():
    """ login """
    if request.method == "POST":
        if app.specter.config["auth"] == "none":
            app.login("admin")
            app.logger.info("AUDIT: Successfull Login no credentials")
            return redirect_login(request)
        if app.specter.config["auth"] == "rpcpasswordaspin":
            # TODO: check the password via RPC-call
            if app.specter.rpc is None:
                flash(
                    "We could not check your password, maybe Bitcoin Core is not running or not configured?",
                    "error",
                )
                app.logger.info("AUDIT: Failed to check password")
                return (
                    render_template(
                        "login.jinja",
                        specter=app.specter,
                        data={"controller": "controller.login"},
                    ),
                    401,
                )
            rpc = app.specter.rpc.clone()
            rpc.password = request.form["password"]
            if rpc.test_connection():
                app.login("admin")
                app.logger.info("AUDIT: Successfull Login via RPC-credentials")
                return redirect_login(request)
        elif app.specter.config["auth"] == "usernamepassword":
            # TODO: This way both "User" and "user" will pass as usernames, should there be strict check on that here? Or should we keep it like this?
            username = request.form["username"]
            password = request.form["password"]
            user = app.specter.user_manager.get_user_by_username(username)
            if user:
                if verify_password(user.password, password):
                    app.login(user.id)
                    return redirect_login(request)
        # Either invalid method or incorrect credentials
        flash("Invalid username or password", "error")
        app.logger.info("AUDIT: Invalid password login attempt")
        return (
            render_template(
                "login.jinja",
                specter=app.specter,
                data={"controller": "controller.login"},
            ),
            401,
        )
    else:
        if app.config.get("LOGIN_DISABLED"):
            app.login("admin")
            return redirect("")
        return render_template(
            "login.jinja", specter=app.specter, data={"next": request.args.get("next")}
        )


def redirect_login(request):
    flash("Logged in successfully.", "info")
    if request.form.get("next") and request.form.get("next") != "None":
        response = redirect(request.form["next"])
    else:
        response = redirect(url_for("index"))
    return response


@app.route("/register", methods=["GET", "POST"])
def register():
    """ register """
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])
        otp = request.form["otp"]
        user_id = alias(username)
        if app.specter.user_manager.get_user(user_id):
            flash("Username is already taken, please choose another one", "error")
            return redirect("register?otp={}".format(otp))
        if app.specter.burn_new_user_otp(otp):
            config = {
                "explorers": {"main": "", "test": "", "regtest": "", "signet": ""},
                "hwi_bridge_url": "/hwi/api/",
            }
            user = User(user_id, username, password, config)
            app.specter.add_user(user)
            flash(
                "You have registered successfully, \
please login with your new account to start using Specter"
            )
            return redirect("login")
        else:
            flash(
                "Invalid registration link, \
please request a new link from the node operator.",
                "error",
            )
            return redirect("register?otp={}".format(otp))
    return render_template("register.jinja", specter=app.specter)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    flash("You were logged out", "info")
    return redirect("login")


@app.route("/settings/", methods=["GET"])
@login_required
def settings():
    if current_user.is_admin:
        return redirect(url_for("bitcoin_core_settings"))
    else:
        return redirect(url_for("general_settings"))


@app.route("/settings/hwi", methods=["GET", "POST"])
@login_required
def hwi_settings():
    current_version = notify_upgrade()
    if request.method == "POST":
        hwi_bridge_url = request.form["hwi_bridge_url"]
        app.specter.update_hwi_bridge_url(hwi_bridge_url, current_user)
        flash("HWIBridge URL is updated! Don't forget to whitelist Specter!")
    return render_template(
        "settings/hwi_settings.jinja",
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


@app.route("/settings/general", methods=["GET", "POST"])
@login_required
def general_settings():
    current_version = notify_upgrade()
    explorer = app.specter.explorer
    loglevel = get_loglevel(app)
    unit = app.specter.unit
    if request.method == "POST":
        action = request.form["action"]
        explorer = request.form["explorer"]
        unit = request.form["unit"]
        validate_merkleproof_bool = request.form.get("validatemerkleproof") == "on"

        if current_user.is_admin:
            loglevel = request.form["loglevel"]

        if action == "save":
            if current_user.is_admin:
                set_loglevel(app, loglevel)

            app.specter.update_explorer(explorer, current_user)
            app.specter.update_unit(unit, current_user)
            app.specter.update_merkleproof_settings(
                validate_bool=validate_merkleproof_bool
            )
            app.specter.check()
        elif action == "backup":
            return send_file(
                app.specter.specter_backup_file(),
                attachment_filename="specter-backup.zip",
                as_attachment=True,
            )
        elif action == "restore":
            restore_devices = []
            restore_wallets = []
            if request.form.get("restoredevices", ""):
                restore_devices = json.loads(request.form.get("restoredevices", "[]"))
            if request.form.get("restorewallets", ""):
                restore_wallets = json.loads(request.form.get("restorewallets", "[]"))
            write_devices(restore_devices)
            app.specter.device_manager.update()

            rescanning = False
            for wallet in restore_wallets:
                try:
                    app.specter.wallet_manager.rpc.createwallet(
                        os.path.join(
                            app.specter.wallet_manager.rpc_path, wallet["alias"]
                        ),
                        True,
                    )
                except Exception as e:
                    # if wallet already exists in Bitcoin Core
                    # continue with the existing one
                    if "already exists" not in str(e):
                        flash(
                            "Failed to import wallet {}, error: {}".format(
                                wallet["name"], e
                            ),
                            "error",
                        )
                        continue
                write_wallet(wallet)
                app.specter.wallet_manager.update()
                try:
                    wallet_obj = app.specter.wallet_manager.get_by_alias(
                        wallet["alias"]
                    )
                    wallet_obj.import_labels(wallet.get("labels", []))
                    try:
                        wallet_obj.rpc.rescanblockchain(
                            wallet["blockheight"]
                            if "blockheight" in wallet
                            else get_startblock_by_chain(app.specter),
                            timeout=1,
                        )
                        app.logger.info("Rescanning Blockchain ...")
                        rescanning = True
                    except requests.exceptions.ReadTimeout:
                        # this is normal behavior in our usecase
                        pass
                    except Exception as e:
                        app.logger.error(
                            "Exception while rescanning blockchain for wallet {}: {}".format(
                                wallet["alias"], e
                            )
                        )
                        flash(
                            "Failed to perform rescan for wallet: {}".format(e), "error"
                        )
                    wallet_obj.getdata()
                except Exception:
                    flash("Failed to import wallet {}".format(wallet["name"]), "error")
            flash("Specter data was successfully loaded from backup.", "info")
            if rescanning:
                flash(
                    "Wallets are rescanning for transactions history.\n\
This may take a few hours to complete.",
                    "info",
                )

    return render_template(
        "settings/general_settings.jinja",
        explorer=explorer,
        loglevel=loglevel,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs") is True,
        unit=unit,
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


@app.route("/settings/bitcoin_core", methods=["GET", "POST"])
@login_required
def bitcoin_core_settings():
    current_version = notify_upgrade()
    if not current_user.is_admin:
        flash("Only an admin is allowed to access this page.", "error")
        return redirect("")
    rpc = app.specter.config["rpc"]
    user = rpc["user"]
    password = rpc["password"]
    port = rpc["port"]
    host = rpc["host"]
    protocol = "http"
    autodetect = rpc["autodetect"]
    datadir = rpc["datadir"]
    err = None

    if "protocol" in rpc:
        protocol = rpc["protocol"]
    test = None
    if request.method == "POST":
        action = request.form["action"]
        if current_user.is_admin:
            autodetect = "autodetect" in request.form
            if autodetect:
                datadir = request.form["datadir"]
            user = request.form["username"]
            password = request.form["password"]
            port = request.form["port"]
            host = request.form["host"]

        # protocol://host
        if "://" in host:
            arr = host.split("://")
            protocol = arr[0]
            host = arr[1]

        if action == "test":
            # If this is failing, the test_rpc-method needs improvement
            # Don't wrap this into a try/except otherwise the feedback
            # of what's wron to the user gets broken
            test = app.specter.test_rpc(
                user=user,
                password=password,
                port=port,
                host=host,
                protocol=protocol,
                autodetect=autodetect,
                datadir=datadir,
            )
        elif action == "save":
            if current_user.is_admin:
                success = app.specter.update_rpc(
                    user=user,
                    password=password,
                    port=port,
                    host=host,
                    protocol=protocol,
                    autodetect=autodetect,
                    datadir=datadir,
                )
                if not success:
                    flash("Failed connecting to the node", "error")
            app.specter.check()

    return render_template(
        "settings/bitcoin_core_settings.jinja",
        test=test,
        autodetect=autodetect,
        datadir=datadir,
        username=user,
        password=password,
        port=port,
        host=host,
        protocol=protocol,
        specter=app.specter,
        current_version=current_version,
        error=err,
        rand=rand,
    )


@app.route("/settings/auth", methods=["GET", "POST"])
@login_required
def auth_settings():
    current_version = notify_upgrade()
    auth = app.specter.config["auth"]
    new_otp = -1
    users = None
    if current_user.is_admin and auth == "usernamepassword":
        users = [user for user in app.specter.user_manager.users if not user.is_admin]
    if request.method == "POST":
        action = request.form["action"]

        if action == "save":
            if "specter_username" in request.form:
                specter_username = request.form["specter_username"]
                specter_password = request.form["specter_password"]
            else:
                specter_username = None
                specter_password = None
            if current_user.is_admin:
                auth = request.form["auth"]
            if specter_username:
                if current_user.username != specter_username:
                    if app.specter.user_manager.get_user(specter_username):
                        flash(
                            "Username is already taken, please choose another one",
                            "error",
                        )
                        return render_template(
                            "settings/auth_settings.jinja",
                            auth=auth,
                            new_otp=new_otp,
                            users=users,
                            specter=app.specter,
                            current_version=current_version,
                            rand=rand,
                        )
                current_user.username = specter_username
                if specter_password:
                    current_user.password = hash_password(specter_password)
                current_user.save_info(app.specter)
            if current_user.is_admin:
                app.specter.update_auth(auth)
                if auth == "rpcpasswordaspin" or auth == "usernamepassword":
                    if auth == "usernamepassword":
                        users = [
                            user
                            for user in app.specter.user_manager.users
                            if not user.is_admin
                        ]
                    else:
                        users = None
                    app.config["LOGIN_DISABLED"] = False
                else:
                    users = None
                    app.config["LOGIN_DISABLED"] = True

            app.specter.check()
        elif action == "adduser":
            if current_user.is_admin:
                new_otp = random.randint(100000, 999999)
                app.specter.add_new_user_otp(
                    {"otp": new_otp, "created_at": time.time()}
                )
                flash(
                    "New user link generated successfully: {}register?otp={}".format(
                        request.url_root, new_otp
                    ),
                    "info",
                )
            else:
                flash(
                    "Error: Only the admin account can issue new registration links.",
                    "error",
                )
        elif action == "deleteuser":
            delete_user = request.form["deleteuser"]
            user = app.specter.user_manager.get_user(delete_user)
            if current_user.is_admin:
                app.specter.delete_user(user)
                users.remove(user)
                flash("User {} was deleted successfully".format(user.username), "info")
            else:
                flash("Error: Only the admin account can delete users", "error")
    return render_template(
        "settings/auth_settings.jinja",
        auth=auth,
        new_otp=new_otp,
        users=users,
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


################# wallet management #####################


@app.route("/new_wallet/")
@login_required
def new_wallet_type():
    err = None
    if app.specter.chain is None:
        err = "Configure Bitcoin Core to create wallets"
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    try:
        # Make sure wallet is enabled on Bitcoin Core
        app.specter.rpc.listwallets()
    except Exception:
        err = '<p><br>Configure Bitcoin Core is running with wallets disabled.<br><br>Please make sure disablewallet is off (set disablewallet=0 in your bitcoin.conf), then restart Bitcoin Core and try again.<br>See <a href="https://github.com/cryptoadvance/specter-desktop/blob/34ca139694ecafb2e7c2bd5ad5c4ac74c6d11501/docs/faq.md#im-not-sure-i-want-the-bitcoin-core-wallet-functionality-to-be-used-is-that-mandatory-if-so-is-it-considered-secure" target="_blank" style="color: white;">here</a> for more information.</p>'
        return render_template("base.jinja", error=err, specter=app.specter, rand=rand)
    return render_template(
        "wallet/new_wallet/new_wallet_type.jinja", specter=app.specter, rand=rand
    )


@app.route("/new_wallet/<wallet_type>/", methods=["GET", "POST"])
@login_required
def new_wallet(wallet_type):
    wallet_types = ["simple", "multisig", "import_wallet"]
    if wallet_type not in wallet_types:
        err = "Unknown wallet type requested"
        return render_template("base.jinja", specter=app.specter, rand=rand)
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
        sigs_required = sigs_total * 2 // 3
        if sigs_required < 2:
            sigs_required = 2
    else:
        sigs_total = 1
        sigs_required = 1

    if request.method == "POST":
        action = request.form["action"]
        if action == "importwallet":
            wallet_data = json.loads(request.form["wallet_data"].replace("'", "h"))
            wallet_name = (
                wallet_data["label"] if "label" in wallet_data else "Imported Wallet"
            )
            startblock = (
                wallet_data["blockheight"]
                if "blockheight" in wallet_data
                else app.specter.wallet_manager.rpc.getblockcount()
            )
            try:
                descriptor = Descriptor.parse(
                    AddChecksum(wallet_data["descriptor"].split("#")[0]),
                    testnet=app.specter.chain != "main",
                )
                if descriptor is None:
                    err = "Invalid wallet descriptor."
            except:
                err = "Invalid wallet descriptor."
            if wallet_name in app.specter.wallet_manager.wallets_names:
                err = "Wallet with the same name already exists"

            if not err:
                try:
                    sigs_total = descriptor.multisig_N
                    sigs_required = descriptor.multisig_M
                    if descriptor.wpkh:
                        address_type = "wpkh"
                    elif descriptor.wsh:
                        address_type = "wsh"
                    elif descriptor.sh_wpkh:
                        address_type = "sh-wpkh"
                    elif descriptor.sh_wsh:
                        address_type = "sh-wsh"
                    elif descriptor.sh:
                        address_type = "sh-wsh"
                    else:
                        address_type = "pkh"
                    keys = []
                    cosigners = []
                    unknown_cosigners = []
                    if sigs_total == None:
                        sigs_total = 1
                        sigs_required = 1
                        descriptor.origin_fingerprint = [descriptor.origin_fingerprint]
                        descriptor.origin_path = [descriptor.origin_path]
                        descriptor.base_key = [descriptor.base_key]
                    for i in range(sigs_total):
                        cosigner_found = False
                        for device in app.specter.device_manager.devices:
                            cosigner = app.specter.device_manager.devices[device]
                            if descriptor.origin_fingerprint[i] is None:
                                descriptor.origin_fingerprint[i] = ""
                            if descriptor.origin_path[i] is None:
                                descriptor.origin_path[
                                    i
                                ] = descriptor.origin_fingerprint[i]
                            for key in cosigner.keys:
                                if key.fingerprint + key.derivation.replace(
                                    "m", ""
                                ) == descriptor.origin_fingerprint[
                                    i
                                ] + descriptor.origin_path[
                                    i
                                ].replace(
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
                                    descriptor.origin_fingerprint[i],
                                    descriptor.origin_path[i],
                                    descriptor.base_key[i],
                                )
                            )
                            unknown_cosigners.append(desc_key)
                        #     raise Exception('Could not find device with matching key to import wallet')
                    wallet_type = "multisig" if sigs_total > 1 else "simple"
                    createwallet = "createwallet" in request.form
                    if createwallet:
                        wallet_name = request.form["wallet_name"]
                        for i, unknown_cosigner in enumerate(unknown_cosigners):
                            unknown_cosigner_name = request.form[
                                "unknown_cosigner_{}_name".format(i)
                            ]
                            device = app.specter.device_manager.add_device(
                                name=unknown_cosigner_name,
                                device_type="other",
                                keys=[unknown_cosigner],
                            )
                            keys.append(unknown_cosigner)
                            cosigners.append(device)
                        wallet = app.specter.wallet_manager.create_wallet(
                            wallet_name, sigs_required, address_type, keys, cosigners
                        )
                        flash("Wallet imported successfully", "info")
                        try:
                            wallet.rpc.rescanblockchain(startblock, timeout=1)
                            app.logger.info("Rescanning Blockchain ...")
                        except requests.exceptions.ReadTimeout:
                            # this is normal behavior in our usecase
                            pass
                        except Exception as e:
                            app.logger.error(
                                "Exception while rescanning blockchain: %e" % e
                            )
                            flash(
                                "Failed to perform rescan for wallet: %r" % e, "error"
                            )
                        wallet.getdata()
                        return redirect(url_for("wallet", wallet_alias=wallet.alias))
                    else:
                        return render_template(
                            "wallet/new_wallet/import_wallet.jinja",
                            wallet_data=json.dumps(wallet_data),
                            wallet_type=wallet_type,
                            wallet_name=wallet_name,
                            cosigners=cosigners,
                            unknown_cosigners=unknown_cosigners,
                            sigs_required=sigs_required,
                            sigs_total=sigs_total,
                            error=err,
                            specter=app.specter,
                            rand=rand,
                        )
                except Exception as e:
                    err = "%r" % e

            if err:
                return render_template(
                    "wallet/new_wallet/new_wallet_type.jinja",
                    error="Failed to import wallet: " + err,
                    specter=app.specter,
                    rand=rand,
                )
        else:
            wallet_name = request.form["wallet_name"]
            if wallet_name in app.specter.wallet_manager.wallets_names:
                err = "Wallet already exists"
            address_type = request.form["type"]
            sigs_total = int(request.form.get("sigs_total", 1))
            sigs_required = int(request.form.get("sigs_required", 1))

        if action == "device" and err is None:
            cosigners = [
                app.specter.device_manager.get_by_alias(alias)
                for alias in request.form.getlist("devices")
            ]
            if len(cosigners) != sigs_total:
                err = (
                    "Select the device"
                    if sigs_total == 1
                    else "Select all the cosigners"
                )
                return render_template(
                    "wallet/new_wallet/new_wallet.jinja",
                    wallet_type=wallet_type,
                    wallet_name=wallet_name,
                    sigs_required=sigs_required,
                    sigs_total=sigs_total,
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )
            devices = get_devices_with_keys_by_type(app, cosigners, address_type)
            for device in devices:
                if len(device.keys) == 0:
                    err = (
                        "Device %s doesn't have keys matching this wallet type"
                        % device.name
                    )
                    break
            return render_template(
                "wallet/new_wallet/new_wallet_keys.jinja",
                purposes=purposes,
                wallet_type=address_type,
                wallet_name=wallet_name,
                cosigners=devices,
                sigs_required=sigs_required,
                sigs_total=sigs_total,
                error=err,
                specter=app.specter,
                rand=rand,
            )
        if action == "key" and err is None:
            keys = []
            cosigners = []
            devices = []
            for i in range(sigs_total):
                try:
                    key = request.form["key%d" % i]
                    cosigner_name = request.form["cosigner%d" % i]
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
                    purposes=purposes,
                    wallet_type=address_type,
                    wallet_name=wallet_name,
                    cosigners=devices,
                    sigs_required=sigs_required,
                    sigs_total=sigs_total,
                    error=err,
                    specter=app.specter,
                    rand=rand,
                )
            # create a wallet here
            wallet = app.specter.wallet_manager.create_wallet(
                wallet_name, sigs_required, address_type, keys, cosigners
            )
            app.logger.info("Created Wallet %s" % wallet_name)
            rescan_blockchain = "rescanblockchain" in request.form
            if rescan_blockchain:
                # old wallet - import more addresses
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=False)
                wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=True)
                if "utxo" in request.form.get("full_rescan_option"):
                    explorer = None
                    if "use_explorer" in request.form:
                        explorer = app.specter.get_default_explorer()
                    wallet.rescanutxo(explorer)
                    app.specter.info["utxorescan"] = 1
                    app.specter.utxorescanwallet = wallet.alias
                else:
                    app.logger.info("Rescanning Blockchain ...")
                    startblock = int(request.form["startblock"])
                    try:
                        wallet.rpc.rescanblockchain(startblock, timeout=1)
                    except requests.exceptions.ReadTimeout:
                        # this is normal behavior in our usecase
                        pass
                    except Exception as e:
                        app.logger.error(
                            "Exception while rescanning blockchain: %e" % e
                        )
                        err = "%r" % e
                    wallet.getdata()
            return redirect(url_for("wallet", wallet_alias=wallet.alias))

    return render_template(
        "wallet/new_wallet/new_wallet.jinja",
        wallet_type=wallet_type,
        wallet_name=wallet_name,
        sigs_required=sigs_required,
        sigs_total=sigs_total,
        error=err,
        specter=app.specter,
        rand=rand,
    )


@app.route("/wallets/<wallet_alias>/")
@login_required
def wallet(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    return redirect(url_for("wallet_receive", wallet_alias=wallet_alias))


@app.route("/wallets_overview/")
@login_required
def wallets_overview():
    idx = int(request.args.get("idx", default=0))
    return render_template(
        "wallet/wallets_overview.jinja",
        idx=idx,
        history=True,
        specter=app.specter,
        rand=rand,
    )


@app.route("/singlesig_setup_wizard/", methods=["GET", "POST"])
@login_required
def singlesig_setup_wizard():
    err = None
    if request.method == "POST":
        xpubs = request.form["xpubs"]
        if not xpubs:
            err = "xpubs name must not be empty"
        keys, failed = Key.parse_xpubs(xpubs)
        if len(failed) > 0:
            err = "Failed to parse these xpubs:\n" + "\n".join(failed)
        device_type = request.form.get("devices")
        device_name = get_device_class(device_type).name
        i = 2
        while device_name in [
            device.name for device in app.specter.device_manager.devices.values()
        ]:
            device_name = "%s %d" % (get_device_class(device_type).name, i)
            i += 1
        if err is None:
            device = app.specter.device_manager.add_device(
                name=device_name, device_type=device_type, keys=keys
            )
        wallet_name = request.form["wallet_name"]
        if wallet_name in app.specter.wallet_manager.wallets_names:
            err = "Wallet already exists"
        address_type = request.form["type"]
        wallet_key = [
            key
            for key in device.keys
            if key.key_type == address_type
            and (key.xpub.startswith("xpub") != (app.specter.chain != "main"))
        ]

        if len(wallet_key) != 1:
            err = "Device key was not imported properly. Please make\
                sure your device is on the right network and try again."

        if err:
            app.specter.device_manager.remove_device(
                device,
                app.specter.wallet_manager,
                bitcoin_datadir=app.specter.bitcoin_datadir,
                chain=app.specter.chain,
            )
            return render_template(
                "wizards/singlesig_setup_wizard.jinja",
                error=err,
                specter=app.specter,
                rand=rand,
            )
        wallet = app.specter.wallet_manager.create_wallet(
            wallet_name, 1, address_type, wallet_key, [device]
        )
        app.logger.info("Created Wallet %s" % wallet_name)
        rescan_blockchain = request.form["rescan"] == "true"
        if rescan_blockchain:
            # old wallet - import more addresses
            wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=False)
            wallet.keypoolrefill(0, wallet.IMPORT_KEYPOOL, change=True)
            explorer = None
            if "use_explorer" in request.form:
                explorer = app.specter.get_default_explorer()
            wallet.rescanutxo(explorer)
            app.specter.info["utxorescan"] = 1
            app.specter.utxorescanwallet = wallet.alias
        return redirect(url_for("wallet", wallet_alias=wallet.alias))
    return render_template(
        "wizards/singlesig_setup_wizard.jinja", specter=app.specter, rand=rand
    )


@app.route("/wallets/<wallet_alias>/tx/")
@login_required
def wallet_tx(wallet_alias):
    return redirect(url_for("wallet_tx_history", wallet_alias=wallet_alias))


@app.route("/wallets/<wallet_alias>/tx/history/")
@login_required
def wallet_tx_history(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_tx: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    idx = int(request.args.get("idx", default=0))

    return render_template(
        "wallet/history/txs/wallet_tx.jinja",
        idx=idx,
        wallet_alias=wallet_alias,
        wallet=wallet,
        history=True,
        specter=app.specter,
        rand=rand,
    )


@app.route("/wallets/<wallet_alias>/tx/utxo/", methods=["GET", "POST"])
@login_required
def wallet_tx_utxo(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_addresses: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    # check utxo list
    wallet.check_utxo()
    viewtype = "address" if request.args.get("view") != "label" else "label"
    idx = int(request.args.get("idx", default=0))
    if request.method == "POST":
        action = request.form["action"]
        if action == "updatelabel":
            label = request.form["label"]
            account = request.form["account"]
            if viewtype == "address":
                wallet.setlabel(account, label)
            else:
                for address in wallet.addresses_on_label(account):
                    wallet.setlabel(address, label)
                wallet.getdata()
    return render_template(
        "wallet/history/utxo/wallet_utxo.jinja",
        idx=idx,
        wallet_alias=wallet_alias,
        wallet=wallet,
        history=False,
        viewtype=viewtype,
        specter=app.specter,
        rand=rand,
    )


@app.route("/wallets/<wallet_alias>/receive/", methods=["GET", "POST"])
@login_required
def wallet_receive(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form["action"]
        if action == "newaddress":
            wallet.getnewaddress()
        elif action == "updatelabel":
            label = request.form["label"]
            wallet.setlabel(wallet.address, label)
    # check that current address is unused
    # and generate new one if it is
    wallet.check_unused()
    return render_template(
        "wallet/receive/wallet_receive.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
    )


@app.route("/get_fee/<blocks>")
@login_required
def fees(blocks):
    res = app.specter.estimatesmartfee(int(blocks))
    return res


@app.route("/get_txout_set_info")
@login_required
def txout_set_info():
    res = app.specter.rpc.gettxoutsetinfo()
    return res


@app.route("/get_scantxoutset_status")
@login_required
def get_scantxoutset_status():
    status = app.specter.rpc.scantxoutset("status", [])
    app.specter.info["utxorescan"] = status.get("progress", None) if status else None
    if app.specter.info["utxorescan"] is None:
        app.specter.utxorescanwallet = None
    return {
        "active": app.specter.info["utxorescan"] is not None,
        "progress": app.specter.info["utxorescan"],
    }


@app.route(
    "/wallets/<wallet_alias>/get_wallet_rescan_progress", methods=["GET", "POST"]
)
@login_required
def get_wallet_rescan_progress(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
        wallet.get_info()
        return {
            "active": wallet.rescan_progress is not None,
            "progress": wallet.rescan_progress,
        }
    except SpecterError as se:
        app.logger.error("SpecterError while get_wallet_rescan_progress: %s" % se)
        return {}


@app.route("/wallets/<wallet_alias>/send")
@login_required
def wallet_send(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if len(wallet.pending_psbts) > 0:
        return redirect(url_for("wallet_sendpending", wallet_alias=wallet_alias))
    else:
        return redirect(url_for("wallet_sendnew", wallet_alias=wallet_alias))


@app.route("/wallets/<wallet_alias>/send/new", methods=["GET", "POST"])
@login_required
def wallet_sendnew(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    # update balances in the wallet
    wallet.get_balance()
    # update utxo list for coin selection
    wallet.check_utxo()
    psbt = None
    addresses = [""]
    labels = [""]
    amounts = [0]
    fee_rate = 0.0
    err = None
    ui_option = "ui"
    recipients_txt = ""
    if request.method == "POST":
        action = request.form["action"]
        if action == "createpsbt":
            i = 0
            addresses = []
            labels = []
            amounts = []
            ui_option = request.form.get("ui_option")
            if "ui" in ui_option:
                while "address_{}".format(i) in request.form:
                    addresses.append(request.form["address_{}".format(i)])
                    amounts.append(float(request.form["btc_amount_{}".format(i)]))
                    labels.append(request.form["label_{}".format(i)])
                    if request.form["label_{}".format(i)] != "":
                        wallet.setlabel(addresses[i], labels[i])
                    i += 1
            else:
                recipients_txt = request.form["recipients"]
                for output in recipients_txt.splitlines():
                    addresses.append(output.split(",")[0].strip())
                    if request.form.get("amount_unit_text") == "sat":
                        amounts.append(float(output.split(",")[1].strip()) / 1e8)
                    else:
                        amounts.append(float(output.split(",")[1].strip()))
            subtract = bool(request.form.get("subtract", False))
            subtract_from = int(request.form.get("subtract_from", 1)) - 1
            selected_coins = request.form.getlist("coinselect")
            app.logger.info("selected coins: {}".format(selected_coins))
            if "dynamic" in request.form.get("fee_options"):
                fee_rate = float(request.form.get("fee_rate_dynamic")) * 1e5
            else:
                if request.form.get("fee_rate"):
                    fee_rate = float(request.form.get("fee_rate"))
            try:
                psbt = wallet.createpsbt(
                    addresses,
                    amounts,
                    subtract=subtract,
                    subtract_from=subtract_from,
                    fee_rate=fee_rate,
                    selected_coins=selected_coins,
                    readonly="estimate_fee" in request.form,
                )
                if psbt is None:
                    err = "Probably you don't have enough funds, or something else..."
                else:
                    # calculate new amount if we need to subtract
                    if subtract:
                        for v in psbt["tx"]["vout"]:
                            if addresses[0] in v["scriptPubKey"]["addresses"]:
                                amounts[0] = v["value"]
            except Exception as e:
                err = e
                app.logger.error(e)
            if err is None:
                if "estimate_fee" in request.form:
                    return psbt
                return render_template(
                    "wallet/send/sign/wallet_send_sign_psbt.jinja",
                    psbt=psbt,
                    labels=labels,
                    wallet_alias=wallet_alias,
                    wallet=wallet,
                    specter=app.specter,
                    rand=rand,
                )
        elif action == "importpsbt":
            try:
                b64psbt = "".join(request.form["rawpsbt"].split())
                psbt = wallet.importpsbt(b64psbt)
            except Exception as e:
                flash("Could not import PSBT: %s" % e, "error")
                return redirect(url_for("wallet_importpsbt", wallet_alias=wallet_alias))
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
        elif action == "openpsbt":
            psbt = ast.literal_eval(request.form["pending_psbt"])
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
        elif action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                flash("Could not delete Pending PSBT!", "error")
        elif action == "signhotwallet":
            passphrase = request.form["passphrase"]
            psbt = ast.literal_eval(request.form["psbt"])
            b64psbt = wallet.pending_psbts[psbt["tx"]["txid"]]["base64"]
            device = request.form["device"]
            if "devices_signed" not in psbt or device not in psbt["devices_signed"]:
                try:
                    # get device and sign with it
                    signed_psbt = app.specter.device_manager.get_by_alias(
                        device
                    ).sign_psbt(b64psbt, wallet, passphrase)
                    if signed_psbt["complete"]:
                        if "devices_signed" not in psbt:
                            psbt["devices_signed"] = []
                        psbt["devices_signed"].append(device)
                        psbt["sigs_count"] = len(psbt["devices_signed"])
                        raw = wallet.rpc.finalizepsbt(b64psbt)
                        if "hex" in raw:
                            psbt["raw"] = raw["hex"]
                    signed_psbt = signed_psbt["psbt"]
                except Exception as e:
                    signed_psbt = None
                    flash("Failed to sign PSBT: %s" % e, "error")
            else:
                signed_psbt = None
                flash("Device already signed the PSBT", "error")
            return render_template(
                "wallet/send/sign/wallet_send_sign_psbt.jinja",
                signed_psbt=signed_psbt,
                psbt=psbt,
                labels=labels,
                wallet_alias=wallet_alias,
                wallet=wallet,
                specter=app.specter,
                rand=rand,
            )
    return render_template(
        "wallet/send/new/wallet_send.jinja",
        psbt=psbt,
        ui_option=ui_option,
        recipients_txt=recipients_txt,
        labels=labels,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


@app.route("/wallets/<wallet_alias>/send/import")
@login_required
def wallet_importpsbt(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_send: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    err = None
    return render_template(
        "wallet/send/import/wallet_importpsbt.jinja",
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
        rand=rand,
        error=err,
    )


@app.route("/wallets/<wallet_alias>/send/pending/", methods=["GET", "POST"])
@login_required
def wallet_sendpending(wallet_alias):
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_sendpending: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form["action"]
        if action == "deletepsbt":
            try:
                wallet.delete_pending_psbt(
                    ast.literal_eval(request.form["pending_psbt"])["tx"]["txid"]
                )
            except Exception as e:
                app.logger.error("Could not delete Pending PSBT: %s" % e)
                flash("Could not delete Pending PSBT!", "error")
    pending_psbts = wallet.pending_psbts
    ######## Migration to multiple recipients format ###############
    for psbt in pending_psbts:
        if not isinstance(pending_psbts[psbt]["address"], list):
            pending_psbts[psbt]["address"] = [pending_psbts[psbt]["address"]]
            pending_psbts[psbt]["amount"] = [pending_psbts[psbt]["amount"]]
    ###############################################################
    return render_template(
        "wallet/send/pending/wallet_sendpending.jinja",
        pending_psbts=pending_psbts,
        wallet_alias=wallet_alias,
        wallet=wallet,
        specter=app.specter,
    )


@app.route("/wallets/<wallet_alias>/settings/", methods=["GET", "POST"])
@login_required
def wallet_settings(wallet_alias):
    error = None
    try:
        wallet = app.specter.wallet_manager.get_by_alias(wallet_alias)
    except SpecterError as se:
        app.logger.error("SpecterError while wallet_receive: %s" % se)
        return render_template("base.jinja", error=se, specter=app.specter, rand=rand)
    if request.method == "POST":
        action = request.form["action"]
        if action == "rescanblockchain":
            startblock = int(request.form["startblock"])
            try:
                res = wallet.rpc.rescanblockchain(startblock, timeout=1)
            except requests.exceptions.ReadTimeout:
                # this is normal behaviour in our usecase
                pass
            except Exception as e:
                app.logger.error("%s while rescanblockchain" % e)
                error = "%r" % e
            wallet.getdata()
        elif action == "abortrescan":
            res = wallet.rpc.abortrescan()
            if not res:
                error = "Failed to abort rescan. Maybe already complete?"
            wallet.getdata()
        elif action == "rescanutxo":
            explorer = None
            if "use_explorer" in request.form:
                explorer = app.specter.get_default_explorer()
            wallet.rescanutxo(explorer)
            app.specter.info["utxorescan"] = 1
            app.specter.utxorescanwallet = wallet.alias
        elif action == "abortrescanutxo":
            app.specter.abortrescanutxo()
            app.specter.info["utxorescan"] = None
            app.specter.utxorescanwallet = None
        elif action == "keypoolrefill":
            delta = int(request.form["keypooladd"])
            wallet.keypoolrefill(wallet.keypool, wallet.keypool + delta)
            wallet.keypoolrefill(
                wallet.change_keypool, wallet.change_keypool + delta, change=True
            )
            wallet.getdata()
        elif action == "deletewallet":
            app.specter.wallet_manager.delete_wallet(
                wallet, app.specter.bitcoin_datadir, app.specter.chain
            )
            response = redirect(url_for("index"))
            return response
        elif action == "rename":
            wallet_name = request.form["newtitle"]
            if not wallet_name:
                flash("Wallet name cannot be empty", "error")
            elif wallet_name == wallet.name:
                pass
            elif wallet_name in app.specter.wallet_manager.wallets_names:
                flash("Wallet already exists", "error")
            else:
                app.specter.wallet_manager.rename_wallet(wallet, wallet_name)

        return render_template(
            "wallet/settings/wallet_settings.jinja",
            purposes=purposes,
            wallet_alias=wallet_alias,
            wallet=wallet,
            specter=app.specter,
            rand=rand,
            error=error,
        )
    else:
        return render_template(
            "wallet/settings/wallet_settings.jinja",
            purposes=purposes,
            wallet_alias=wallet_alias,
            wallet=wallet,
            specter=app.specter,
            rand=rand,
            error=error,
        )


################# devices management #####################


@app.route("/new_device/", methods=["GET", "POST"])
@login_required
def new_device():
    err = None
    device_type = ""
    device_name = ""
    xpubs = ""
    strength = 128
    mnemonic = generate_mnemonic(strength=strength)
    if request.method == "POST":
        action = request.form["action"]
        device_type = request.form["device_type"]
        device_name = request.form["device_name"]
        if action == "newcolddevice":
            if not device_name:
                err = "Device name must not be empty"
            elif device_name in app.specter.device_manager.devices_names:
                err = "Device with this name already exists"
            xpubs = request.form["xpubs"]
            if not xpubs:
                err = "xpubs name must not be empty"
            keys, failed = Key.parse_xpubs(xpubs)
            if len(failed) > 0:
                err = "Failed to parse these xpubs:\n" + "\n".join(failed)
            if err is None:
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=keys
                )
                return redirect(url_for("device", device_alias=device.alias))
        elif action == "newhotdevice":
            if not device_name:
                err = "Device name must not be empty"
            elif device_name in app.specter.device_manager.devices_names:
                err = "Device with this name already exists"
            if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                err = "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
            mnemo = Mnemonic("english")
            if not mnemo.check(request.form["mnemonic"]):
                err = "Invalid mnemonic entered."
            range_start = int(request.form["range_start"])
            range_end = int(request.form["range_end"])
            if range_start > range_end:
                err = "Invalid address range selected."
            if err is None:
                mnemonic = request.form["mnemonic"]
                paths = [
                    l.strip()
                    for l in request.form["derivation_paths"].split("\n")
                    if len(l) > 0
                ]
                passphrase = request.form["passphrase"]
                file_password = request.form["file_password"]
                device = app.specter.device_manager.add_device(
                    name=device_name, device_type=device_type, keys=[]
                )
                device.setup_device(file_password, app.specter.wallet_manager)
                device.add_hot_wallet_keys(
                    mnemonic,
                    passphrase,
                    paths,
                    file_password,
                    app.specter.wallet_manager,
                    app.specter.chain != "main",
                    keys_range=[range_start, range_end],
                )
                return redirect(url_for("device", device_alias=device.alias))
        elif action == "generatemnemonic":
            strength = int(request.form["strength"])
            mnemonic = generate_mnemonic(strength=strength)
    return render_template(
        "device/new_device.jinja",
        device_type=device_type,
        device_name=device_name,
        xpubs=xpubs,
        mnemonic=mnemonic,
        strength=strength,
        error=err,
        specter=app.specter,
        rand=rand,
    )


@app.route("/devices/<device_alias>/", methods=["GET", "POST"])
@login_required
def device(device_alias):
    err = None
    try:
        device = app.specter.device_manager.get_by_alias(device_alias)
    except:
        return render_template(
            "base.jinja", error="Device not found", specter=app.specter, rand=rand
        )
    if not device:
        return redirect(url_for("index"))
    wallets = device.wallets(app.specter.wallet_manager)
    if request.method == "POST":
        action = request.form["action"]
        if action == "forget":
            if len(wallets) != 0:
                err = "Device could not be removed since it is used in wallets: {}.\nYou must delete those wallets before you can remove this device.".format(
                    [wallet.name for wallet in wallets]
                )
            else:
                app.specter.device_manager.remove_device(
                    device,
                    app.specter.wallet_manager,
                    bitcoin_datadir=app.specter.bitcoin_datadir,
                    chain=app.specter.chain,
                )
                return redirect("")
        elif action == "delete_key":
            key = request.form["key"]
            device.remove_key(Key.from_json({"original": key}))
        elif action == "rename":
            device_name = request.form["newtitle"]
            if not device_name:
                flash("Device name must not be empty", "error")
            elif device_name == device.name:
                pass
            elif device_name in app.specter.device_manager.devices_names:
                flash("Device already exists", "error")
            else:
                device.rename(device_name)
        elif action == "add_keys":
            strength = 128
            mnemonic = generate_mnemonic(strength=strength)
            return render_template(
                "device/new_device.jinja",
                mnemonic=mnemonic,
                strength=strength,
                device=device,
                device_alias=device_alias,
                specter=app.specter,
                rand=rand,
            )
        elif action == "morekeys":
            if device.hot_wallet:
                if len(request.form["mnemonic"].split(" ")) not in [12, 15, 18, 21, 24]:
                    err = "Invalid mnemonic entered: Must contain either: 12, 15, 18, 21, or 24 words."
                mnemo = Mnemonic("english")
                if not mnemo.check(request.form["mnemonic"]):
                    err = "Invalid mnemonic entered."
                range_start = int(request.form["range_start"])
                range_end = int(request.form["range_end"])
                if range_start > range_end:
                    err = "Invalid address range selected."
                if err is None:
                    mnemonic = request.form["mnemonic"]
                    paths = [
                        l.strip()
                        for l in request.form["derivation_paths"].split("\n")
                        if len(l) > 0
                    ]
                    passphrase = request.form["passphrase"]
                    file_password = request.form["file_password"]
                    device.add_hot_wallet_keys(
                        mnemonic,
                        passphrase,
                        paths,
                        file_password,
                        app.specter.wallet_manager,
                        app.specter.chain != "main",
                        keys_range=[range_start, range_end],
                    )
            else:
                # refactor to fn
                xpubs = request.form["xpubs"]
                keys, failed = Key.parse_xpubs(xpubs)
                err = None
                if len(failed) > 0:
                    err = "Failed to parse these xpubs:\n" + "\n".join(failed)
                    return render_template(
                        "device/new_device.jinja",
                        device=device,
                        device_alias=device_alias,
                        xpubs=xpubs,
                        error=err,
                        specter=app.specter,
                        rand=rand,
                    )
                if err is None:
                    device.add_keys(keys)
        elif action == "settype":
            device_type = request.form["device_type"]
            device.set_type(device_type)
    device = copy.deepcopy(device)
    device.keys.sort(
        key=lambda k: k.metadata["chain"] + k.metadata["purpose"], reverse=True
    )
    return render_template(
        "device/device.jinja",
        device=device,
        device_alias=device_alias,
        purposes=purposes,
        wallets=wallets,
        error=err,
        specter=app.specter,
        rand=rand,
    )


############### filters ##################


@app.template_filter("ascii20")
def ascii20(name):
    return to_ascii20(name)


@app.template_filter("datetime")
def timedatetime(s):
    return format(datetime.fromtimestamp(s), "%d.%m.%Y %H:%M")


@app.template_filter("btcamount")
def btcamount(value):
    value = round(float(value), 8)
    return "{:,.8f}".format(value).rstrip("0").rstrip(".")


@app.template_filter("btc2sat")
def btc2sat(value):
    value = int(round(float(value) * 1e8))
    return f"{value}"


@app.template_filter("feerate")
def feerate(value):
    value = float(value) * 1e8
    # workaround for minimal fee rate
    # because 1.01 doesn't look nice
    if value <= 1.02:
        value = 1
    return "{:,.2f}".format(value).rstrip("0").rstrip(".")


@app.template_filter("btcunitamount")
def btcunitamount(value):
    if app.specter.unit != "sat":
        return btcamount(value)
    value = float(value)
    return "{:,.0f}".format(round(value * 1e8))


@app.template_filter("bytessize")
def bytessize(value):
    value = float(value)
    return "{:,.0f}".format(value / float(1 << 30)) + " GB"


def notify_upgrade():
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
