import logging
import random
from binascii import unhexlify

from flask import Blueprint
from flask import current_app as app
from flask import flash, make_response, redirect, render_template, request, url_for
from flask_babel import lazy_gettext as _
from flask_login import login_required

from ..helpers import notify_upgrade
from ..managers.wallet_manager import purposes

logger = logging.getLogger(__name__)

rand = random.randint(0, 1e32)  # to force style refresh

# Setup endpoint blueprint
welcome_endpoint = Blueprint("welcome_endpoint", __name__)


@welcome_endpoint.route("/")
@login_required
def index():
    if request.args.get("mode"):
        if request.args.get("mode") == "remote":
            pass
    notify_upgrade(app, flash)
    if len(app.specter.wallet_manager.wallets) > 0:
        if len(app.specter.wallet_manager.wallets) > 1:
            return redirect(url_for("wallets_endpoint.wallets_overview"))
        return redirect(
            url_for(
                "wallets_endpoint.wallet",
                wallet_alias=app.specter.wallet_manager.wallets[
                    app.specter.wallet_manager.wallets_names[0]
                ].alias,
            )
        )

    return redirect(url_for("welcome_endpoint.about"))


@welcome_endpoint.route("/about", methods=["GET", "POST"])
@login_required
def about():
    notify_upgrade(app, flash)
    if request.method == "POST":
        action = request.form["action"]
        if action == "cancelsetup":
            app.specter.setup_status["stage"] = "start"
            app.specter.reset_setup("bitcoind")
            app.specter.reset_setup("torbrowser")

    return render_template(
        "base.jinja",
        specter=app.specter,
        rand=rand,
        supported_languages=app.supported_languages,
    )


@welcome_endpoint.route("/bitcoin.pdf")
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
            error=_(
                "You need a mainnet node to retrieve the whitepaper. Check your node configurations."
            ),
        )
