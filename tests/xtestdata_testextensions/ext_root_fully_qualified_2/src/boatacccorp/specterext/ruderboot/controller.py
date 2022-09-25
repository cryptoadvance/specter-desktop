import logging
from flask import redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import RuderbootService


logger = logging.getLogger(__name__)

ruderboot_endpoint = RuderbootService.blueprint


@ruderboot_endpoint.route("/")
@login_required
@user_secret_decrypted_required
def index():
    return render_template(
        "ruderboot/index.jinja",
    )


@ruderboot_endpoint.route("/settings", methods=["GET"])
@login_required
@user_secret_decrypted_required
def settings_get():
    associated_wallet: Wallet = RuderbootService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "ruderboot/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
    )


@ruderboot_endpoint.route("/settings", methods=["POST"])
@login_required
@user_secret_decrypted_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(RuderbootService.id)
    else:
        user.remove_service(RuderbootService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
    return redirect(url_for(f"{RuderbootService.get_blueprint_name()}.settings_get"))
