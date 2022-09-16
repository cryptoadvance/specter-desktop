import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import NotificationsService


logger = logging.getLogger(__name__)

notifications_endpoint = NotificationsService.blueprint


def ext() -> NotificationsService:
    """convenience for getting the extension-object"""
    return app.specter.ext["notifications"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


@notifications_endpoint.route("/")
@login_required
def index():
    return render_template(
        "notifications/index.jinja",
    )


@notifications_endpoint.route("/transactions")
@login_required
def transactions():
    # The wallet currently configured for ongoing autowithdrawals
    wallet: Wallet = NotificationsService.get_associated_wallet()

    return render_template(
        "notifications/transactions.jinja",
        wallet=wallet,
        services=app.specter.service_manager.services,
    )


@notifications_endpoint.route("/settings", methods=["GET"])
@login_required
@user_secret_decrypted_required
def settings_get():
    associated_wallet: Wallet = NotificationsService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "notifications/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
    )


@notifications_endpoint.route("/settings", methods=["POST"])
@login_required
@user_secret_decrypted_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(NotificationsService.id)
    else:
        user.remove_service(NotificationsService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        NotificationsService.set_associated_wallet(wallet)
    return redirect(
        url_for(f"{ NotificationsService.get_blueprint_name()}.settings_get")
    )


@app.route("/websocket", websocket=True)
def websocket():
    logger.debug("websocket route called. This will start a new websocket connection.")
    # this function will run forever. That is ok, because a stream is expected, similar to https://maxhalford.github.io/blog/flask-sse-no-deps/
    #  flask.Response(stream(), mimetype='text/event-stream')
    if app.specter.ext["notifications"].notification_manager.websockets_server:
        app.specter.ext["notifications"].notification_manager.websockets_server.serve(
            request.environ
        )
    else:
        logger.warning(
            "/websocket route accessed, but no websockets_server is initialized."
        )
    # returning a string solved some error message when the function ends: https://stackoverflow.com/questions/25034123/flask-value-error-view-function-did-not-return-a-response
    return ""
