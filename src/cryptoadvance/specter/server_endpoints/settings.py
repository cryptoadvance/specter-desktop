import json
import logging
import os
import platform
import random
import secrets
import shutil
import sys
import tarfile
import time
import zipfile
from pathlib import Path

import pgpy
import requests
from flask import Blueprint, Flask
from flask import current_app as app
from flask import flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required

from ..helpers import (
    get_loglevel,
    get_startblock_by_chain,
    notify_upgrade,
    set_loglevel,
)
from ..persistence import write_devices, write_wallet
from ..specter_error import ExtProcTimeoutException, handle_exception
from ..user import hash_password
from ..util.sha256sum import sha256sum
from ..util.shell import get_last_lines_from_file
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
settings_endpoint = Blueprint("settings_endpoint", __name__)


@settings_endpoint.route("/", methods=["GET"])
@login_required
def settings():
    return redirect(url_for("settings_endpoint.general"))


@settings_endpoint.route("/general", methods=["GET", "POST"])
@login_required
def general():
    current_version = notify_upgrade(app, flash)
    explorer_id = app.specter.explorer_id
    explorer = ""
    fee_estimator = app.specter.fee_estimator
    fee_estimator_custom_url = app.specter.config.get("fee_estimator_custom_url", "")
    loglevel = get_loglevel(app)
    unit = app.specter.unit
    if request.method == "POST":
        action = request.form["action"]
        explorer_id = request.form["explorer"]
        explorer_data = app.config["EXPLORERS_LIST"][explorer_id]
        if explorer_id == "CUSTOM":
            explorer_data["url"] = request.form["custom_explorer"]
        fee_estimator = request.form["fee_estimator"]
        fee_estimator_custom_url = request.form["fee_estimator_custom_url"]
        unit = request.form["unit"]
        validate_merkleproof_bool = request.form.get("validatemerkleproof") == "on"

        if current_user.is_admin:
            loglevel = request.form["loglevel"]

        if action == "save":
            if current_user.is_admin:
                set_loglevel(app, loglevel)

            app.specter.update_explorer(explorer_id, explorer_data, current_user)
            app.specter.update_unit(unit, current_user)
            app.specter.update_merkleproof_settings(
                validate_bool=validate_merkleproof_bool
            )
            app.specter.update_fee_estimator(
                fee_estimator=fee_estimator,
                custom_url=fee_estimator_custom_url,
                user=current_user,
            )
            app.specter.check()
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
                            _("Failed to import wallet {}, error: {}").format(
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
                    wallet_obj.keypoolrefill(0, wallet_obj.IMPORT_KEYPOOL, change=False)
                    wallet_obj.keypoolrefill(0, wallet_obj.IMPORT_KEYPOOL, change=True)
                    wallet_obj.import_labels(wallet.get("labels", {}))
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
                            _("Failed to perform rescan for wallet: {}").format(e),
                            "error",
                        )
                    wallet_obj.getdata()
                except Exception:
                    flash(
                        _("Failed to import wallet {}").format(wallet["name"]), "error"
                    )
            flash(_("Specter data was successfully loaded from backup"), "info")
            if rescanning:
                flash(
                    _(
                        "Wallets are rescanning for transactions history.\n\
This may take a few hours to complete."
                    ),
                    "info",
                )

    return render_template(
        "settings/general_settings.jinja",
        fee_estimator=fee_estimator,
        fee_estimator_custom_url=fee_estimator_custom_url,
        loglevel=loglevel,
        validate_merkle_proofs=app.specter.config.get("validate_merkle_proofs") is True,
        unit=unit,
        specter=app.specter,
        current_version=current_version,
        rand=rand,
        supported_languages=app.supported_languages,
    )


@settings_endpoint.route("/tor", methods=["GET", "POST"])
@login_required
def tor():
    """
    controls the tor related settings
    GET for displaying the page, POST for updates
    param action might be "save", "test_tor" or "toggle_hidden_service"
    param proxy_url the Tor deamon url, usually something like socks5h://localhost:9050
    param only_tor "on" or something else ("off")
    """
    if not current_user.is_admin:
        flash(_("Only an admin is allowed to access this page."), "error")
        return redirect("")
    app.specter.reset_setup("torbrowser")
    current_version = notify_upgrade(app, flash)
    proxy_url = app.specter.proxy_url
    only_tor = app.specter.only_tor
    tor_control_port = app.specter.tor_control_port
    tor_type = app.specter.tor_type
    if request.method == "POST":
        action = request.form["action"]
        tor_type = request.form["tor_type"]
        proxy_url = request.form["proxy_url"]
        only_tor = request.form.get("only_tor") == "on"
        tor_control_port = request.form["tor_control_port"]
        hidden_service = request.form.get("hidden_service") == "on"

        if action == "save":
            logger.info("Updating Tor settings...")
            app.specter.update_tor_type(tor_type, current_user)

            if tor_type == "custom":
                app.specter.update_proxy_url(proxy_url, current_user)
                app.specter.update_tor_control_port(tor_control_port, current_user)
            else:
                proxy_url = "socks5h://localhost:9050"
                tor_control_port = ""

            app.specter.update_only_tor(only_tor, current_user)
            if hidden_service != app.specter.config["tor_status"]:
                if not app.config["DEBUG"]:
                    if app.specter.config["auth"].get("method", "none") == "none":
                        flash(
                            "Enabling Tor hidden service will expose your Specter for remote access.<br>It is therefore required that you set up authentication tab for Specter first to prevent unauthorized access.<br><br>Please go to Settings -> Authentication and set up an authentication method and retry.",
                            "error",
                        )
                    else:
                        if hasattr(current_user, "is_admin") and current_user.is_admin:
                            if not hidden_service:
                                stop_hidden_services(app)
                                app.specter.toggle_tor_status()
                                flash(
                                    "Tor hidden service turn off successfully", "info"
                                )
                            else:
                                try:
                                    start_hidden_service(app)
                                    app.specter.toggle_tor_status()
                                    flash(
                                        "Tor hidden service turn on successfully",
                                        "info",
                                    )
                                except Exception as e:
                                    handle_exception(e)
                                    flash(
                                        "Failed to start Tor hidden service. Make sure you have Tor running with ControlPort configured and try again. Error returned: {}".format(
                                            e
                                        ),
                                        "error",
                                    )
                else:
                    flash(
                        "Can't toggle hidden service while Specter is running in DEBUG mode",
                        "error",
                    )

            app.specter.check()

        elif action == "starttor":
            logger.info("Starting Tor...")
            try:
                app.specter.tor_daemon.start_tor_daemon()
                flash(_("Specter has started Tor"))
            except Exception as e:
                flash(_("Failed to start Tor, error: {}").format(e), "error")
                logger.error(f"Failed to start Tor, error: {e}")
        elif action == "stoptor":
            logger.info("Stopping Tor...")
            try:
                app.specter.tor_daemon.stop_tor_daemon()
                time.sleep(1)
                flash(_("Specter stopped Tor successfully"))
            except Exception as e:
                flash(_("Failed to stop Tor, error: {}").format(e), "error")
                logger.error(f"Failed to start Tor, error: {e}")
        elif action == "uninstalltor":
            logger.info("Uninstalling Tor...")
            try:
                if app.specter.is_tor_dameon_running():
                    app.specter.tor_daemon.stop_tor_daemon()
                shutil.rmtree(os.path.join(app.specter.data_folder, "tor-binaries"))
                os.remove(os.path.join(app.specter.data_folder, "torrc"))
                flash(_("Tor uninstalled successfully"))
            except Exception as e:
                flash(_("Failed to uninstall Tor, error: {}").format(e), "error")
                logger.error(f"Failed to uninstall Tor, error: {e}")
        elif action == "test_tor":
            logger.info("Testing the Tor connection...")
            try:
                requests_session = requests.Session()
                requests_session.proxies["http"] = proxy_url
                requests_session.proxies["https"] = proxy_url
                res = requests_session.get(
                    # "http://expyuzz4wqqyqhjn.onion",  # Tor Project onion website (seems to be down)
                    "https://protonirockerxow.onion",  # Proton mail onion website
                    timeout=30,
                )
                tor_connectable = res.status_code == 200
                if tor_connectable:
                    flash(_("Tor requests test completed successfully!"), "info")
                else:
                    flash(
                        _(
                            "Failed to make test request over Tor. Status-Code: {}"
                        ).format(res.status_code),
                        "error",
                    )
                    logger.error(
                        f"Failed to make test request over Tor. Status-Code: {res.status_code}"
                    )
                    if tor_type == "builtin":
                        logger.error("Tor-Logs:")
                        app.specter.tor_daemon.stop_tor_daemon()
                        time.sleep(1)
                        logger.error(app.specter.tor_daemon.get_logs())
                        app.specter.tor_daemon.start_tor_daemon()
            except Exception as e:
                flash(
                    _("Failed to make test request over Tor.\nError: {}").format(e),
                    "error",
                )
                logger.error(f"Failed to make test request over Tor.\nError: {e}")
                if tor_type == "builtin":
                    logger.error("Tor-Logs:")
                    app.specter.tor_daemon.stop_tor_daemon()
                    time.sleep(1)
                    logger.error(app.specter.tor_daemon.get_logs())
                    app.specter.tor_daemon.start_tor_daemon()
                tor_connectable = False

    return render_template(
        "settings/tor_settings.jinja",
        tor_type=tor_type,
        proxy_url=proxy_url,
        only_tor=only_tor,
        tor_control_port=tor_control_port,
        tor_service_id=app.tor_service_id,
        torbrowser_installed=os.path.isfile(app.specter.torbrowser_path),
        torbrowser_running=app.specter.is_tor_dameon_running(),
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


@settings_endpoint.route("/auth", methods=["GET", "POST"])
@login_required
def auth():
    current_version = notify_upgrade(app, flash)
    auth = app.specter.config["auth"]
    method = auth["method"]
    rate_limit = auth["rate_limit"]
    registration_link_timeout = auth["registration_link_timeout"]
    users = None
    if current_user.is_admin and method == "usernamepassword":
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
                method = request.form["method"]
                rate_limit = request.form["rate_limit"]
                registration_link_timeout = request.form["registration_link_timeout"]
            min_chars = int(auth["password_min_chars"])
            if specter_username:
                if current_user.username != specter_username:
                    if app.specter.user_manager.get_user_by_username(specter_username):
                        flash(
                            _("Username is already taken, please choose another one"),
                            "error",
                        )
                        return render_template(
                            "settings/auth_settings.jinja",
                            method=method,
                            rate_limit=rate_limit,
                            registration_link_timeout=registration_link_timeout,
                            users=users,
                            specter=app.specter,
                            current_version=current_version,
                            rand=rand,
                        )
                current_user.username = specter_username
                if specter_password:
                    if len(specter_password) < min_chars:
                        flash(
                            _(
                                "Please enter a password of a least {} characters"
                            ).format(min_chars),
                            "error",
                        )
                        return render_template(
                            "settings/auth_settings.jinja",
                            method=method,
                            rate_limit=rate_limit,
                            registration_link_timeout=registration_link_timeout,
                            users=users,
                            specter=app.specter,
                            current_version=current_version,
                            rand=rand,
                        )
                    current_user.password = hash_password(specter_password)
                current_user.save_info()
            if current_user.is_admin:
                app.specter.update_auth(method, rate_limit, registration_link_timeout)
                if method in ["rpcpasswordaspin", "passwordonly", "usernamepassword"]:
                    if method == "passwordonly":
                        new_password = request.form.get("specter_password_only", "")
                        if new_password:
                            if len(new_password) < min_chars:
                                flash(
                                    _(
                                        "Please enter a password of a least {} characters"
                                    ).format(min_chars),
                                    "error",
                                )
                                return render_template(
                                    "settings/auth_settings.jinja",
                                    method=method,
                                    rate_limit=rate_limit,
                                    registration_link_timeout=registration_link_timeout,
                                    users=users,
                                    specter=app.specter,
                                    current_version=current_version,
                                    rand=rand,
                                )

                            current_user.password = hash_password(new_password)
                            current_user.save_info()
                    if method == "usernamepassword":
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
                new_otp = secrets.token_urlsafe(16)
                now = time.time()
                timeout = int(registration_link_timeout)
                timeout = 0 if timeout < 0 else timeout
                if timeout > 0:
                    expiry = now + timeout * 60 * 60
                    if timeout > 1:
                        expiry_desc = " " + _("(expires in {} hours)").format(timeout)
                    else:
                        expiry_desc = " " + _("(expires in 1 hour)")
                else:
                    expiry = 0
                    expiry_desc = ""
                app.specter.otp_manager.add_new_user_otp(
                    {"otp": new_otp, "created_at": now, "expiry": expiry}
                )
                flash(
                    _("New user link generated{}: {}auth/register?otp={}").format(
                        expiry_desc, request.url_root, new_otp
                    ),
                    "info",
                )
            else:
                flash(
                    _("Error: Only the admin account can issue new registration links"),
                    "error",
                )
        elif action == "deleteuser":
            delete_user = request.form["deleteuser"]
            user = app.specter.user_manager.get_user(delete_user)
            if current_user.is_admin:
                app.specter.delete_user(user)
                users.remove(user)
                flash(
                    _("User {} was deleted successfully").format(user.username), "info"
                )
            else:
                flash(_("Error: Only the admin account can delete users"), "error")
    return render_template(
        "settings/auth_settings.jinja",
        method=method,
        rate_limit=rate_limit,
        registration_link_timeout=registration_link_timeout,
        users=users,
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


@settings_endpoint.route("/hwi", methods=["GET", "POST"])
@login_required
def hwi():
    current_version = notify_upgrade(app, flash)
    if request.method == "POST":
        hwi_bridge_url = request.form["hwi_bridge_url"]
        app.specter.update_hwi_bridge_url(hwi_bridge_url, current_user)
        flash(_("HWIBridge URL is updated! Don't forget to whitelist Specter!"))
    return render_template(
        "settings/hwi_settings.jinja",
        specter=app.specter,
        current_version=current_version,
        rand=rand,
    )


@settings_endpoint.route("/assets/set_label", methods=["POST"])
@login_required
def set_asset_label():
    asset = request.form["asset"]
    label = request.form["label"].rstrip()
    if label.lower() in ["btc", "bitcoin", "sat", "lbtc"]:
        return f'Label "{label}" is not allowed', 500
    try:
        app.specter.update_asset_label(asset, label)
    except Exception as e:
        return str(e), 500
    return {"success": True}


################## Settings util endpoints #######################

# Specter backup file
@settings_endpoint.route("/specter_backup.zip")
@login_required
def backup_file():
    return send_file(
        app.specter.specter_backup_file(),
        attachment_filename="specter-backup.zip",
        as_attachment=True,
    )
