import random, traceback, socket
from datetime import datetime
from binascii import unhexlify
from flask import make_response

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
@app.csrf.exempt
def txout_set_info():
    res = app.specter.rpc.gettxoutsetinfo()
    return res


@app.route("/get_scantxoutset_status")
@login_required
@app.csrf.exempt
def get_scantxoutset_status():
    status = app.specter.rpc.scantxoutset("status", [])
    app.specter.info["utxorescan"] = status.get("progress", None) if status else None
    if app.specter.info["utxorescan"] is None:
        app.specter.utxorescanwallet = None
    return {
        "active": app.specter.info["utxorescan"] is not None,
        "progress": app.specter.info["utxorescan"],
    }


@app.route("/bitcoin.pdf")
@login_required
def get_whitepaper():
    if app.specter.chain == "main":
        if not app.specter.info["pruned"]:
            raw_tx = app.specter.rpc.getrawtransaction(
                "54e48e5f5c656b26c3bca14a8c95aa583d07ebe84dde3b7dd4a78f4e4186e713",
                False,
                "00000000000000ecbbff6bafb7efa2f7df05b227d5c73dca8f2635af32a2e949",
            )
            outputs = raw_tx.split("0100000000000000")
            pdf = ""
            for output in outputs[1:-2]:
                cur = 6
                pdf += output[cur : cur + 130]
                cur += 132
                pdf += output[cur : cur + 130]
                cur += 132
                pdf += output[cur : cur + 130]
            pdf += outputs[-2][6:-4]
        else:
            outputs_prun = app.specter.rpc.multi(
                [
                    (
                        "gettxout",
                        "54e48e5f5c656b26c3bca14a8c95aa583d07ebe84dde3b7dd4a78f4e4186e713",
                        i,
                    )
                    for i in range(0, 946)
                ]
            )
            pdf = ""
            for output in outputs_prun[:-1]:
                cur = 4
                pdf += output["result"]["scriptPubKey"]["hex"][cur : cur + 130]
                cur += 132
                pdf += output["result"]["scriptPubKey"]["hex"][cur : cur + 130]
                cur += 132
                pdf += output["result"]["scriptPubKey"]["hex"][cur : cur + 130]
            pdf += outputs_prun[-1]["result"]["scriptPubKey"]["hex"][4:-4]
        res = make_response(unhexlify(pdf[16:-16]))
        res.headers.set("Content-Disposition", "attachment")
        res.headers.set("Content-Type", "application/pdf")
        return res
    else:
        return render_template(
            "500.jinja",
            error="You need a mainnet node to retrieve the whitepaper. Check your node configurations.",
        )
