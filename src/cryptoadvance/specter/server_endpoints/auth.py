import random
from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_login import login_required, current_user, logout_user
from flask import current_app as app
from ..helpers import alias
from ..user import User, hash_password, verify_password


rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
auth_endpoint = Blueprint("auth_endpoint", __name__)


@auth_endpoint.route("/login", methods=["GET", "POST"])
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


@auth_endpoint.route("/register", methods=["GET", "POST"])
def register():
    """ register """
    if request.method == "POST":
        username = request.form["username"]
        password = hash_password(request.form["password"])
        otp = request.form["otp"]
        user_id = alias(username)
        i = 1
        while app.specter.user_manager.get_user(user_id):
            i += 1
            user_id = "{}{}".format(alias(username), i)
        if app.specter.user_manager.get_user_by_username(username):
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
            return redirect(url_for("auth_endpoint.login"))
        else:
            flash(
                "Invalid registration link, \
please request a new link from the node operator.",
                "error",
            )
            return redirect("register?otp={}".format(otp))
    return render_template("register.jinja", specter=app.specter)


@auth_endpoint.route("/logout", methods=["GET", "POST"])
def logout():
    logout_user()
    flash("You were logged out", "info")
    return redirect(url_for("auth_endpoint.login"))


################### Util ######################
def redirect_login(request):
    flash("Logged in successfully.", "info")
    if request.form.get("next") and request.form.get("next") != "None":
        response = redirect(request.form["next"])
    else:
        response = redirect(url_for("index"))
    return response
