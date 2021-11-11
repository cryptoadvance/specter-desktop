import base64
import hashlib
import json
import logging
import secrets
from functools import wraps

import requests
from flask import Flask, Response, redirect, render_template, request
from ..service_settings_manager import ServiceSettingsManager
from .manifest import SwanService

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


@swan_endpoint.route("/")
def index():
    # Do we have a token already?
    if tokens.get("access_token"):
        return redirect("/dashboard")
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
        "scope=openid",
    ]
    flow_url = flow_url + "&".join(query_params)
    return render_template("index.jinja", flow_url=flow_url)


@swan_endpoint.route("/oauth2/callback")
def oauth2_auth():
    if request.args.get("error"):
        print(request.args.get("error"))
        print(request.args.get("error_description"))
        return render_template(
            "error.html",
            error=request.args.get("error"),
            error_description=request.args.get("error_description"),
            cookies=request.cookies,
        )
    code = request.args.get("code")
    print(f"looks good, we got a code: {code}")
    print(f"try to get an access-token: ")
    print(f"client_secret : {client_secret}")
    print(f"code_verifier: {code_verifier}")
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
        tokens["access_token"] = resp["access_token"]
    else:
        return render_template(
            "error.html",
            response=response.text,
            error=request.args.get("error"),
            error_description=request.args.get("error_description"),
            cookies=request.cookies,
        )
    return redirect("/dashboard")


@swan_endpoint.route("/balances")
def balances():
    """The dashboard is supposed to only be used authenticated"""
    if not tokens.get("access_token"):
        return redirect("/")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    # Some easy calls:
    me = requests.get("https://dev-api.swanbitcoin.com/oidc/me", headers=headers).text
    wallets = requests.get(
        "https://dev-api.swanbitcoin.com/apps/v20210824/wallets", headers=headers
    ).text
    # we need to pass in the headers in order to not get CSRF-issues
    # client.whoami(cookie=kratos_session)

    return render_template(
        "dashboard.html", tokens=tokens, wallets=wallets, me=me, cookies=request.cookies
    )


@swan_endpoint.route("/trade")
def trade():
    return render_template(
        "dashboard.html", tokens=tokens, wallets=wallets, me=me, cookies=request.cookies
    )


@swan_endpoint.route("/resources")
def resources():
    return render_template("resources.html")


@swan_endpoint.route("/deposit")
def deposit():
    return render_template(
        "resources.html", tokens=tokens, wallets=None, me=None, cookies=request.cookies
    )


@swan_endpoint.route("/withdraw")
def withdraw():
    return render_template(
        "resources.html", tokens=tokens, wallets=None, me=None, cookies=request.cookies
    )


@swan_endpoint.route("/settings")
def settings():
    return render_template(
        "resources.html", tokens=tokens, wallets=None, me=None, cookies=request.cookies
    )
