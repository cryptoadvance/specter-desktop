import base64
import datetime
import hashlib
import json
import logging
import pytz
import requests
import secrets

from flask_babel import lazy_gettext as _
from typing import List

from .service import SwanService


logger = logging.getLogger(__name__)


client_id = "specter-dev"
client_secret = "BcetcVcmueWf5P3UPJnHhCBMQ49p38fhzYwM7t3DJGzsXSjm89dDR5URE46SY69j"
code_verifier = "64fRjTuy6SKqdC1wSoInUNxX65dQUhVVKTqZXuQ7dqw"
api_url = "https://dev-api.swanbitcoin.com"


def get_oauth2_start_url():
    """
    Set up the Swan API integration by requesting our initial access_token and
    refresh_token.
    """
    # Let's start the PKCE-flow
    global code_verifier

    if code_verifier is None:
        code_verifier = secrets.token_urlsafe(43)
    # see specification: https://datatracker.ietf.org/doc/html/rfc7636#section-4.2
    # and example impl: https://github.com/RomeoDespres/pkce/blob/master/pkce/__init__.py#L94-L96
    hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
    encoded = base64.urlsafe_b64encode(hashed)
    code_challenge = encoded.decode("ascii")[:-1]
        
    print(f"code_challenge: {code_challenge}")
    flow_url = "https://dev-api.swanbitcoin.com/oidc/auth?"
    query_params = [
        "client_id=specter-dev",
        "redirect_uri=http://localhost:25441/svc/swan/oauth2/callback",     # TODO: Will localhost work in all usage contexts?
        "response_type=code",
        "response_mode=query",
        f"code_challenge={code_challenge}",
        "code_challenge_method=S256",
        "state=kjkmdskdmsmmsmdslmdlsm",
        "scope=offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
    ]
    flow_url += "&".join(query_params)

    return flow_url


def get_access_token(code: str = None, code_verifier: str = None):
    """
    If code and code_verifier are specified, this is our initial request for an 
    access_token and, more importantly, the refresh_token.

    If code is None, use the refresh_token to get a new short-lived access_token.
    """
    if code:
        # Requesting initial refresh_token and access_token
        payload = {
            "client_id": "specter-dev",
            "client_secret": client_secret,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "code": code,
        }
    else:
        service_data = SwanService.get_current_user_service_data()
        if "access_token" in service_data and service_data["expires"] > datetime.datetime.now(tz=pytz.utc).timestamp():
            # Current access_token is still valid!
            return service_data["access_token"]

        # Use the refresh_token to get a new access_token
        if "refresh_token" not in service_data:
            # TODO: Better Exception handling
            raise Exception("Required service integration data not found")
    
        print("api_data: " + json.dumps(service_data, indent=4))
        
        payload = {
            "grant_type": "refresh_token",
            # "redirect_uri":   # Necessary?
            "refresh_token": service_data["refresh_token"],
            "scope": "offline_access",      # Possibly get an updated refresh_token back
        },

    response = requests.post(
        f"{api_url}/oidc/token",
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
        new_api_data = {
            "access_token": resp["access_token"],
            "expires": (datetime.datetime.now(tz=pytz.utc) + datetime.timedelta(seconds=resp["expires_in"])).timestamp(),
        }
        if "refresh_token" in resp:
            new_api_data["refresh_token"] = resp["refresh_token"]

        SwanService.update_current_user_service_data(new_api_data)

        print(json.dumps(SwanService.get_current_user_service_data(), indent=4))
        return resp["access_token"]
    else:
        logger.debug(response)
        raise Exception(response.text)


def handle_oauth2_auth_callback(request):
    code = request.args.get("code")
    logger.debug(f"request.args: {request.args}")
    logger.debug(f"looks good, we got a code: {code}")
    logger.debug(f"try to get an access-token: ")
    logger.debug(f"client_secret : {client_secret}")
    logger.debug(f"code_verifier: {code_verifier}")
    get_access_token(code=code, code_verifier=code_verifier)


def authenticated_request(endpoint: str, method: str = "GET", data: dict = None):
    access_token = get_access_token()

    auth_header = {
        "Authorization": f"Bearer {access_token}",
    }
    try:
        if method == "GET":
            response = requests.get(api_url + endpoint, headers=auth_header)
        elif method == "POST":
            response = requests.post(
                url=api_url + endpoint,
                headers=auth_header,
                data=data,
            )
        elif method == "PUT":
            response = requests.put(
                url=api_url + endpoint,
                headers=auth_header,
                data=data,
            )
        resp = json.loads(response.text)
    except Exception as e:
        # TODO: tighten up expected Exceptions
        logger.exception(e)
        raise e


def update_autowithdrawal_addresses(addresses: List[str], label: str):
    # Swan endpoint specifies "path" (derivation path) but can be omitted
    addr_list = [{"address": addr} for addr in addresses]

    resp = authenticated_request(
        endpoint="/apps/v20210824/wallets",
        method="POST",
        data={
            "btcAddresses": addr_list,
            "displayName": label,
        }
    )

    print(resp)
    return resp

