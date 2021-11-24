import base64
import hashlib
import json
import logging
import secrets
from functools import wraps

import requests
from flask import Flask, Response, redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import current_user, login_required

from cryptoadvance.specter.services.service_apikey_storage import (
    ServiceApiKeyStorageError,
)
from .manifest import SwanService
from .swan_client import get_wallets, get_automatic_withdrawal
from ..controller import user_secret_decrypted_required
from ..service_settings_manager import ServiceSettingsManager

client_id = "specter-dev"
client_secret = "BcetcVcmueWf5P3UPJnHhCBMQ49p38fhzYwM7t3DJGzsXSjm89dDR5URE46SY69j"
code_verifier = "64fRjTuy6SKqdC1wSoInUNxX65dQUhVVKTqZXuQ7dqw"
tokens = {}


logger = logging.getLogger(__name__)

swan_endpoint = SwanService.blueprint


def calc_code_challenge(code_verifier=None):
    if code_verifier is None:
        code_verifier = secrets.token_urlsafe(43)
    # see specification: https://datatracker.ietf.org/doc/html/rfc7636#section-4.2
    # and example impl: https://github.com/RomeoDespres/pkce/blob/master/pkce/__init__.py#L94-L96
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    code_challenge = encoded.decode("ascii")[:-1]
    return code_verifier, code_challenge


def accesstoken_required(func):
    """Access token needed for this function"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if SwanService.get_current_user_api_data().get("access_token") is None:
                logger.debug(f"No access token, redirecting to {SwanService.id}.index")
                return redirect(url_for(f"{SwanService.get_blueprint_name()}.oauth2_start"))
        except ServiceApiKeyStorageError as e:
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
    if SwanService.get_current_user_api_data().get("access_token") is not None:
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    return render_template(
        "swan/index.jinja",
    )


@swan_endpoint.route("/oauth2/start")
@login_required
@user_secret_decrypted_required
def oauth2_start():
    # Do we have a token already?
    if SwanService.get_current_user_api_data().get("access_token"):
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.settings"))

    # Let's start the PKCE-flow
    global code_verifier
    code_verifier, code_challenge = calc_code_challenge()
    print(f"code_challenge: {code_challenge}")
    flow_url = "https://dev-api.swanbitcoin.com/oidc/auth?"
    query_params = [
        "client_id=specter-dev",
        "redirect_uri=http://localhost:25441/svc/swan/oauth2/callback",
        "response_type=code",
        "response_mode=query",
        f"code_challenge={code_challenge}",
        "code_challenge_method=S256",
        "state=kjkmdskdmsmmsmdslmdlsm",
        "scope=openid v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
    ]
    flow_url = flow_url + "&".join(query_params)

    print(f"current_user: {current_user}")
    return render_template("swan/oauth2_start.jinja", flow_url=flow_url)


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
    code = request.args.get("code")
    logger.debug(f"looks good, we got a code: {code}")
    logger.debug(f"try to get an access-token: ")
    logger.debug(f"client_secret : {client_secret}")
    logger.debug(f"code_verifier: {code_verifier}")
    response = requests.post(
        "https://dev-api.swanbitcoin.com/oidc/token",
        data={
            "client_id": "specter-dev",
            "client_secret": client_secret,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "code": code,
        },
    )
    resp = json.loads(response.text)
    if resp.get("access_token"):
        print(f"current_user: {current_user}")
        SwanService.set_current_user_api_data({"access_token": resp["access_token"]})
        return redirect(url_for(".oauth2_success"))
    else:
        return render_template(
            "error.html",
            response=response.text,
            error=request.args.get("error"),
            error_description=request.args.get("error_description"),
            cookies=request.cookies,
        )


@swan_endpoint.route("/oauth2/success")
@login_required
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


@swan_endpoint.route("/withdrawals")
@login_required
@accesstoken_required
def withdrawals():
    return render_template(
        "swan/withdrawals.jinja",
        wallets=get_automatic_withdrawal(),
    )


@swan_endpoint.route("/settings")
@login_required
@accesstoken_required
def settings():
    return render_template(
        "swan/settings.jinja",
        tokens=tokens,
        wallet_manager=current_user.wallet_manager,
        cookies=request.cookies,
    )


@swan_endpoint.route("/settings/autowithdrawal", methods=["POST"])
@login_required
@accesstoken_required
def update_autowithdrawal():
    print(request.form)
    return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))


@swan_endpoint.route("/oauth2/delete-token", methods=["POST"])
@login_required
@accesstoken_required
def oauth2_delete_token():
    SwanService.set_current_user_api_data({})
    return redirect(url_for(f"{SwanService.get_blueprint_name()}.oauth2_start"))


