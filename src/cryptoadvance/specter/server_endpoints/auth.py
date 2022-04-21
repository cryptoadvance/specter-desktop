import random
import time

from flask import Blueprint, Flask
from flask import current_app as app
from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required, logout_user

from ..helpers import alias
from ..services import ExtensionException
from ..user import User, hash_password, verify_password

rand = random.randint(0, 1e32)  # to force style refresh
last_sensitive_request = 0  # to rate limit sensitive requests

# Setup endpoint blueprint
auth_endpoint = Blueprint("auth_endpoint", __name__)


@auth_endpoint.route("/login", methods=["GET", "POST"])
@app.csrf.exempt
def login():
    """login"""
    if request.method == "POST":
        rate_limit()
        auth = app.specter.config["auth"]

        if auth["method"] == "none":
            app.login("admin")
            app.logger.info("AUDIT: Successful Login no credentials")
            return redirect_login(request)

        if auth["method"] == "rpcpasswordaspin":
            # TODO: check the password via RPC-call
            if (
                app.specter.default_node.rpc is None
                or not app.specter.default_node.rpc.test_connection()
            ):
                if app.specter.default_node.password == request.form["password"]:
                    app.login("admin", request.form["password"])
                    app.logger.info(
                        "AUDIT: Successfull Login via RPC-credentials (node disconnected)"
                    )
                    return redirect_login(request)

                flash(
                    _(
                        "We could not check your password, maybe Bitcoin Core is not running or not configured?"
                    ),
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
            rpc = app.specter.default_node.rpc.clone()
            rpc.password = request.form["password"]
            if rpc.test_connection():
                app.login("admin", request.form["password"])
                app.logger.info("AUDIT: Successfull Login via RPC-credentials")
                return redirect_login(request)

        elif auth["method"] == "passwordonly":
            password = request.form["password"]
            if verify_password(app.specter.user_manager.admin.password_hash, password):
                app.login("admin", request.form["password"])
                return redirect_login(request)

        elif auth["method"] == "usernamepassword":
            # TODO: This way both "User" and "user" will pass as usernames, should there be strict check on that here? Or should we keep it like this?
            username = request.form["username"]
            password = request.form["password"]
            user = app.specter.user_manager.get_user_by_username(username)
            if user:
                if verify_password(user.password_hash, password):
                    app.login(user.id, request.form["password"])
                    return redirect_login(request)

        # Either invalid method or incorrect credentials
        flash(_("Invalid username or password"), "error")
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


@auth_endpoint.route("/register", methods=["GET", "POST"])
def register():
    """register"""
    if request.method == "POST":
        rate_limit()
        username = request.form["username"]
        password = request.form["password"]
        otp = request.form["otp"]
        if not username:
            flash(
                _("Please enter a username."),
                "error",
            )
            return redirect("register?otp={}".format(otp))
        min_chars = int(app.specter.config["auth"]["password_min_chars"])
        if not password or len(password) < min_chars:
            flash(
                _("Please enter a password of a least {} characters.").format(
                    min_chars
                ),
                "error",
            )
            return redirect("register?otp={}".format(otp))
        if app.specter.otp_manager.validate_new_user_otp(otp):
            user_id = alias(username)
            i = 1
            while app.specter.user_manager.get_user(user_id):
                i += 1
                user_id = "{}{}".format(alias(username), i)
            if app.specter.user_manager.get_user_by_username(username):
                flash(
                    _("Username is already taken, please choose another one"), "error"
                )
                return redirect("register?otp={}".format(otp))
            app.specter.otp_manager.remove_new_user_otp(otp)
            config = {
                "explorers": {"main": "", "test": "", "regtest": "", "signet": ""},
                "hwi_bridge_url": "/hwi/api/",
            }

            user = app.specter.user_manager.create_user(
                user_id=user_id,
                username=username,
                plaintext_password=password,
                config=config,
            )

            flash(
                _(
                    "You have registered successfully, \
please login with your new account to start using Specter"
                )
            )
            return redirect(url_for("auth_endpoint.login"))
        else:
            flash(
                _(
                    "Invalid registration link, \
please request a new link from the node operator."
                ),
                "error",
            )
            return redirect("register?otp={}".format(otp))
    return render_template("register.jinja", specter=app.specter)


@auth_endpoint.route("/logout", methods=["GET", "POST"])
def logout():
    # Clear the decrypted user_secret from memory
    current_user.plaintext_user_secret = None

    logout_user()
    if "timeout" in request.args:
        flash(_("You were automatically logged out"), "info")
    else:
        flash(_("You were logged out"), "info")
    return redirect(url_for("auth_endpoint.login"))


@auth_endpoint.route("/toggle_hide_sensitive_info/", methods=["POST"])
@login_required
@app.csrf.exempt  # might get called by a timeout in the browser --> csrf-issues
def toggle_hide_sensitive_info():
    try:
        app.specter.update_hide_sensitive_info(
            not app.specter.hide_sensitive_info, current_user
        )
        return {"success": True}
    except Exception as e:
        app.logger.warning(
            "Failed to update sensitive info display settings. Exception: {}".format(e)
        )
    return {"success": False}


################### Util ######################
def redirect_login(request):
    flash(_("Logged in successfully."), "info")

    # If the user is auto-logged out, hide_sensitive_info will be set. If they're
    #   explicitly logging in now, clear the setting and reveal user's info.
    if app.specter.hide_sensitive_info:
        app.specter.update_hide_sensitive_info(False, current_user)

    if request.form.get("next") and request.form.get("next") != "None":
        response = redirect(request.form["next"])
    else:
        response = redirect(url_for("index"))

    for service_id in app.specter.user_manager.get_user().services:
        try:
            service_cls = app.specter.service_manager.get_service(service_id)
            service_cls.on_user_login()
        except ExtensionException as ee:
            if not str(ee).startswith("No such plugin"):
                raise ee
        except Exception as e:
            app.logger.exception(e)

    return response


def rate_limit():
    global last_sensitive_request
    limit = int(app.specter.config["auth"]["rate_limit"])
    if limit < 0:
        limit = 0
    now = time.time()
    if (
        last_sensitive_request != 0
        and limit > 0
        and last_sensitive_request + limit > now
    ):
        remaining_time = last_sensitive_request + limit - now
        time.sleep(remaining_time)
    last_sensitive_request = time.time()
