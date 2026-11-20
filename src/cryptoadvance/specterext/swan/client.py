import base64
import datetime
import hashlib
import json
import logging
import os
import secrets
import sqlite3
import stat
import time
from contextlib import closing, contextmanager
from decimal import Decimal
from os import access
from pathlib import Path
from typing import List
from urllib import request
from urllib.parse import urlparse

import pytz
import requests
from cryptography.fernet import Fernet
from flask import current_app as app
from flask import has_request_context, request as flask_request, session
from flask_babel import lazy_gettext as _

logger = logging.getLogger(__name__)


# TODO: Update with prod values

OAUTH_FLOW_LIFETIME = 600  # seconds
OAUTH_FLOW_LIMIT = 8  # per browser; older tabs can be restarted
OAUTH_SESSION_KEY = "swan_oauth_browser"


@contextmanager
def _oauth_flows():
    """Shared server-side store: separate Gunicorn workers must see the same flows."""
    path = app.config.get("SWAN_OAUTH_DB") or str(
        Path(app.specter.data_folder) / "swan_oauth.sqlite"
    )
    # SQLite can create a journal next to the database; protect the entire folder.
    directory = Path(path).parent
    dir_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(dir_fd, 0o700)
        for name in (
            Path(path).name,
            *(Path(path).name + suffix for suffix in ("-journal", "-wal", "-shm")),
        ):
            flags = os.O_RDWR | os.O_NOFOLLOW
            if name == Path(path).name:
                flags |= os.O_CREAT
            try:
                fd = os.open(name, flags, 0o600, dir_fd=dir_fd)
            except FileNotFoundError:
                continue
            try:
                if not stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError("Swan OAuth store must be a regular file")
                os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
    finally:
        os.close(dir_fd)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS flows (state TEXT PRIMARY KEY, browser TEXT NOT NULL, "
        "user_id TEXT, verifier TEXT NOT NULL, redirect_uri TEXT NOT NULL, expires REAL NOT NULL)"
    )
    with closing(conn), conn:
        yield conn


def _flow_cipher():
    key = hashlib.sha256(app.secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key))


class SwanApiException(Exception):
    pass


class SwanApiRefreshTokenException(SwanApiException):
    pass


class SwanClient:
    def __init__(
        self, hostname, access_token: str, access_token_expires, refresh_token
    ):
        self.hostname = hostname
        self.access_token: str = str(
            access_token
        )  # The ServiceSwan storage might have one in its storage
        self.access_token_expires = (
            access_token_expires  # a timestamp when the access token will expire
        )
        self.refresh_token = refresh_token

        self.api_url = app.config.get("SWAN_API_URL")
        self.client_id = app.config.get("SWAN_CLIENT_ID")
        self.client_secret = app.config.get("SWAN_CLIENT_SECRET")

    def is_access_token_valid(self):
        return (
            self.access_token_expires > datetime.datetime.now(tz=pytz.utc).timestamp()
        )

    def calc_callback_url(self):
        scheme = flask_request.scheme if has_request_context() else "http"
        return f"{scheme}://{self.hostname}{app.config['APP_URL_PREFIX']}{app.config['EXT_URL_PREFIX']}/swan/oauth2/callback"

    def get_oauth2_start_url(self, callback_hostname, user_id=None):
        """
        Set up the Swan API integration by requesting our initial access_token and
        refresh_token.
        """
        # Let's start the PKCE-flow
        self.hostname = callback_hostname
        callback_url = self.calc_callback_url()
        code_verifier = secrets.token_urlsafe(32)
        state = secrets.token_urlsafe(32)
        browser = session.get(OAUTH_SESSION_KEY)
        if not browser:
            browser = secrets.token_urlsafe(32)
            session[OAUTH_SESSION_KEY] = browser
        with _oauth_flows() as flows:
            flows.execute("BEGIN IMMEDIATE")
            now = time.time()
            flows.execute("DELETE FROM flows WHERE expires <= ?", (now,))
            browser_flows = flows.execute(
                "SELECT state FROM flows WHERE browser = ? ORDER BY expires", (browser,)
            ).fetchall()
            for (key,) in browser_flows[: -(OAUTH_FLOW_LIMIT - 1)]:
                flows.execute("DELETE FROM flows WHERE state = ?", (key,))
            flows.execute(
                "INSERT INTO flows VALUES (?, ?, ?, ?, ?, ?)",
                (
                    state,
                    browser,
                    user_id,
                    _flow_cipher()
                    .encrypt(code_verifier.encode("ascii"))
                    .decode("ascii"),
                    callback_url,
                    now + OAUTH_FLOW_LIFETIME,
                ),
            )
        # see specification: https://datatracker.ietf.org/doc/html/rfc7636#section-4.2
        # and example impl: https://github.com/RomeoDespres/pkce/blob/master/pkce/__init__.py#L94-L96
        hashed = hashlib.sha256(code_verifier.encode("ascii")).digest()
        encoded = base64.urlsafe_b64encode(hashed)
        code_challenge = encoded.decode("ascii").rstrip("=")

        flow_url = f"{self.api_url}/oidc/auth?"
        query_params = [
            f"client_id={self.client_id}",
            f"redirect_uri={callback_url}",
            "response_type=code",
            "response_mode=query",
            f"code_challenge={code_challenge}",
            "code_challenge_method=S256",
            f"state={state}",
            "scope=offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
            "prompt=consent",
        ]
        flow_url += "&".join(query_params)

        return flow_url

    def _get_access_token(
        self, code: str = None, code_verifier: str = None, request_uri=None, state=None
    ) -> str:
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
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "state": state,
                "code": code,
                "redirect_uri": request_uri,
            }
        else:
            if self.is_access_token_valid():
                return self.access_token

            # Use the refresh_token to get a new access_token
            if not self.refresh_token:
                raise SwanApiRefreshTokenException(
                    "access_token is expired but we don't have a refresh_token"
                )

            payload = {
                "grant_type": "refresh_token",
                # "redirect_uri":   # Necessary? Probably yes but more difficult to reconstruct it but the refresh-token is not yet used anyway
                "refresh_token": self.refresh_token,
                "scope": "offline_access v1 write:vendor_wallet read:vendor_wallet write:automatic_withdrawal read:automatic_withdrawal",
            }

            auth_hash = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode()
            ).decode()
            auth_header["Authorization"] = f"Basic {auth_hash}"

        try:
            response = requests.post(
                f"{self.api_url}/oidc/token",
                data=payload,
                headers=auth_header,
                timeout=30,
            )
        except requests.exceptions.RequestException as e:
            logger.exception(e)
            raise SwanApiException(
                f"Could not reach the Swan API ({self.api_url}/oidc/token): {e}"
            ) from e
        try:
            resp = json.loads(response.text)
        except ValueError as e:
            logger.error(f"{response.status_code}: {response.text}")
            raise SwanApiException(
                f"Swan API returned no valid json ({response.status_code}): {response.text}"
            ) from e
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
            self.access_token = resp.get("access_token")
            self.access_token_expires = (
                datetime.datetime.now(tz=pytz.utc)
                + datetime.timedelta(seconds=resp["expires_in"])
            ).timestamp()
            self.refresh_token = resp.get("refresh_token")
            return self.access_token
        else:
            logger.warning(response)
            raise SwanApiException(response.text)

    def handle_oauth2_auth_callback(self, request, user_id=None, callback_uri=None):
        state = request.args.get("state")
        browser = session.get(OAUTH_SESSION_KEY)
        if not state or not browser:
            raise SwanApiException("Invalid or expired Swan OAuth state")
        with _oauth_flows() as flows:
            flows.execute("BEGIN IMMEDIATE")
            flow = flows.execute(
                "SELECT browser, user_id, verifier, redirect_uri, expires "
                "FROM flows WHERE state = ?",
                (state,),
            ).fetchone()
            if (
                not flow
                or not secrets.compare_digest(flow[0], browser)
                or flow[1] != user_id
            ):
                raise SwanApiException("Invalid or expired Swan OAuth state")
            # Consume before talking to Swan, including provider errors and failed exchanges.
            flows.execute("DELETE FROM flows WHERE state = ?", (state,))
        if flow[4] <= time.time():
            raise SwanApiException("Invalid or expired Swan OAuth state")
        if request.args.get("error"):
            raise SwanApiException("Swan OAuth authorization was declined")
        code = request.args.get("code")
        if not code:
            raise SwanApiException(
                "Swan OAuth callback is missing an authorization code"
            )
        rp = urlparse(request.url)
        request_uri = callback_uri or f"{rp.scheme}://{rp.netloc}{rp.path}"
        if request_uri != flow[3]:
            raise SwanApiException(
                "Swan OAuth callback URL does not match the authorization"
            )
        self._get_access_token(
            code=code,
            code_verifier=_flow_cipher()
            .decrypt(flow[2].encode("ascii"))
            .decode("ascii"),
            request_uri=flow[3],
            state=state,
        )

    def authenticated_request(
        self, endpoint: str, method: str = "GET", json_payload: dict = {}
    ) -> dict:
        logger.debug(f"{method} endpoint: {endpoint}")

        access_token = self._get_access_token()

        # Must explicitly set User-Agent; Swan firewall blocks all requests with "python".
        auth_header = {
            "User-Agent": "Specter Desktop",
            "Authorization": f"Bearer {access_token}",
        }
        request_context = f"endpoint: {self.api_url}{endpoint} | method: {method} | payload: {json.dumps(json_payload, indent=4)}"

        try:
            if method == "GET":
                response = requests.get(
                    self.api_url + endpoint, headers=auth_header, timeout=30
                )
            elif method in ["POST", "PATCH", "PUT", "DELETE"]:
                response = requests.request(
                    method=method,
                    url=self.api_url + endpoint,
                    headers=auth_header,
                    json=json_payload,
                    timeout=30,
                )
            else:
                raise SwanApiException(f"Unsupported method: {method}")
        except requests.exceptions.RequestException as e:
            # Timeouts, connection errors, ... : no response to report about
            logger.exception(e)
            logger.error(request_context)
            raise SwanApiException(f"Could not reach the Swan API: {e}") from e

        if response.status_code != 200:
            logger.error(request_context)
            logger.error(f"{response.status_code}: {response.text}")
            raise SwanApiException(f"{response.status_code}: {response.text}")

        try:
            return response.json()
        except ValueError as e:
            logger.exception(e)
            logger.error(request_context)
            logger.error(f"{response.status_code}: {response.text}")
            raise SwanApiException(
                f"Swan API returned no valid json ({response.status_code}): {response.text}"
            ) from e

    def get_autowithdrawal_addresses(self, swan_wallet_id: str) -> dict:
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

        resp = self.authenticated_request(
            endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}?full=true",
            method="GET",
        )

        return resp

    def update_autowithdrawal_addresses(
        self,
        swan_wallet_id: str,
        specter_wallet_name: str,
        specter_wallet_alias: str,
        addresses: List[str],
    ) -> str:
        """
        * If SWAN_WALLET_ID is known, any existing unused addresses are cleared.
        * If there is no known SWAN_WALLET_ID, we `POST` to create an initial Swan wallet and store the resulting SWAN_WALLET_ID.
        * Sends the list of new addresses for SWAN_WALLET_ID.
        * Returns the swan wallet id if the response provides it or raises an SwanApiException.
        """
        if swan_wallet_id:
            # We already have a Swan walletId. DELETE the existing unused addresses...
            self.delete_autowithdrawal_addresses(swan_wallet_id)

            # ...and then append the new ones.
            endpoint = f"/apps/v20210824/wallets/{swan_wallet_id}/addresses"
            method = "PATCH"
        else:
            # We don't yet have a Swan walletId. POST to create one.
            endpoint = "/apps/v20210824/wallets"
            method = "POST"

        # For the required structure of the paylod see: https://developers.swanbitcoin.com/api/create-a-new-wallet
        resp = self.authenticated_request(
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
                return swan_wallet_id
        else:
            raise SwanApiException(
                f"No 'id' returned for the new/updated wallet: {json.dumps(resp, indent=4)}"
            )

    def delete_autowithdrawal_addresses(self, swan_wallet_id: str):
        """
        Deletes all unused autowithdrawal addresses from the specified SWAN_WALLET_ID
        """
        resp = self.authenticated_request(
            endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}/addresses",
            method="DELETE",
        )
        return resp

    def get_autowithdrawal_info(self) -> dict:
        """
        See note in set_autowithdrawal. This returns all autowithdrawal objs from the Swan
        side.
        """
        resp = self.authenticated_request(
            endpoint="/apps/v20210824/automatic-withdrawal",
            method="GET",
        )
        return resp

    def set_autowithdrawal(self, swan_wallet_id, btc_threshold: Decimal) -> dict:
        """
        0 == Weekly; other float values = BTC threshold

        The Swan api generates a new autowithdrawal id each time but there is no support to
        update an existing autowithdrawal, other than activating or deactivating it.

        New autowithdrawals are initialized as `isActive: false` and require the user to
        complete a Swan-side email verification step.

        We save the resulting autowithdrawal_id even though it isn't clear at the moment if
        it's desirable to ever call the `deactivate/` or `activate/` endpoints.
        """

        endpoint = "/apps/v20210824/automatic-withdrawal"
        method = "POST"
        resp = self.authenticated_request(
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
            return resp
        else:
            raise SwanApiException(
                f"No 'id' returned for the new/updated autowithdrawal: {json.dumps(resp, indent=4)}"
            )

    def activate_autowithdrawal(self, autowithdrawal_id) -> dict:
        """
        Activates the autowithdrawal specified in SwanService.AUTOWITHDRAWAL_ID.

        If the automatic withdrawal was just created, this will generate a 400 error:
        "Cannot activate an automatic withdrawal before withdrawal address is confirmed".

        The user must first confirm the first withdrawal addr via Swan-side email flow.
        After they confirm, the autowithdrawal should then return `isActive: true`.

        NOT CURRENTLY USED; remove if we don't ever enable disable/activate flows.
        """

        endpoint = f"/apps/v20210824/automatic-withdrawal/{autowithdrawal_id}/activate"
        method = "POST"
        resp = self.authenticated_request(
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
            autowithdrawal_id = resp["item"]["id"]
            return autowithdrawal_id
        raise SwanApiException(
            f"No 'id' returned for the new/updated autowithdrawal: {json.dumps(resp, indent=4)}"
        )

    def get_wallet_details(self, swan_wallet_id: str) -> dict:
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
        resp = self.authenticated_request(
            endpoint=f"/apps/v20210824/wallets/{swan_wallet_id}",
            method="GET",
        )

        return resp

    def get_wallets(self) -> dict:
        """
        Return all Swan wallet entries. Should only be one per Specter-Swan user combo (but can be more due
        to testing/debugging, calling `/wallets` POST more than once, etc.)
        """
        resp = self.authenticated_request(
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
