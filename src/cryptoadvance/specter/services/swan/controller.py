import base64
import hashlib
import json
import logging
import secrets
from functools import wraps

import requests
from flask import Flask, Response, redirect, render_template, request, url_for, flash
from flask_login import login_required

from cryptoadvance.specter.services.service_apikey_storage import (
    ServiceApiKeyStorageError,
)
from ..service_settings_manager import ServiceSettingsManager
from .manifest import SwanService
from .swan_client import get_wallets

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
            if SwanService._.get_sec_data().get("access_token") is None:
                logger.info(f"No access token, redirecting to {SwanService.id}.index")
                return redirect(url_for(f"{SwanService._.bp_name}.oauth2_start"))
        except ServiceApiKeyStorageError:
            flash(
                "Accessing the Swan Sevice needs relogin to get access to the access-key"
            )
            return redirect(url_for(f"auth_endpoint.logout"))
        return func(*args, **kwargs)

    return wrapper


@swan_endpoint.route("/")
@login_required
@accesstoken_required
def index():
    return redirect(url_for(f"{SwanService._.bp_name}.balances"))


@swan_endpoint.route("/oauth2/start")
@login_required
def oauth2_start():
    # Do we have a token already?
    if SwanService._.get_sec_data().get("access_token"):
        logger.info(f"No access token, redirecting to {SwanService.id}.index")
        return redirect(url_for(f"{SwanService._.bp_name}.balances"))
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
    return render_template("swan/index.jinja", flow_url=flow_url)


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
        SwanService._.set_sec_data({"access_token": resp["access_token"]})
    else:
        return render_template(
            "error.html",
            response=response.text,
            error=request.args.get("error"),
            error_description=request.args.get("error_description"),
            cookies=request.cookies,
        )
    return redirect(url_for(f"{SwanService._.bp_name}.balances"))


@swan_endpoint.route("/oauth2/delete-token")
def oauth2_delete_token():
    SwanService._.set_sec_data({})
    return redirect(url_for(f"{SwanService._.bp_name}.oauth2_start"))


@swan_endpoint.route("/balances")
@login_required
@accesstoken_required
def balances():
    return render_template("swan/balances.jinja", tokens=tokens, wallets=get_wallets())


@swan_endpoint.route("/trade")
@login_required
@accesstoken_required
def trade():
    return render_template(
        "swan/dashboard.html",
        tokens=tokens,
        wallets=wallets,
        me=me,
        cookies=request.cookies,
    )


@swan_endpoint.route("/resources")
@login_required
@accesstoken_required
def resources():
    return render_template("swan/resources.html")


@swan_endpoint.route("/deposit")
@login_required
@accesstoken_required
def deposit():
    return render_template(
        "swan/resources.html",
        tokens=tokens,
        wallets=None,
        me=None,
        cookies=request.cookies,
    )


@swan_endpoint.route("/withdraw")
@login_required
@accesstoken_required
def withdraw():
    return render_template(
        "swan/resources.html",
        tokens=tokens,
        wallets=None,
        me=None,
        cookies=request.cookies,
    )


@swan_endpoint.route("/settings")
@login_required
@accesstoken_required
def settings():
    return render_template(
        "swan/settings.jinja",
        tokens=tokens,
        wallets=None,
        me=None,
        cookies=request.cookies,
    )
