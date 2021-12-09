import base64
import datetime
import hashlib
import json
import logging
import pytz
import requests
import secrets

from flask import Flask, Response, redirect, render_template, request, url_for, flash
from flask import current_app as app
from flask_login import current_user, login_required
from functools import wraps

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


# TODO: Change this to refreshtoken_required
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
    print("index")
    if SwanService.get_current_user_api_data().get("access_token") is not None:
        return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))
    return render_template(
        "swan/index.jinja",
    )


@swan_endpoint.route("/oauth2/start")
@login_required
@user_secret_decrypted_required
def oauth2_start():
    """
    Set up the Swan API integration by requesting our initial access_token and
    refresh_token.
    """
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
        "scope=offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
    ]
    flow_url = flow_url + "&".join(query_params)

    print(f"current_user: {current_user}")
    return render_template("swan/oauth2_start.jinja", flow_url=flow_url)


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
    code = request.args.get("code")
    logger.debug(f"request.args: {request.args}")
    logger.debug(f"looks good, we got a code: {code}")
    logger.debug(f"try to get an access-token: ")
    logger.debug(f"client_secret : {client_secret}")
    logger.debug(f"code_verifier: {code_verifier}")

    try:
        get_access_token(code=code, code_verifier=code_verifier)
        return redirect(url_for(".oauth2_success"))
    except Exception as e:
        return render_template(
            "error.html",
            response=None,
            error=str(e),
            error_description=None,
            cookies=request.cookies,
        )


def get_access_token(code: str = None, code_verifier: str = None):
    """
    If code and code_verifier are specified, this is our initial request for an 
    access_token and, more importantly, the refresh_token.

    If code is None, use the refresh_token to get a new short-lived access_token.
    """
    if code:
        payload = {
            "client_id": "specter-dev",
            "client_secret": client_secret,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "code": code,
        }
    else:
        api_data = SwanService.get_current_user_api_data()
        if "refresh_token" not in api_data:
            # TODO: Better Exception handling
            raise Exception("Required service integration data not found")
    
        print("api_data: " + json.dumps(api_data, indent=4))
        
        data={
            "grant_type": "refresh_token",
            # "redirect_uri":   # Necessary?
            "refresh_token": api_data["refresh_token"],
            "scope": "offline_access",      # Possibly get an updated refresh_token back
        },

    response = requests.post(
        "https://dev-api.swanbitcoin.com/oidc/token",
        data=payload,
    )
    resp = json.loads(response.text)
    """
        {
            "access_token": "eyJhbGciOiJ[...]K1Sun9bA",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "offline_access",
            "refresh_token": "MIOf-U1zQbyfa3MUfJHhvnUqIut9ClH0xjlDXGJAyqo",
            "id_token": "eyJraWQiO[...]hMEJQX6WRQ"
        }
    """
    logger.debug(json.dumps(resp, indent=4))
    if resp.get("access_token"):
        print(f"current_user: {current_user}")
        new_api_data = {
            "access_token": resp["access_token"],
            "expires": (datetime.datetime.now(tz=pytz.utc) + datetime.timedelta(seconds=resp["expires_in"])).timestamp(),
        }
        if "refresh_token" in resp:
            new_api_data["refresh_token"] = resp["refresh_token"]

        SwanService.update_current_user_api_data(new_api_data)

        print(json.dumps(SwanService.get_current_user_api_data(), indent=4))
        return
    else:
        print(response)
        raise Exception(response.text)


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


@swan_endpoint.route("/withdrawals")
@login_required
@accesstoken_required
def withdrawals():
    if not SwanService.is_access_token_valid:
        get_access_token()
    
    reserved_addrs = []
    for wallet_alias, wallet in app.specter.wallet_manager.wallets.items():
        reserved_addrs.extend(wallet.get_reserved_addresses(service_id=SwanService.id, unused_only=True))

    return render_template(
        "swan/withdrawals.jinja",
        wallets=get_wallets(),
        reserved_addrs=reserved_addrs,
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
    threshold = request.form["threshold"]
    destination_wallet = request.form["destination_wallet"]
    wallet = current_user.wallet_manager.get_by_alias(destination_wallet)

    # Remove any unused reserved addresses for this service in all of this User's wallets
    for wallet_alias, cur_wallet in app.specter.wallet_manager.wallets.items():
        SwanService.unreserve_addresses(wallet=cur_wallet)

    # Now claim new ones
    SwanService.reserve_addresses(wallet=wallet)

    return redirect(url_for(f"{SwanService.get_blueprint_name()}.withdrawals"))


@swan_endpoint.route("/oauth2/delete-token", methods=["POST"])
@login_required
@accesstoken_required
def oauth2_delete_token():
    # TODO: Separate deleting the token from removing service integration altogether?
    for wallet_name, wallet in current_user.wallet_manager.wallets.items():
        SwanService.unreserve_addresses(wallet=wallet)
    
    SwanService.set_current_user_api_data({})

    url = url_for(f"{SwanService.get_blueprint_name()}.index")
    return redirect(url_for(f"{SwanService.get_blueprint_name()}.index"))


