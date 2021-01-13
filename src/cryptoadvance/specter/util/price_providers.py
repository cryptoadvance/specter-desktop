import requests
import logging

logger = logging.getLogger(__name__)


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
            if specter.price_provider.startswith("bitstamp"):
                currency = "usd"
                currency_symbol = "$"
                if specter.price_provider.endswith("_eur"):
                    currency = "eur"
                    currency_symbol = "€"
                elif specter.price_provider.endswith("_gbp"):
                    currency = "gbp"
                    currency_symbol = "£"
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
                return (True, price, currency_symbol)
            if specter.price_provider == "coindesk_eur":
                if timestamp == "now":
                    price = requests_session.get(
                        "https://api.coindesk.com/v1/bpi/currentprice/EUR.json"
                    ).json()["bpi"]["EUR"]["rate_float"]
                else:
                    return False, 0, ""
                return (True, price, "€")
            if specter.price_provider == "coindesk_gbp":
                if timestamp == "now":
                    price = requests_session.get(
                        "https://api.coindesk.com/v1/bpi/currentprice/GBP.json"
                    ).json()["bpi"]["GBP"]["rate_float"]
                else:
                    return False, 0, ""
                return (True, price, "£")
            if specter.price_provider.startswith("spotbit"):
                currency = "usd"
                currency_symbol = "$"
                if specter.price_provider.endswith("_eur"):
                    currency = "eur"
                    currency_symbol = "€"
                elif specter.price_provider.endswith("_gbp"):
                    currency = "gbp"
                    currency_symbol = "£"
                exchange = specter.price_provider.split("spotbit_")[1]
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
                return (True, price, currency_symbol)
    except Exception as e:
        logger.warning(
            "Failed to get price data from: {}. Exception: {}".format(
                specter.price_provider, e
            )
        )
    return (False, 0, "")
