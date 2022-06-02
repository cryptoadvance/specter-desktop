from ..services.callbacks import flask_before_request
import random, traceback
from time import time
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import MethodNotAllowed, NotFound
from flask import render_template, request, redirect, url_for, flash, g
from flask_babel import lazy_gettext as _
from ..specter_error import SpecterError, ExtProcTimeoutException
from pathlib import Path

env_path = Path(".") / ".flaskenv"
from dotenv import load_dotenv

load_dotenv(env_path)

from flask import current_app as app
from .filters import filters_bp

app.register_blueprint(filters_bp)

# Setup specter endpoints
from .welcome import welcome_endpoint
from .auth import auth_endpoint
from .devices import devices_endpoint
from .nodes import nodes_endpoint
from .price import price_endpoint
from .settings import settings_endpoint
from .setup import setup_endpoint
from .wallets import wallets_endpoint
from .wallets_api import wallets_endpoint_api
from ..rpc import RpcError

# Services live in their own separate path
from cryptoadvance.specter.services.controller import services_endpoint

spc_prefix = app.config["SPECTER_URL_PREFIX"]
app.register_blueprint(welcome_endpoint, url_prefix=f"{spc_prefix}/welcome")
app.register_blueprint(auth_endpoint, url_prefix=f"{spc_prefix}/auth")
app.register_blueprint(devices_endpoint, url_prefix=f"{spc_prefix}/devices")
app.register_blueprint(nodes_endpoint, url_prefix=f"{spc_prefix}/nodes")
app.register_blueprint(price_endpoint, url_prefix=f"{spc_prefix}/price")
app.register_blueprint(services_endpoint, url_prefix=f"{spc_prefix}/services")
app.register_blueprint(settings_endpoint, url_prefix=f"{spc_prefix}/settings")
app.register_blueprint(setup_endpoint, url_prefix=f"{spc_prefix}/setup")
app.register_blueprint(wallets_endpoint, url_prefix=f"{spc_prefix}/wallets")
app.register_blueprint(wallets_endpoint_api, url_prefix=f"{spc_prefix}/wallets")

rand = random.randint(0, 1e32)  # to force style refresh

########## exception handlers ##############
@app.errorhandler(RpcError)
def server_rpc_error(rpce):
    """Specific SpecterErrors get passed on to the User as flash"""
    if rpce.error_code == -18:  # RPC_WALLET_NOT_FOUND
        flash(
            _("Wallet not found. Specter reloaded all wallets, please try again."),
            "error",
        )
    else:
        flash(_("Bitcoin Core RpcError: {}").format(str(rpce)), "error")
    try:
        app.specter.wallet_manager.update()
    except SpecterError as se:
        flash(str(se), "error")
    return redirect(url_for("welcome_endpoint.about"))


@app.errorhandler(SpecterError)
def server_specter_error(se):
    """Specific SpecterErrors get passed on to the User as flash"""
    flash(str(se), "error")
    try:
        app.specter.wallet_manager.update()
    except SpecterError as se:
        flash(str(se), "error")
    if request.method == "POST":
        return redirect(request.url)
    # potentially avoiding http loops. Might be improvable but how?
    else:
        return redirect(url_for("welcome_endpoint.about"))


@app.errorhandler(NotFound)
def server_notFound_error(e):
    """Unspecific Exceptions get a 404 Error-Page"""
    # if rpc is not available
    app.logger.error("Could not find Resource (404): %s" % request.url)
    return render_template("500.jinja", error=e), 404


@app.errorhandler(Exception)
def server_error(e):
    """Unspecific Exceptions get a 500 Error-Page"""
    # if rpc is not available
    if app.specter.rpc is None or not app.specter.rpc.test_connection():
        # make sure specter knows that rpc is not there
        app.specter.check()
    app.logger.error("Uncaught exception: %s" % e)
    trace = traceback.format_exc()
    app.logger.error(trace)
    return render_template("500.jinja", error=e, traceback=trace), 500


@app.errorhandler(ExtProcTimeoutException)
def server_error_timeout(e):
    """Unspecific Exceptions get a 500 Error-Page"""
    # if rpc is not available
    if app.specter.rpc is None or not app.specter.rpc.test_connection():
        # make sure specter knows that rpc is not there
        app.specter.check()
    app.logger.error("ExternalProcessTimeoutException: %s" % e)
    flash(
        _(
            "Bitcoin Core is not coming up in time. Maybe it's just slow but please check the logs below"
        ),
        "warn",
    )
    return redirect(
        url_for(
            "node_settings.bitcoin_core_internal_logs",
            node_alias=app.specter.node.alias,
        )
    )


@app.errorhandler(CSRFError)
def server_error_csrf(e):
    """CSRF token missing. Most likely session expired.
    If persisting after refresh this could mean the front-end
    is not sending the CSRF token properly in some form"""
    app.logger.error("CSRF Exception: %s" % e)
    trace = traceback.format_exc()
    app.logger.error(trace)
    flash(_("Session expired. Please refresh and try again."), "error")
    return redirect(request.url)


@app.errorhandler(MethodNotAllowed)
def server_error_405(e):
    """405 method not allowed. Token might have expired."""
    app.logger.error("405 MethodNotAllowed Exception: %s" % e)
    trace = traceback.format_exc()
    app.logger.error(trace)
    flash(_("Session expired. Please refresh and try again."), "error")
    return redirect(request.url)


########## on every request ###############
@app.before_request
def selfcheck():
    """check status before every request"""
    if app.specter.rpc is not None:
        type(app.specter.rpc).counter = 0
        if not app.specter.chain:
            app.specter.check()
    if app.config.get("LOGIN_DISABLED"):
        app.login("admin")


@app.before_request
def slow_request_detection_start():
    g.start = time()


@app.before_request
def execute_service_manager_hook():
    """inform extensions about the request"""
    app.specter.service_manager.execute_ext_callbacks(flask_before_request, request)


@app.after_request
def slow_request_detection_stop(response):
    try:
        diff = time() - g.start
    except Exception as e:
        app.logger.error(e)
        return response
    if (
        (response.response)
        and (200 <= response.status_code < 300)
        and (response.content_type.startswith("text/html"))
    ):
        threshold = app.config["REQUEST_TIME_WARNING_THRESHOLD"]
        if diff > threshold:
            flash(
                _(
                    "The request before this one took {} seconds which is longer than the threshold ({}). Checkout the perfomance-improvement-hints in the documentation".format(
                        int(diff), threshold
                    )
                ),
                "warning",
            )
    return response


########## template injections #############
@app.context_processor
def inject_common_stuff():
    """Can be used in all jinja2 templates"""
    return dict(
        debug=app.config["DEBUG"],
        specter_url_prefix=app.config["APP_URL_PREFIX"]
        + app.config["SPECTER_URL_PREFIX"],
        ext_url_prefix=app.config["APP_URL_PREFIX"] + app.config["EXT_URL_PREFIX"],
    )


################ Specter global routes ####################
@app.route("/")
def index():
    if app.config["SPECTER_URL_PREFIX"] == "":
        return redirect(url_for("welcome_endpoint.index"))
    else:
        """This is the root-entry URL which redirects to ROOT_URL_REDIRECT"""
        return redirect(app.config["ROOT_URL_REDIRECT"])


if app.config["SPECTER_URL_PREFIX"] != "":
    # Not necessary if the prefix has been removed
    @app.route(f"{app.config['SPECTER_URL_PREFIX']}/")
    def index_prefix():
        return redirect(url_for("welcome_endpoint.index"))


@app.route("/healthz/liveness")
def liveness():
    return {"message": "i am alive"}


@app.route("/healthz/readyness")
def readyness():
    try:
        # Probably improvable:
        app.specter.check()
    except Exception as e:
        return {"message": "i am not ready"}, 500
    return {"message": "i am ready"}
