import copy, random
import os
import logging
from cryptoadvance.specter import services
from flask import (
    Flask,
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
    make_response,
)
from flask_login import login_required, current_user
from flask import current_app as app
from ..service_settings_manager import ServiceSettingsManager
from .vaultoro_api import VaultoroApi
import requests

logger = logging.getLogger(__name__)

# Setup endpoint blueprint
vaultoro_endpoint = Blueprint(
    "vaultoro_endpoint",
    "cryptoadvance.specter.services.controller",
    template_folder="templates",
    static_folder="static",
)

vaultoro_url = os.getenv("VAULTORO_API", "https://api.vaultoro.com")


@vaultoro_endpoint.route("/")
# @login_required
def index():
    settings_manager = ServiceSettingsManager(app.specter, "vaultoro")
    if not settings_manager.get_key(
        app.specter.user_manager.get_user(current_user).id, "token"
    ):
        return redirect("settings")

    return redirect("balances")


@vaultoro_endpoint.route("/balances/", methods=["GET", "POST"])
# @login_required
def balances():
    """ shows the balance and history and such stuff """
    api = get_api()
    try:
        return render_template(
            "vaultoro/balances.jinja",
            specter=app.specter,
            balances=api.get_balances(),
            history=api.get_trades(),
            vaultoro_url=vaultoro_url,
        )
    except:
        flash("Please provide a Vaultoro API token to access this page", "error")
        return redirect(url_for("vaultoro_endpoint.settings"))


@vaultoro_endpoint.route("/trade/", methods=["GET", "POST"])
# @login_required
def trade():
    try:
        return render_template(
            "vaultoro/trade.jinja",
            specter=app.specter,
            balances=get_api().get_balances(),
            vaultoro_url=vaultoro_url,
        )
    except:
        flash("Please provide a Vaultoro API token to access this page", "error")
        return redirect(url_for("vaultoro_endpoint.settings"))


@vaultoro_endpoint.route("/deposit/", methods=["GET", "POST"])
# @login_required
def deposit():
    try:
        all_addresses = get_api().get_wallet_addresses()
        deposit_address = [
            address
            for address in all_addresses
            if address.get("active", False) and "address" in address
        ]
        deposit_address = deposit_address[0]
        return render_template(
            "vaultoro/deposit.jinja",
            deposit_address=deposit_address,
            all_addresses=all_addresses,
            specter=app.specter,
        )
    except:
        flash("Please provide a Vaultoro API token to access this page", "error")
        return redirect(url_for("vaultoro_endpoint.settings"))


@vaultoro_endpoint.route("/withdraw/", methods=["GET", "POST"])
# @login_required
def withdraw():
    flash("Not yet implemented", "error")
    return redirect(url_for("vaultoro_endpoint.settings"))


@vaultoro_endpoint.route("/settings/", methods=["GET", "POST"])
# @login_required
def settings():

    settings_manager = ServiceSettingsManager(app.specter, "vaultoro")

    if request.method == "POST":
        action = request.form["action"]
        token = request.form["vaultoro_token"]
        if action == "save":
            settings_manager.set_key(
                app.specter.user_manager.get_user(current_user).id, "token", token
            )
            return render_template(
                "vaultoro/settings.jinja", specter=app.specter, vaultoro_token=token
            )
        elif action == "test_token":
            v_api = VaultoroApi(token)
            try:
                v_api.get_me()
                flash("Token-Test successfull! Save it!")
            except Exception as e:
                flash(f"token-test failed: {e}", "error")
            return render_template(
                "vaultoro/settings.jinja", specter=app.specter, vaultoro_token=token
            )
        else:
            raise Exception(f"Unknown action {action}")
    elif request.method == "GET":
        token = settings_manager.get_key(
            app.specter.user_manager.get_user(current_user).id, "token"
        )
        return render_template(
            "vaultoro/settings.jinja", specter=app.specter, vaultoro_token=token
        )


def get_api():
    settings_manager = ServiceSettingsManager(app.specter, "vaultoro")
    token = settings_manager.get_key(
        app.specter.user_manager.get_user(current_user).id, "token"
    )
    return VaultoroApi(token)


@vaultoro_endpoint.route("/api/buy/quote", methods=["POST"])
def api_buy_quote():
    """ implements https://api-docs.vaultoro.com/otc """
    pair = request.json["pair"]
    total = request.json["total"]
    quantity = request.json["quantity"]
    mytype = request.json["type"]
    return get_api().get_quote(pair, mytype, total, quantity)


@vaultoro_endpoint.route("/api/buy/order", methods=["POST"])
def api_buy_order():
    """ implements https://api-docs.vaultoro.com/otc """
    try:
        return get_api().create_order(
            request.json["pair"],
            request.json["type"],
            request.json["total"],
            request.json["quantity"],
        )
    except Exception as e:
        print({"errors": str(e)})
        return {"errors": str(e)}


@vaultoro_endpoint.route("/api/history/trades", methods=["GET"])
def api_history_trades():
    """ implements https://api-docs.vaultoro.com/history/untitled """
    return get_api().get_trades()


@vaultoro_endpoint.route("/api/coins/withdraw", methods=["POST"])
def api_coins_withdraw():
    """ implements https://api-docs.vaultoro.com/assets """
    address = request.json["address"]
    quantity = request.json["quantity"]
    otp = request.json["otp"]
    return get_api().coins_withdraw(otp, address, quantity)


@vaultoro_endpoint.route("/api/coins/withdraw/fees", methods=["POST"])
def api_coins_withdraw_fees():
    """ implements https://api-docs.vaultoro.com/assets """
    quantity = request.json["quantity"]
    return get_api().coins_withdraw_fees(quantity)


# Stuff below here needs to be implemented on specter-cloud


def trace_call():
    logger.info("tracecall triggered")


@vaultoro_endpoint.route("/.vaultoro/v1/<path:mypath>", methods=["GET", "POST"])
def vaultoro_proxy(mypath):
    logger.debug(f"VTProxy {mypath}")
    tracefilter = ["v1/private/balances"]
    for path in tracefilter:
        if mypath.endswith(path):
            trace_call()
    url = app.config["VAULTORO_API"] + "/" + mypath
    logger.debug(f"VTProxy {url}")
    # Not sure what about request.data ... irgnore it for now
    session = requests.session()
    newheaders = {
        "Vtoken": request.headers["VTOKEN"],
        "Content-type": "application/json",
    }
    resp = session.request(
        request.method,
        url,
        params=request.args,
        stream=False,
        headers=newheaders,
        allow_redirects=True,
        # cookies=request.cookies,
        data=request.data,
    )

    if resp.status_code != 200:
        logger.error(f"VTProxy: status-code {resp.status_code} for request {url}")
    # A Flask/Werkzeug Response is very different from a requests-response
    # So we need to create one manually.
    f_resp = make_response(resp.content, resp.status_code)  # resp.headers.items())
    # Would love to have a generic cookie-handling here but i can't figure out
    # how to reasonably iterate over a RequestsCookieJar respecting paths, domains etc.
    # for cookie in resp.cookies:
    #    print("cookiename: {}expires: {}".format(cookie.name, cookie.expires))
    #    f_resp.set_cookie(cookie.name, value=resp.cookies.get(cookie.name),
    #        path=cookie.path, domain=cookie.domain  )
    return f_resp
