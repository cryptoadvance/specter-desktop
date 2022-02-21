import logging
from flask import Flask, Response, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from .service import DevhelpService
from cryptoadvance.specter.wallet import Wallet


logger = logging.getLogger(__name__)

devhelp_endpoint = DevhelpService.blueprint


@devhelp_endpoint.route("/")
@login_required
@user_secret_decrypted_required
def index():
    return render_template(
        "devhelp/index.jinja",
    )


@devhelp_endpoint.route("/html/<html_component>")
@login_required
@user_secret_decrypted_required
def html_component(html_component):
    associated_wallet: Wallet = DevhelpService.get_associated_wallet()
    return render_template(
        f"devhelp/html/{html_component}",
        wallet=associated_wallet,
        services=app.specter.service_manager.services,
        address=associated_wallet.get_address(3),
    )


@devhelp_endpoint.route("/settings", methods=["GET"])
@login_required
@user_secret_decrypted_required
def settings_get():
    associated_wallet: Wallet = DevhelpService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "devhelp/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
    )


@devhelp_endpoint.route("/settings", methods=["POST"])
@login_required
@user_secret_decrypted_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(DevhelpService.id)
    else:
        user.remove_service(DevhelpService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        DevhelpService.set_associated_wallet(wallet)
    return redirect(url_for(f"{DevhelpService.get_blueprint_name()}.settings_get"))
