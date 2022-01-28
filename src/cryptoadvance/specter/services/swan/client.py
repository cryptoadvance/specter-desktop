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
client_id = app.config.get("SWAN_CLIENT_ID")
client_secret = app.config.get("SWAN_CLIENT_SECRET")
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
        f"client_id={client_id}",
        "redirect_uri=http://localhost:25441/svc/swan/oauth2/callback",  # TODO: Will localhost work in all usage contexts (e.g. standalone app)?
        "response_type=code",
        "response_mode=query",
        f"code_challenge={code_challenge}",
        "code_challenge_method=S256",
        "state=kjkmdskdmsmmsmdslmdlsm",
        "scope=offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
        "prompt=consent",
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
    # Must explicitly set User-Agent; Swan firewall blocks all requests with "python".
    auth_header = {"User-Agent": "Specter Desktop"}

    if code:
        # Requesting initial refresh_token and access_token
        payload = {
            "client_id": client_id,
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

        payload = {
            "grant_type": "refresh_token",
            # "redirect_uri":   # Necessary?
            "refresh_token": service_data[SwanService.REFRESH_TOKEN],
            "scope": "offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
        }

        auth_hash = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        auth_header["Authorization"] = f"Basic {auth_hash}"

    response = requests.post(
        f"{api_url}/oidc/token",
        data=payload,
        headers=auth_header,
    )
    resp = json.loads(response.text)
    """
        {
            "access_token": "***************",
            "expires_in": 3600,
            "refresh_token": "***************",
            "scope": "offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
            "token_type": "Bearer"
        }
    """
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

        return resp["access_token"]
    else:
        logger.warning(response)
        raise SwanApiException(response.text)


def handle_oauth2_auth_callback(request):
    code = request.args.get("code")
    get_access_token(code=code, code_verifier=code_verifier)


def authenticated_request(
    endpoint: str, method: str = "GET", json_payload: dict = {}
) -> dict:
    logger.debug(f"{method} endpoint: {endpoint}")

    access_token = get_access_token()

    # Must explicitly set User-Agent; Swan firewall blocks all requests with "python".
    auth_header = {
        "User-Agent": "Specter Desktop",
        "Authorization": f"Bearer {access_token}",
    }
    try:
        if method == "GET":
            response = requests.get(api_url + endpoint, headers=auth_header)
        elif method in ["POST", "PATCH", "PUT", "DELETE"]:
            response = requests.request(
                method=method,
                url=api_url + endpoint,
                headers=auth_header,
                json=json_payload,
            )
        if response.status_code != 200:
            raise SwanApiException(f"{response.status_code}: {response.text}")
        return response.json()
    except Exception as e:
        # TODO: tighten up expected Exceptions
        logger.exception(e)
        logger.error(
            f"endpoint: {endpoint} | method: {method} | payload: {json.dumps(json_payload, indent=4)}"
        )
        logger.error(f"{response.status_code}: {response.text}")
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
                }
            }
        }
    """
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
    return resp


def get_autowithdrawal_info() -> dict:
    """
    See note in set_autowithdrawal. This returns all autowithdrawal objs from the Swan
    side.
    """
    resp = authenticated_request(
        endpoint="/apps/v20210824/automatic-withdrawal",
        method="GET",
    )
    return resp


def set_autowithdrawal(btc_threshold: Decimal) -> dict:
    """
    0 == Weekly; other float values = BTC threshold

    The Swan api generates a new autowithdrawal id each time but there is no support to
    update an existing autowithdrawal, other than activating or deactivating it.

    New autowithdrawals are initialized as `isActive: false` and require the user to
    complete a Swan-side email verification step.

    We save the resulting autowithdrawal_id even though it isn't clear at the moment if
    it's desirable to ever call the `deactivate/` or `activate/` endpoints.
    """
    service_data = SwanService.get_current_user_service_data()
    swan_wallet_id = service_data.get(SwanService.SWAN_WALLET_ID)

    endpoint = "/apps/v20210824/automatic-withdrawal"
    method = "POST"
    resp = authenticated_request(
        endpoint=endpoint,
        method=method,
        json_payload={
            "walletId": swan_wallet_id,
            "minBtcThreshold": btc_threshold,
        },
    )

    """
        {
            "entity": "automaticWithdrawal",
            "item": {
                "id": "******************",
                "minBtcThreshold": "0.01",
                "isActive": false,
                "isCanceled": false,
                "createdAt": "2022-01-07T02:14:56.070Z",
                "walletId": "******************",
                "walletAddressId": null
            }
        }
    """
    if "item" in resp and "id" in resp["item"]:
        autowithdrawal_id = resp["item"]["id"]
        if autowithdrawal_id != service_data.get(SwanService.AUTOWITHDRAWAL_ID):
            SwanService.update_current_user_service_data(
                {
                    SwanService.AUTOWITHDRAWAL_ID: autowithdrawal_id,
                }
            )
    else:
        raise SwanApiException(
            f"No 'id' returned for the new/updated autowithdrawal: {json.dumps(resp, indent=4)}"
        )

    return resp


def activate_autowithdrawal() -> dict:
    """
    Activates the autowithdrawal specified in SwanService.AUTOWITHDRAWAL_ID.

    If the automatic withdrawal was just created, this will generate a 400 error:
    "Cannot activate an automatic withdrawal before withdrawal address is confirmed".

    The user must first confirm the first withdrawal addr via Swan-side email flow.
    After they confirm, the autowithdrawal should then return `isActive: true`.

    NOT CURRENTLY USED; remove if we don't ever enable disable/activate flows.
    """
    service_data = SwanService.get_current_user_service_data()
    autowithdrawal_id = service_data.get(SwanService.AUTOWITHDRAWAL_ID)
    if not autowithdrawal_id:
        raise SwanApiException(
            f"AUTOWITHDRAWAL_ID ({SwanService.AUTOWITHDRAWAL_ID}) not found in service data"
        )

    endpoint = f"/apps/v20210824/automatic-withdrawal/{autowithdrawal_id}/activate"
    method = "POST"
    resp = authenticated_request(
        endpoint=endpoint,
        method=method,
    )

    """
        {
            "entity": "automaticWithdrawal",
            "item": {
                "id": "******************",
                "minBtcThreshold": "0.01",
                "isActive": true,
                "isCanceled": false,
                "createdAt": "2022-01-07T02:14:56.070Z",
                "walletId": "******************",
                "walletAddressId": null
            }
        }
    """
    if "item" in resp and "id" in resp["item"]:
        if resp["item"]["id"] != service_data[SwanService.AUTOWITHDRAWAL_ID]:
            autowithdrawal_id = resp["item"]["id"]
    else:
        raise SwanApiException(
            f"No 'id' returned for the new/updated autowithdrawal: {json.dumps(resp, indent=4)}"
        )

    return resp


def get_wallet_details(swan_wallet_id: str) -> dict:
    """
    {
        "entity": "wallet",
        "item": {
            "id": "********************",
            "walletAddressId": ""********************",
            "btcAddress": ""********************",
            "isConfirmed": true,
            "displayName": "Specter Desktop \"DCA Cold Storage\"",
            "metadata": {
                "oidc": {
                    "clientId": "specter-dev"
                },
                "specter_wallet_alias": "dca_cold_storage"
            }
        }
    }
    """
    resp = authenticated_request(
        endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}",
        method="GET",
    )

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
    return resp
