import base64
import datetime
import hashlib
import json
import logging
import pytz
import requests
import secrets

from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required
from functools import wraps
from cryptoadvance.specter.wallet import Wallet

from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorageError,
)
from . import api as swan_api
from .service import SwanService
from ..controller import user_secret_decrypted_required


logger = logging.getLogger(__name__)

swan_endpoint = SwanService.blueprint


# TODO: Change this to refreshtoken_required
# TODO: Generalize this to work for all Services?
def accesstoken_required(func):
    """Access token needed for this function"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if SwanService.get_current_user_service_data().get("access_token") is None:
                logger.debug(f"No access token, redirecting to {SwanService.id}.index")
                return redirect(url_for(f"{SwanService.get_blueprint_name()}.oauth2_start"))
        except ServiceEncryptedStorageError as e:
            logger.debug(repr(e))
            flash(
                "Re-login required to access your protected services data"
            )
            return redirect(url_for(f"auth_endpoint.logout"))
        return func(*args, **kwargs)

    return wrapper


@swan_endpoint.route("/")
@login_required
@user_secret_decrypted_required
def index():
    if SwanService.get_current_user_service_data().get("access_token") is not None:
        # User has already completed Swan integration; skip ahead
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    return render_template(
        "swan/index.jinja",
    )


@swan_endpoint.route("/withdrawals")
@login_required
@accesstoken_required
def withdrawals():
    # Gather Specter's internal info 
    wallet: Wallet = SwanService.get_associated_wallet()
    print(wallet)
    reserved_addrs = []
    if wallet:
        reserved_addrs = wallet.get_associated_addresses(service_id=SwanService.id, unused_only=True)
        print(reserved_addrs)
    
    return render_template(
        "swan/withdrawals.jinja",
        wallets=[wallet],
        reserved_addrs=reserved_addrs,
    )


@swan_endpoint.route("/settings")
@login_required
@accesstoken_required
def settings():
    # TODO: Remove this check after refresh_token support is added
    if not SwanService.is_access_token_valid():
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.oauth2_start", is_relink=1))

    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    print(wallet_names)
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]
    print(wallets)
    wallet_data = [{"alias": w.alias, "name": w.name, "address_type": w.address_type} for w in wallets]
    return render_template(
        "swan/settings.jinja",
        wallet_data=wallet_data,
        cookies=request.cookies,
    )


@swan_endpoint.route("/settings/autowithdrawal", methods=["POST"])
@login_required
@accesstoken_required
def update_autowithdrawal():
    print(request.form)
    threshold = request.form["threshold"]
    destination_wallet = request.form["destination_wallet"]
    wallet = current_user.wallet_manager.get_by_alias(destination_wallet)

    # Remove any unused reserved addresses for this service in all of this User's wallets
    for wallet_alias, cur_wallet in app.specter.wallet_manager.wallets.items():
        SwanService.unreserve_addresses(wallet=cur_wallet)

    # Now claim new ones
    addr_list = SwanService.reserve_addresses(wallet=wallet, num_addresses=10)

    try:
        # Send the new list to Swan
        swan_api.update_autowithdrawal_addresses(wallet=wallet, addresses=addr_list)

        # TODO: Send the autowithdrawal settings with the Swan walletId


        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    except swan_api.SwanServiceApiException as e:
        logger.exception(e)
        flash(
            _("Error communicating with Swan API")
        )
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.settings"))




""" ***************************************************************************
                                OAuth2 endpoints
*************************************************************************** """
@swan_endpoint.route("/oauth2/start")
@swan_endpoint.route("/oauth2/start/<is_relink>")
@login_required
@user_secret_decrypted_required
def oauth2_start(is_relink=0):
    """
    Set up the Swan API integration by requesting our initial access_token and
    refresh_token.
    """
    from . import api as swan_api

    # Do we have a token already?
    if SwanService.is_access_token_valid():
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.settings"))

    # Let's start the PKCE-flow
    flow_url = swan_api.get_oauth2_start_url()

    print(f"current_user: {current_user}")
    print(f"is_relink: {is_relink}")
    return render_template(
        "swan/oauth2_start.jinja",
        flow_url=flow_url,
        is_relink=int(is_relink) == 1,
    )


@swan_endpoint.route("/oauth2/callback")
def oauth2_auth():
    if request.args.get("error"):
        logger.error(
            f"OAuth2 flow error: {request.args.get('error')}, {request.args.get('error_description')}"
        )
        return render_template(
            "500.jinja",
            error=request.args.get("error"),
            traceback=request.args.get(
                "error_description"
            ),  # Slightly misusing the traceback field
        )
    
    try:
        from . import api as swan_api
        swan_api.handle_oauth2_auth_callback(request)

        user = app.specter.user_manager.get_user()

        if SwanService.id not in user.services:
            user.services.append(SwanService.id)

        return redirect(url_for(".oauth2_success"))
    except Exception as e:
        logger.exception(e)
        return render_template(
            "error.html",
            response=None,
            error=str(e),
            error_description=None,
            cookies=request.cookies,
        )


@swan_endpoint.route("/oauth2/success")
def oauth2_success():
    """
        The redirect from the oauth2 callback has to land on an endpoint that does not
        have the @login_required filter set. Once we're back we can proceed to login-
        protected pages as usual.
    """
    print(f"current_user: {current_user}")
    return render_template(
        "swan/oauth2_success.jinja",
    )


@swan_endpoint.route("/oauth2/delete-token", methods=["POST"])
@login_required
@user_secret_decrypted_required
def oauth2_delete_token():
    # TODO: Separate deleting the token from removing service integration altogether?
    for wallet_name, wallet in current_user.wallet_manager.wallets.items():
        SwanService.unreserve_addresses(wallet=wallet)
    
    SwanService.set_current_user_service_data({})

    current_user.services.remove(SwanService.id)

    url = url_for(f"{SwanService.get_blueprint_name()}.index")
    return redirect(url_for(f"{SwanService.get_blueprint_name()}.index"))
