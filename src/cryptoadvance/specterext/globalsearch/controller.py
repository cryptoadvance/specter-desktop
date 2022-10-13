import logging
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import login_required, current_user

from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.services.controller import user_secret_decrypted_required
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet
from .service import GlobalsearchService
from cryptoadvance.specter.util.common import robust_json_dumps

logger = logging.getLogger(__name__)

globalsearch_endpoint = GlobalsearchService.blueprint


def ext() -> GlobalsearchService:
    """convenience for getting the extension-object"""
    return app.specter.ext["globalsearch"]


def specter() -> Specter:
    """convenience for getting the specter-object"""
    return app.specter


@globalsearch_endpoint.route("/")
@login_required
def index():
    return render_template(
        "globalsearch/index.jinja",
    )


@globalsearch_endpoint.route("/transactions")
@login_required
def transactions():
    # The wallet currently configured for ongoing autowithdrawals
    wallet: Wallet = GlobalsearchService.get_associated_wallet()

    return render_template(
        "globalsearch/transactions.jinja",
        wallet=wallet,
        services=app.specter.service_manager.services,
    )


@globalsearch_endpoint.route("/settings", methods=["GET"])
@login_required
@user_secret_decrypted_required
def settings_get():
    associated_wallet: Wallet = GlobalsearchService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "globalsearch/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
    )


@globalsearch_endpoint.route("/settings", methods=["POST"])
@login_required
@user_secret_decrypted_required
def settings_post():
    show_menu = request.form["show_menu"]
    user = app.specter.user_manager.get_user()
    if show_menu == "yes":
        user.add_service(GlobalsearchService.id)
    else:
        user.remove_service(GlobalsearchService.id)
    used_wallet_alias = request.form.get("used_wallet")
    if used_wallet_alias != None:
        wallet = current_user.wallet_manager.get_by_alias(used_wallet_alias)
        GlobalsearchService.set_associated_wallet(wallet)
    return redirect(
        url_for(f"{ GlobalsearchService.get_blueprint_name()}.settings_get")
    )


@globalsearch_endpoint.route("/global_search", methods=["POST"])
@login_required
def global_search():
    search_term = request.form.get("global-search-input")
    user = app.specter.user_manager.get_user(current_user)
    return robust_json_dumps(
        app.specter.ext["globalsearch"].global_search_tree.do_global_search(
            search_term.strip(),
            current_user,
            app.specter.hide_sensitive_info,
            app.specter.wallet_manager.wallets,
            app.specter.device_manager.devices,
            locale=app.get_language_code(),
        )
    )
