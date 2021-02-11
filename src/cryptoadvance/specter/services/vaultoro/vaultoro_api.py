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
        return self._call_api("/private/orders", "POST", data=data)

    def get_trades(self):
        res = {
            "GOLDBTC": self._call_api(
                "/private/history/trades", "GET", params={"pair": "GOLDBTC"}
            ),
            "SILVBTC": self._call_api(
                "/private/history/trades", "GET", params={"pair": "SILVBTC"}
            ),
        }

        return {
            "data": list(
                {**trade, "pair": "GOLDBTC"}
                for trade in (
                    res["GOLDBTC"]["data"]
                    if "data" in res["GOLDBTC"]
                    else res["GOLDBTC"]
                )
            )
            + list(
                {**trade, "pair": "SILVBTC"}
                for trade in (
                    res["SILVBTC"]["data"]
                    if "data" in res["SILVBTC"]
                    else res["SILVBTC"]
                )
            )
        }

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

    def _call_api(self, path, method, params=None, data=None):
        """ call the Vaultoro API (or the proxy) """
        headers = self._get_headers(path)
        url = self._calc_url(path)
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

    def _get_headers(self, path):
        """return the VTOKEN, the Content-type and maybe specter-version and -destination"""
        headers = {"Vtoken": self.token, "Content-type": "application/json"}
        if self._is_proxy_call(path):
            headers["Specter-Version"] = app.specter.version.info["current"]
            headers["Specter-Destination"] = app.config["VAULTORO_API"]
        return headers

    def _calc_url(self, path):
        """ returns either Vaultoro or proxy-url """
        if self._is_proxy_call(path):
            return "https://specter-cloud.bitcoinops.de/.vaultoro/v1" + path
            # local development of specter-cloud
            # return "http://localhost.localdomain:5000/.vaultoro/v1"+path
            # with the proxy still in specter-desktop
            # return "http://localhost.localdomain:5000/vaultoro/.vaultoro/v1"+path
        else:
            return app.config["VAULTORO_API"] + path

    def _is_proxy_call(self, path):
        """ Should we call the proxy or Vaultoro directly ? """
        proxy_filter = ["/private/orders"]
        for exc_path in proxy_filter:
            if path.endswith(exc_path):
                return True
        return False
