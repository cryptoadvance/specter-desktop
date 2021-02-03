import requests
import os
import json
import logging
from flask import current_app as app

logger = logging.getLogger(__name__)


class VaultoroApi:
    def __init__(self, token):
        self.token = token

    def get_me(self):
        return self._call_api("/me", "GET")

    def get_balances(self):
        return self._call_api("/private/balances", "GET")

    def get_market_price(self, pair="GOLDBTC"):
        return self._call_api("/public/ticker", "GET", params={"pair": pair})

    def get_active_address(self, asset="BTC"):
        addresses = self.get_wallet_addresses(asset)
        active_address = [
            myobject["address"] for myobject in addresses if myobject["active"] == True
        ][0]
        return active_address

    def get_wallet_addresses(self, asset="BTC"):
        addresses = self._get_wallet_address("GET", asset)

        if addresses == {}:
            logger.debug("No deposit-address found, asking for a new one!")
            addresses = self._get_wallet_address("POST", asset)
            print(f".........+ {addresses}")
        return addresses

    def _get_wallet_address(self, method, asset="BTC"):
        return self._call_api("/private/coins/address", method, params={"asset": asset})

    def get_quote(self, pair, mytype, total, quantity):
        data = {"type": mytype, "pair": pair}
        if total != None:
            data["total"] = float(total)
        elif quantity != None:
            data["quantity"] = float(quantity)
        else:
            raise Exception("Neither total nor quantity set")
        return self._call_api("/private/orders/quote", "POST", data=data)

    def create_order(self, pair, mytype, total, quantity):
        data = {
            "matchType": "OTC",
            "type": mytype,
            "pair": pair,
            "quantity": quantity,
            "total": total,
        }
        if quantity is None or total is None or mytype is None:
            raise Exception("quantity not set")
        return self._call_api("/private/orders/", "POST", data=data)

    def get_trades(self):
        # As The API on the test-server isn't returning any usefull data,
        # let's return fake-data in the meantime
        return json.loads(
            """
            {
                "data": [
                    {
                        "createdAt": 1595427428,
                        "fees": {
                            "typeHandle": "VOLUME30",
                            "value": "-0.01900000",
                            "handle": "GOLD"
                        },
                        "matchType": "LIMIT",
                        "orderReferenceId": "dczi1trxkcwatf0x",
                        "pair": "GOLDBTC",
                        "price": "0.00615450",
                        "quantity": "1.0000",
                        "referenceId": "1pxn6pkkcxgaq9o",
                        "type": "BUY",
                        "updatedAt": 1595427428
                    },
                    {
                        "createdAt": 1595427428,
                        "fees": {
                            "typeHandle": "VOLUME30",
                            "value": "-0.01900000",
                            "handle": "GOLD"
                        },
                        "matchType": "LIMIT",
                        "orderReferenceId": "dczi1trxkcwatf0x",
                        "pair": "GOLDBTC",
                        "price": "0.00615450",
                        "quantity": "1.0000",
                        "referenceId": "1pxn6pkkcxgaq9o",
                        "type": "BUY",
                        "updatedAt": 1595427428
                    }

                ],
                "pagination": {
                    "count": 1
                }
            }
            """
        )

        return self._call_api(
            "/private/history/trades", "GET", params={"pair": "GOLDBTC"}
        )

    def coins_withdraw(self, otp, address, quantity):
        return self._call_api(
            "/private/coins/withdraw",
            "POST",
            params={
                "asset": "BTC",
                "otp": otp,
                "address": address,
                "quantity": quantity,
            },
        )

    def coins_withdraw_fees(self, quantity):
        return self._call_api(
            "/private/coins/withdraw/fees",
            "POST",
            params={"asset": "BTC", "quantity": quantity},
        )

    def _call_api(self, url, method, params=None, data=None):
        # Use the proxy or not?!
        url = self.calc_url(url)
        headers = self._get_headers()
        session = requests.session()
        if data != None:
            data = json.dumps(data)
        logger.debug(f"VTClient Calling {url}")
        logger.debug(f"VTClient method  {method}")
        logger.debug(f"VTClient params  {params}")
        logger.debug(f"VTClient data    {data}")
        logger.debug(f"VTClient headers {headers}")
        response = session.request(
            method,
            url,
            params=params,
            data=data,
            stream=False,
            headers=headers,
        )
        result = response.text
        logger.debug(f"VTClient result {result}")
        try:
            result = json.loads(result)
        except:
            raise Exception(
                f"Could not json-parse response, got {response.status_code}"
            )
        if result.get("data"):
            return result["data"]
        if result.get("errors"):
            raise Exception(f"got {response.status_code} and error {result['errors']}")
        return result

    def _get_headers(self):
        return {"Vtoken": self.token, "Content-type": "application/json"}

    def calc_url(self, path):
        # vaultoro_url=os.getenv("VAULTORO_API", "https://api.vaultoro.com/v1")

        # ToDo: whitelist instead of blacklist.

        # ToDo: decide where to use which domain.
        domain = "http://localhost:25441/vaultoro/.vaultoro/v1"

        # pathes which won't go through the proxy
        logger.info(f"Making Vaultoro-request: {path}")
        exceptions_for_proxy_filter = [
            "/me",
            "/private/balances",
            "/private/orders/quote",
        ]
        for exc_path in exceptions_for_proxy_filter:
            if path.endswith(exc_path):
                domain = app.config["VAULTORO_API"]

        return domain + path
