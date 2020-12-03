import random, traceback
from datetime import datetime

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import login_required, current_user
from ..helpers import (
    generate_mnemonic,
    notify_upgrade,
)
from ..specter import Specter
from ..specter_error import SpecterError
from ..util.tor import start_hidden_service, stop_hidden_services

from pathlib import Path

env_path = Path(".") / ".flaskenv"
from dotenv import load_dotenv

load_dotenv(env_path)

from flask import current_app as app
from .filters import filters_bp

app.register_blueprint(filters_bp)

# Setup specter endpoints
from .auth import auth_endpoint
from .devices import devices_endpoint
from .price import price_endpoint
from .settings import settings_endpoint
from .wallets import wallets_endpoint

app.register_blueprint(auth_endpoint, url_prefix="/auth")
app.register_blueprint(devices_endpoint, url_prefix="/devices")
app.register_blueprint(price_endpoint, url_prefix="/price")
app.register_blueprint(settings_endpoint, url_prefix="/settings")
app.register_blueprint(wallets_endpoint, url_prefix="/wallets")

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


################ Specter global routes ####################
@app.route("/")
@login_required
def index():
    notify_upgrade(app, flash)
    if len(app.specter.wallet_manager.wallets) > 0:
        return redirect(
            url_for(
                "wallets_endpoint.wallet",
                wallet_alias=app.specter.wallet_manager.wallets[
                    app.specter.wallet_manager.wallets_names[0]
                ].alias,
            )
        )

    return redirect("about")


@app.route("/about")
@login_required
def about():
    notify_upgrade(app, flash)

    return render_template("base.jinja", specter=app.specter, rand=rand)


# TODO: Move all these below to REST API

################ Utils ####################


@app.route("/generatemnemonic/", methods=["GET", "POST"])
@login_required
def generatemnemonic():
    return {"mnemonic": generate_mnemonic(strength=int(request.form["strength"]))}


################ RPC data utils ####################
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
