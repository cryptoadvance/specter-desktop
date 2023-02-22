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

import cryptography
import pgpy
import requests
from cryptoadvance.specter.util.wallet_importer import WalletImporter
from flask import Blueprint, Flask
from flask import current_app as app
from flask import jsonify, redirect, render_template, request, send_file, url_for
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required

from ..helpers import (
    get_loglevel,
    get_startblock_by_chain,
    notify_upgrade,
    set_loglevel,
)
from ..persistence import write_devices, write_wallet
from ..server_endpoints import flash
from ..services.service import callbacks
from ..specter_error import SpecterError, handle_exception
from ..user import UserSecretException
from ..util.sha256sum import sha256sum
from ..util.shell import get_last_lines_from_file
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
settings_endpoint = Blueprint("settings_endpoint", __name__)


@settings_endpoint.context_processor
def inject_common_stuff():
    """Can be used in all jinja2 templates of this Blueprint
    Injects the additional settings_tabs via extentions
    """
    ext_settingstabs = app.specter.service_manager.execute_ext_callbacks(
        callbacks.add_settingstabs
    )
    return dict(ext_settingstabs=ext_settingstabs)


@settings_endpoint.route("/", methods=["GET"])
@login_required
def settings():
    return redirect(url_for("settings_endpoint.general"))


@settings_endpoint.route("/general", methods=["GET", "POST"])
@login_required
def general():
    current_version = notify_upgrade(app, flash)
    explorer_id = app.specter.explorer_id
    fee_estimator = app.specter.fee_estimator
    fee_estimator_custom_url = app.specter.config.get("fee_estimator_custom_url", "")
    loglevel = get_loglevel(app)
    unit = app.specter.unit
    services = app.specter.service_manager.services
    if request.method == "POST":
        action = request.form["action"]

        autohide_sensitive_info_timeout = request.form[
            "autohide_sensitive_info_timeout"
        ]
        if autohide_sensitive_info_timeout == "NEVER":
            autohide_sensitive_info_timeout = None
        elif autohide_sensitive_info_timeout == "CUSTOM":
            autohide_sensitive_info_timeout = int(
                request.form["custom_autohide_sensitive_info_timeout"]
            )
        else:
            autohide_sensitive_info_timeout = int(autohide_sensitive_info_timeout)

        if "autologout_timeout" in request.form:
            # Is only in the form if specter.config.auth.method != "none"
            autologout_timeout = request.form["autologout_timeout"]
            if autologout_timeout == "NEVER":
                autologout_timeout = None
            elif autologout_timeout == "CUSTOM":
                autologout_timeout = int(request.form["custom_autologout_timeout"])
            else:
                autologout_timeout = int(autologout_timeout)
        else:
            autologout_timeout = None

        explorer_id = request.form["explorer"]
        explorer_data = app.config["EXPLORERS_LIST"][explorer_id]
        if explorer_id == "CUSTOM":
            explorer_data["url"] = request.form["custom_explorer"]
        fee_estimator = request.form["fee_estimator"]
        fee_estimator_custom_url = request.form["fee_estimator_custom_url"]
        unit = request.form["unit"]
        validate_merkleproof_bool = request.form.get("validatemerkleproof") == "on"
        if current_user.is_admin:
            active_services = []
            for service_name in services:
                if request.form.get(f"service_{service_name}"):
                    active_services.append(service_name)

            loglevel = request.form["loglevel"]

        if action == "save":
            if current_user.is_admin:
                set_loglevel(app, loglevel)

            app.specter.config_manager.update_autohide_sensitive_info_timeout(
                autohide_sensitive_info_timeout, current_user
            )
            app.specter.config_manager.update_autologout_timeout(
                autologout_timeout, current_user
            )

            app.specter.update_explorer(explorer_id, explorer_data, current_user)
            app.specter.update_unit(unit, current_user)
            app.specter.update_merkleproof_settings(
                validate_bool=validate_merkleproof_bool
            )
            if current_user.is_admin:
                app.specter.service_manager.set_active_services(active_services)
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
            logger.info(f"Importing {len(restore_wallets)} wallets ...")
            counter = {
                "success": 0,
                "specific_error": 0,
                "unspecific_error": 0,
                "rescan_error": 0,
            }
            for wallet in restore_wallets:

                try:
                    logger.info(f"Importing wallet {wallet['name']}")
                    wallet_importer = WalletImporter(json.dumps(wallet), app.specter)
                    wallet_importer.create_wallet(app.specter.wallet_manager)
                    wallet_importer.rescan_as_needed(app.specter)
                    counter["success"] += 1
                except SpecterError as se:
                    error_type = (
                        "rescan_error" if "rescan" in str(se) else "specific_error"
                    )
                    flash(f"Wallet '{wallet.get('name')}': {se} (skipped)", "error")
                    counter[error_type] += 1
                except Exception as e:
                    flash(
                        f"Error while importing wallet {wallet['name']}, check logs for details! (skipped)",
                        "error",
                    )
                    logger.exception(
                        f"Error while importing wallet {wallet['name']}: {e}"
                    )
                    counter["unspecific_error"] += 1

            counter["errors_sum"] = (
                counter["rescan_error"]
                + counter["specific_error"]
                + counter["unspecific_error"]
            )
            if counter["success"] > 0:
                message = f"{counter['success']} wallets successfully restored. "

            else:
                message = f"Sorry, this doesn't went that well. "
            if counter["errors_sum"] > 0:
                message += "however, we had " if counter["success"] > 0 else "We had "
                message += f"""<br>
                Successful imports: {counter["success"]}<br>
                Specific errors:    {counter["specific_error"]}<br>
                Unspecific errors:  {counter["unspecific_error"]} (create an issue about it on github)<br>
                Rescan issues:      {counter["rescan_error"]}<br>
                """
            if rescanning:
                message += "Wallets are rescanning for transactions history. This may take a few hours to complete."
            flash(message, "info")

    return render_template(
        "settings/general_settings.jinja",
        services=services,
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
    # This is true if the Python interpreter has been bundled with the application into a single executable, so basically it is true for the apps but not for pip-installations
    tor_builtin_possible = getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")
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
                logger.exception(f"Failed to start Tor, error: {e}", e)
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
                logger.exception(f"Failed to uninstall Tor, error: {e}", e)
        elif action == "test_tor":
            logger.info("Testing the Tor connection...")
            try:
                requests_session = requests.Session()
                requests_session.proxies["http"] = proxy_url
                requests_session.proxies["https"] = proxy_url
                res = requests_session.get(
                    "http://2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion/",  # Tor Project onion v3 website
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
                logger.exception(
                    f"Failed to make test request over Tor.\nError: {e}", e
                )
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
        tor_builtin_possible=tor_builtin_possible,
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
    # TODO: Simplify this endpoint. Separate out setting the Authentication mode from all
    # the other options here: updating admin username/password, adding users, deleting
    # users, etc. Do those in simple separate screens with their own endpoints.
    current_version = notify_upgrade(app, flash)
    auth = app.specter.config["auth"]
    method = auth["method"]
    rate_limit = auth["rate_limit"]
    registration_link_timeout = auth["registration_link_timeout"]
    users = None

    if (
        request.method == "GET"
        and current_user.is_admin
        and app.config["LOGIN_DISABLED"] == False
        and not current_user.plaintext_user_secret
    ):
        # Password protection is enabled but the admin user doesn't have their
        # user_secret decrypted. Force them to login again to prevent problems if they
        # try to change their password (changing password requires re-encrypting the
        # user_secret... which we can't do if it isn't decrypted first).
        flash(_("Must login again to before making Authentication changes"))
        return redirect(
            url_for("auth_endpoint.login")
            + "?next="
            + url_for("settings_endpoint.auth")
        )

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
                            has_service_encrypted_storage=app.specter.service_manager.user_has_encrypted_storage(
                                current_user
                            ),
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
                            has_service_encrypted_storage=app.specter.service_manager.user_has_encrypted_storage(
                                current_user
                            ),
                        )
                    current_user.set_password(specter_password)

                current_user.save_info()

            if current_user.is_admin:
                app.specter.update_auth(method, rate_limit, registration_link_timeout)
                if method in ["rpcpasswordaspin", "passwordonly", "usernamepassword"]:
                    if method == "passwordonly":
                        specter_password = request.form.get("specter_password_only")
                        if specter_password and len(specter_password) < min_chars:
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
                                has_service_encrypted_storage=app.specter.service_manager.user_has_encrypted_storage(
                                    current_user
                                ),
                            )
                        elif not specter_password:
                            # Set to the default
                            specter_password = "admin"

                        try:
                            current_user.set_password(specter_password)
                        except UserSecretException as e:
                            # Most likely the admin User is logged in but the
                            # plaintext_user_secret is not available in memory (happens
                            # when the server restarts).
                            logger.warn(e)
                            flash(
                                _(
                                    "Error re-encrypting Service data. Log out and log back in before trying again."
                                ),
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
                                has_service_encrypted_storage=app.specter.service_manager.user_has_encrypted_storage(
                                    current_user
                                ),
                            )

                        current_user.save_info()

                        flash(
                            _("Admin password successfully updated"),
                            "info",
                        )

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

                    # if there is no password, we have to delete the previously encrypted data from services
                    for user in app.specter.user_manager.users:
                        app.specter.service_manager.delete_services_with_encrypted_storage(
                            user
                        )

            # Redirect if a URL was given via the next variable
            if request.form.get("next") and request.form.get("next") != "":
                return redirect(request.form.get("next"))
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
                # TODO: delete should be done by UserManager
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
        has_service_encrypted_storage=app.specter.service_manager.user_has_encrypted_storage(
            current_user
        ),
        next=request.args.get("next", ""),
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
    if label.lower() in ["btc", "bitcoin", "sat", "lbtc", "tlbtc"]:
        return f'Label "{label}" is not allowed', 500
    try:
        app.specter.update_asset_label(asset, label)
    except Exception as e:
        logger.exception(e)
        return str(e), 500
    return {"success": True}


@settings_endpoint.route("/assets/", methods=["GET"])
@login_required
def assets():
    """List of all known / labeled assets"""
    return app.specter.asset_labels


@settings_endpoint.route("/assets/<asset>/", methods=["GET"])
@login_required
def get_asset(asset):
    """Get info about particular asset. Accepts either label or hex asset"""
    try:
        # check if we've got label, not an asset
        if len(asset) != 64:
            for a, lbl in app.specter.asset_labels.items():
                if lbl == asset:
                    return {"asset": a, "label": lbl}
            return {"error": "asset lookup by label failed"}, 404
        return {"asset": asset, "label": app.specter.asset_label(asset)}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}, 500


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
