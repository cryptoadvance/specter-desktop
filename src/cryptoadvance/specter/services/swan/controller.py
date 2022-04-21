import json
import logging

from decimal import Decimal
from urllib.parse import urlparse
from flask import redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask.json import jsonify
from flask_babel import lazy_gettext as _
from flask_login import current_user, login_required
from functools import wraps
from cryptoadvance.specter.user import User
from cryptoadvance.specter.wallet import Wallet

from cryptoadvance.specter.services.service_encrypted_storage import (
    ServiceEncryptedStorageError,
)
from . import client as swan_client
from .client import SwanApiException
from .service import SwanService
from ..controller import user_secret_decrypted_required


logger = logging.getLogger(__name__)

swan_endpoint = SwanService.blueprint


def refreshtoken_required(func):
    """Refresh token needed for any endpoint that interacts with Swan API"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if not SwanService.has_refresh_token():
                logger.debug(f"No refresh token, redirecting to relink Swan account")
                return redirect(
                    url_for(f"{SwanService.get_blueprint_name()}.oauth2_start")
                )
        except ServiceEncryptedStorageError as e:
            logger.debug(repr(e))
            flash("Re-login required to access your protected services data")

            # Use Flask's built-in re-login w/automatic redirect back to calling page
            return app.login_manager.unauthorized()
        return func(*args, **kwargs)

    return wrapper


@swan_endpoint.route("/")
@login_required
@user_secret_decrypted_required
def index():
    if SwanService.has_refresh_token():
        # User has already completed Swan integration; skip ahead
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    specter_used_hostname = urlparse(request.url).netloc
    return render_template(
        "swan/index.jinja",
        swan_frontend_url=app.config["SWAN_FRONTEND_URL"],
        specter_used_hostname=specter_used_hostname,
        # The oauth2-flow uses a whitelist. Is our hostname whitelisted?!
        specter_hostname_supported=specter_used_hostname
        in app.config["SWAN_ALLOWED_SPECTER_HOSTNAMES"],
        allowed_specter_hostnames=app.config["SWAN_ALLOWED_SPECTER_HOSTNAMES"],
    )


@swan_endpoint.route("/withdrawals")
@login_required
@refreshtoken_required
def withdrawals():
    # The wallet currently configured for ongoing autowithdrawals
    wallet: Wallet = SwanService.get_associated_wallet()

    return render_template(
        "swan/withdrawals.jinja",
        # txlist=swan_txs,
        wallet=wallet,
        services=app.specter.service_manager.services,
        swan_id=SwanService.id,
        autowithdrawal_threshold=SwanService.get_current_user_service_data().get(
            SwanService.AUTOWITHDRAWAL_THRESHOLD
        ),
    )


@swan_endpoint.route("/settings", methods=["GET"])
@login_required
@refreshtoken_required
def settings():
    associated_wallet: Wallet = SwanService.get_associated_wallet()

    # Get the user's Wallet objs, sorted by Wallet.name
    wallet_names = sorted(current_user.wallet_manager.wallets.keys())
    wallets = [current_user.wallet_manager.wallets[name] for name in wallet_names]

    return render_template(
        "swan/settings.jinja",
        associated_wallet=associated_wallet,
        wallets=wallets,
        cookies=request.cookies,
        num_reserved_addrs=SwanService.MIN_PENDING_AUTOWITHDRAWAL_ADDRS,
    )


@swan_endpoint.route("/settings/autowithdrawal", methods=["POST"])
@login_required
@refreshtoken_required
def update_autowithdrawal():
    threshold = request.form["threshold"]
    destination_wallet_alias = request.form["destination_wallet"]
    wallet = current_user.wallet_manager.get_by_alias(destination_wallet_alias)

    try:
        SwanService.set_autowithdrawal_settings(wallet=wallet, btc_threshold=threshold)
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    except SwanApiException as e:
        logger.exception(e)
        flash(_("Error communicating with Swan API"))
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.settings"))


""" ***************************************************************************
                                OAuth2 endpoints
*************************************************************************** """


@swan_endpoint.route("/oauth2/start")
@login_required
@user_secret_decrypted_required
def oauth2_start():
    """
    Set up the Swan API integration by requesting our initial access_token and
    refresh_token.
    """
    # Do we have a token already?
    if SwanService.has_refresh_token():
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.settings"))

    # Let's start the PKCE-flow
    specter_used_hostname = urlparse(request.url).netloc
    # The oauth2-flow uses a whitelist. Is our hostname whitelisted?!
    if specter_used_hostname not in app.config["SWAN_ALLOWED_SPECTER_HOSTNAMES"]:
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.index"))
    flow_url = SwanService.client().get_oauth2_start_url(specter_used_hostname)

    return render_template(
        "swan/oauth2_start.jinja",
        flow_url=flow_url,
    )


@swan_endpoint.route("/integration_check")
def integration_check():
    """
    Polled by the oauth2_start page via AJAX. Returns False until we have a Swan refresh token.
    Returns True and can then redirect to settings.
    """
    try:
        if SwanService.has_refresh_token():
            return jsonify(success=True)
    except Exception as e:
        # Expected to fail in various possible ways: not logged in, user_secret
        # not decrypted, Swan integration not complete.
        pass
    return jsonify(success=False)


"""
    Note: the callback from Swan will be treated by Flask as an AnonymousUserMixin request
    but we need the user logged in and their user_secret decrypted. So we must require
    @login_required here which will interrupt the return flow with the login prompt.
"""


@swan_endpoint.route("/oauth2/callback")
@login_required
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

    user: User = app.specter.user_manager.get_user()
    error = None

    try:
        SwanService.client().handle_oauth2_auth_callback(request)
        SwanService.store_new_api_access_data()
    except swan_client.SwanApiException as e:
        logger.exception(e)
        error = e

    if not error:
        try:
            # Add the Service to the User's profile (will now appear in sidebar)
            user = app.specter.user_manager.get_user()
            user.add_service(SwanService.id)

            # Sync this Specter instance with any previous Swan-Specter integrations
            SwanService.sync_swan_data()

            service_data = SwanService.get_current_user_service_data()
            if service_data.get(SwanService.SPECTER_WALLET_ALIAS):
                # We've re-synced with an existing auto-withdrawal setup. Redirect
                # straight to the auto-withdrawals page.
                return redirect(
                    url_for(f"{SwanService.get_blueprint_name()}.withdrawals")
                )

            return redirect(url_for(".oauth2_success"))
        except Exception as e:
            logger.exception(e)
            error = e

    return render_template(
        "500.jinja",
        response=None,
        error=str(error),
        error_description=_("Could not complete the OAuth callback from Swan"),
        cookies=request.cookies,
    )


@swan_endpoint.route("/oauth2/success")
def oauth2_success():
    """
    The redirect from the oauth2 callback has to land on an endpoint that does not
    have the @login_required filter set. Once we're back we can proceed to login-
    protected pages as usual.
    """
    return render_template(
        "swan/oauth2_success.jinja",
    )


@swan_endpoint.route("/oauth2/delete-token", methods=["POST"])
@login_required
@refreshtoken_required
def oauth2_delete_token():
    SwanService.remove_swan_integration(current_user)

    url = url_for(f"{SwanService.get_blueprint_name()}.index")
    return redirect(url_for(f"{SwanService.get_blueprint_name()}.index"))
