import base64
import datetime
import hashlib
import json
import logging
import pytz
import requests
import secrets

from decimal import Decimal
from flask import current_app as app
from flask_babel import lazy_gettext as _
from typing import List

from cryptoadvance.specter.wallet import Wallet

from .service import SwanService


logger = logging.getLogger(__name__)


# TODO: Update with prod values
client_id = "specter-dev"
client_secret = "BcetcVcmueWf5P3UPJnHhCBMQ49p38fhzYwM7t3DJGzsXSjm89dDR5URE46SY69j"
code_verifier = "64fRjTuy6SKqdC1wSoInUNxX65dQUhVVKTqZXuQ7dqw"
api_url = app.config.get("SWAN_API_URL")


class SwanApiException(Exception):
    pass


class SwanApiRefreshTokenException(SwanApiException):
    pass


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

    flow_url = f"{api_url}/oidc/auth?"
    query_params = [
        "client_id=specter-dev",
        "redirect_uri=http://localhost:25441/svc/swan/oauth2/callback",  # TODO: Will localhost work in all usage contexts (e.g. standalone app)?
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

    If we don't have the refresh_token, raise SwanApiRefreshTokenException.
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
        if SwanService.is_access_token_valid():
            return service_data[SwanService.ACCESS_TOKEN]

        # Use the refresh_token to get a new access_token
        if SwanService.REFRESH_TOKEN not in service_data:
            raise SwanApiRefreshTokenException(
                "access_token is expired but we don't have a refresh_token"
            )

        payload = (
            {
                "grant_type": "refresh_token",
                # "redirect_uri":   # Necessary?
                "refresh_token": service_data[SwanService.REFRESH_TOKEN],
                "scope": "offline_access",  # Possibly get an updated refresh_token back
            },
        )

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
    # TODO: Remove debugging
    logger.debug(json.dumps(resp, indent=4))
    if resp.get("access_token"):
        new_api_data = {
            SwanService.ACCESS_TOKEN: resp["access_token"],
            SwanService.ACCESS_TOKEN_EXPIRES: (
                datetime.datetime.now(tz=pytz.utc)
                + datetime.timedelta(seconds=resp["expires_in"])
            ).timestamp(),
        }
        if "refresh_token" in resp:
            new_api_data[SwanService.REFRESH_TOKEN] = resp["refresh_token"]

        SwanService.update_current_user_service_data(new_api_data)

        # TODO: Remove debugging
        logger.debug(json.dumps(SwanService.get_current_user_service_data(), indent=4))
        return resp["access_token"]
    else:
        logger.warning(response)
        raise SwanApiException(response.text)


def handle_oauth2_auth_callback(request):
    code = request.args.get("code")
    logger.debug(f"request.args: {request.args}")
    logger.debug(f"looks good, we got a code: {code}")
    get_access_token(code=code, code_verifier=code_verifier)


def authenticated_request(
    endpoint: str, method: str = "GET", json_payload: dict = {}
) -> dict:
    logger.debug(f"{method} endpoint: {endpoint}")

    access_token = get_access_token()

    auth_header = {
        "Authorization": f"Bearer {access_token}",
    }
    try:
        if method == "GET":
            response = requests.get(api_url + endpoint, headers=auth_header)
        elif method in ["POST", "PATCH", "DELETE"]:
            response = requests.request(
                method=method,
                url=api_url + endpoint,
                headers=auth_header,
                json=json_payload,
            )
        return response.json()
    except Exception as e:
        # TODO: tighten up expected Exceptions
        logger.exception(e)
        raise e


def get_autowithdrawal_addresses(swan_wallet_id: str = None) -> dict:
    """
    {
        "entity": "wallet",
        "item": {
            "id": "c47e1e83-90a0-45da-ae25-6a0d324b9f29",
            "isConfirmed": false,
            "displayName": "Specter autowithdrawal to SeedSigner demo",
            "metadata": {
                "oidc": {
                    "clientId": "specter-dev"
                },
                "specter_wallet_alias": "seedsigner_demo"
            },
            "btcAddresses": []
        }
    }
    """
    if not swan_wallet_id:
        swan_wallet_id = SwanService.get_current_user_service_data().get(
            SwanService.SWAN_WALLET_ID
        )

    resp = authenticated_request(
        endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}?full=true",
        method="GET",
    )

    logger.debug(json.dumps(resp, indent=4))
    return resp


def update_autowithdrawal_addresses(
    specter_wallet_name: str, specter_wallet_alias: str, addresses: List[str]
) -> dict:
    """
    * If SWAN_WALLET_ID is known, any existing unused addresses are cleared.
    * If there is no known SWAN_WALLET_ID, we `POST` to create an initial Swan wallet and store the resulting SWAN_WALLET_ID.
    * Sends the list of new addresses for SWAN_WALLET_ID.
    """
    swan_wallet_id = SwanService.get_current_user_service_data().get(
        SwanService.SWAN_WALLET_ID
    )

    if swan_wallet_id:
        # We already have a Swan walletId. DELETE the existing unused addresses...
        delete_autowithdrawal_addresses(swan_wallet_id)

        # ...and then append the new ones.
        endpoint = f"/apps/v20210824/wallets/{swan_wallet_id}/addresses"
        method = "PATCH"
    else:
        # We don't yet have a Swan walletId. POST to create one.
        endpoint = "/apps/v20210824/wallets"
        method = "POST"

    resp = authenticated_request(
        endpoint=endpoint,
        method=method,
        json_payload={
            "btcAddresses": [{"address": addr} for addr in addresses],
            "displayName": str(
                _('Specter Desktop "{}"').format(specter_wallet_name)
            ),  # Can't pass a LazyString into json
            "metadata": {
                "specter_wallet_alias": specter_wallet_alias,
            },
        },
    )

    """
    Response should include wallet ("item") details:
        {
            "entity": "wallet",
            "item": {
                "id": "c47e1e83-90a0-45da-ae25-6a0d324b9f29",
                "isConfirmed": false,
                "displayName": "Specter autowithdrawal to SeedSigner demo",
                "metadata": {
                    "oidc": {
                        "clientId": "specter-dev"
                    },
                    "specter_wallet_alias": "seedsigner_demo"
                },
                "btcAddresses": []
            }
        }
    """
    logger.debug(json.dumps(resp, indent=4))

    if "item" in resp and "id" in resp["item"]:
        if resp["item"]["id"] != swan_wallet_id:
            swan_wallet_id = resp["item"]["id"]

            # Save the swan_wallet_id in the user's persistent Service settings
            logger.debug(f"Updating the Swan wallet id to {swan_wallet_id}")
            SwanService.update_current_user_service_data(
                {SwanService.SWAN_WALLET_ID: swan_wallet_id}
            )
    else:
        raise SwanApiException(
            f"No 'id' returned for the new/updated wallet: {json.dumps(resp, indent=4)}"
        )


def delete_autowithdrawal_addresses(swan_wallet_id: str):
    """
    Deletes all unused autowithdrawal addresses from the specified SWAN_WALLET_ID
    """
    resp = authenticated_request(
        endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}/addresses",
        method="DELETE",
    )
    logger.debug(json.dumps(resp, indent=4))
    return resp


def get_autowithdrawal_info() -> dict:
    """
    Not currently used
    """
    resp = authenticated_request(
        endpoint="/apps/v20210824/automatic-withdrawal",
        method="GET",
    )
    logger.debug(json.dumps(resp, indent=4))
    return resp


def set_autowithdrawal(btc_threshold: Decimal) -> dict:
    """
    0 == Weekly
    """
    swan_wallet_id = SwanService.get_current_user_service_data().get(
        SwanService.SWAN_WALLET_ID
    )

    resp = authenticated_request(
        endpoint="/apps/v20210824/automatic-withdrawal",
        method="POST",
        json_payload={"walletId": swan_wallet_id, "minBtcThreshold": btc_threshold},
    )
    logger.debug(json.dumps(resp, indent=4))

    return resp


def get_wallet_details(swan_wallet_id: str) -> dict:
    """
    {
        "entity": "wallet",
        "item": {
            "id": "********",
            "isConfirmed": false,
            "displayName": "Specter autowithdrawal to SeedSigner demo",
            "metadata": {
                "oidc": {
                    "clientId": "specter-dev"
                },
                "specter_wallet_alias": "seedsigner_demo"
            },
            "btcAddresses": []
        }
    }
    """
    resp = authenticated_request(
        endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}",
        method="GET",
    )

    logger.debug(json.dumps(resp, indent=4))
    return resp


def get_wallets() -> dict:
    """
    Return all Swan wallet entries. Should only be one per Specter-Swan user combo (but can be more due
    to testing/debugging, calling `/wallets` POST more than once, etc.)
    """
    resp = authenticated_request(
        endpoint=f"/apps/v20210824/wallets",
        method="GET",
    )
    """
        {
            "entity": "wallet",
            "list": [
                {
                    "id": "**********",
                    "walletAddressId": "**********",
                    "btcAddress": "bc1q**********",
                    "isConfirmed": false,
                    "displayName": "Specter Desktop \"SeedSigner demo\"",
                    "metadata": {
                        "oidc": {
                            "clientId": "specter-dev"
                        },
                        "specter_wallet_alias": "seedsigner_demo"
                    }
                },
                {
                    "id": "**********",
                    "walletAddressId": "**********",
                    "btcAddress": "bc1q**********",
                    "isConfirmed": false,
                    "displayName": "Specter Desktop \"DCA Corn\"",
                    "metadata": {
                        "oidc": {
                            "clientId": "specter-dev"
                        },
                        "specter_wallet_alias": "dca_corn_2"
                    }
                },
                ...,
            ]
        }
    """
    logger.debug(json.dumps(resp, indent=4))

    return resp
