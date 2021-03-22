import requests
import logging

logger = logging.getLogger(__name__)

OZ_TO_G = 28.3495231


def update_price(specter, current_user):
    success, price, symbol = get_price_at(specter, current_user, timestamp="now")
    if success:
        specter.update_alt_rate(price, current_user)
        specter.update_alt_symbol(symbol, current_user)
    return success


"""
    Tries to get the current BTC price based on the user provider preferences.
    Returns: (success, price, symbol)
"""


def get_price_at(specter, current_user, timestamp="now"):
    try:
        if specter.price_check:
            requests_session = specter.requests_session(
                force_tor=("spotbit" in specter.price_provider)
            )
            currency = "usd"
            currency_symbol = "$"
            weight_unit_convertible = False
            if specter.price_provider.endswith("_eur"):
                currency = "eur"
                currency_symbol = "€"
            elif specter.price_provider.endswith("_gbp"):
                currency = "gbp"
                currency_symbol = "£"
            elif specter.price_provider.endswith("_chf"):
                currency = "chf"
                currency_symbol = " Fr."
            elif specter.price_provider.endswith("_aud"):
                currency = "aud"
                currency_symbol = "$"
            elif specter.price_provider.endswith("_cad"):
                currency = "cad"
                currency_symbol = "$"
            elif specter.price_provider.endswith("_nzd"):
                currency = "nzd"
                currency_symbol = "$"
            elif specter.price_provider.endswith("_hkd"):
                currency = "hkd"
                currency_symbol = "$"
            elif specter.price_provider.endswith("_jpy"):
                currency = "jpy"
                currency_symbol = "¥"
            elif specter.price_provider.endswith("_rub"):
                currency = "rub"
                currency_symbol = "₽"
            elif specter.price_provider.endswith("_ils"):
                currency = "ils"
                currency_symbol = "₪"
            elif specter.price_provider.endswith("_jod"):
                currency = "jod"
                currency_symbol = "د.ا"
            elif specter.price_provider.endswith("_twd"):
                currency = "twd"
                currency_symbol = "$"
            elif specter.price_provider.endswith("_brl"):
                currency = "brl"
                currency_symbol = " BRL"
            elif specter.price_provider.endswith("_xau"):
                currency = "xau"
                currency_symbol = " oz. "
                weight_unit_convertible = True
            elif specter.price_provider.endswith("_xag"):
                currency = "xag"
                currency_symbol = " oz. "
                weight_unit_convertible = True
            elif specter.price_provider.endswith("_xpt"):
                currency = "xpt"
                currency_symbol = " oz. "
                weight_unit_convertible = True
            elif specter.price_provider.endswith("_xpd"):
                currency = "xpd"
                currency_symbol = " oz. "
                weight_unit_convertible = True

            if specter.price_provider.startswith("bitstamp"):
                if timestamp == "now":
                    price = requests_session.get(
                        "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
                    ).json()["last"]
                else:
                    price = requests_session.get(
                        "https://www.bitstamp.net/api/v2/ohlc/btc{}/?limit=1&step=86400&start={}".format(
                            currency, timestamp
                        )
                    ).json()["data"]["ohlc"][0]["close"]
            elif specter.price_provider.startswith("coindesk"):
                if timestamp == "now":
                    price = requests_session.get(
                        f"https://api.coindesk.com/v1/bpi/currentprice/{currency.upper()}.json"
                    ).json()["bpi"][currency.upper()]["rate_float"]
                else:
                    return False, 0, ""
            elif specter.price_provider.startswith("spotbit"):
                exchange = specter.price_provider.split("spotbit_")[1].split("_")[0]
                if timestamp == "now":
                    price = requests_session.get(
                        "http://h6zwwkcivy2hjys6xpinlnz2f74dsmvltzsd4xb42vinhlcaoe7fdeqd.onion/now/{}/{}".format(
                            currency, exchange
                        )
                    ).json()["close"]
                else:
                    price = requests_session.get(
                        "http://h6zwwkcivy2hjys6xpinlnz2f74dsmvltzsd4xb42vinhlcaoe7fdeqd.onion/hist/{}/{}/{}/{}".format(
                            currency,
                            exchange,
                            timestamp * 1000,
                            (timestamp + 121) * 1000,
                        )
                    ).json()["data"][0][7]
            if weight_unit_convertible:
                if specter.weight_unit == "gram":
                    price = price * OZ_TO_G
                    currency_symbol = " g."
                elif specter.weight_unit == "kg":
                    price = price * OZ_TO_G / 1000
                    currency_symbol = " kg"

            return (True, price, currency_symbol)
    except Exception as e:
        logger.warning(
            "Failed to get price data from: {}. Exception: {}".format(
                specter.price_provider, e
            )
        )
    return (False, 0, "")
