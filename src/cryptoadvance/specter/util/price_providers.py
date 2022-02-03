import requests
import logging
from ..specter_error import SpecterError, handle_exception

logger = logging.getLogger(__name__)

OZ_TO_G = 28.3495231

currency_mapping = {
    "usd": { 
        "symbol": "$", 
        "support": 
            ["bitstamp","coindesk","spotbit_coinbase","spotbit_kraken","spotbit_bitfinex","spotbit_okcoin","spotbit_bitstamp"]
        },
    "eur": { "symbol": "€", "support": ["bitstamp","coindesk","spotbit_coinbase","spotbit_kraken",
             "spotbit_bitfinex","spotbit_okcoin_eur","spotbit_bitstamp"] },
    "gbp": { "symbol": "£", "support": ["bitstamp","coindesk","spotbit_coinbase","spotbit_kraken",
             "spotbit_bitfinex","spotbit_bitstamp"] },
    "chf": { "symbol": " Fr.", "support": ["coindesk","spotbit_coinbase","spotbit_kraken"] },
    "aud": { "symbol": "$", "support": ["coindesk","spotbit_coinbase","spotbit_kraken"] },
    "cad": { "symbol": "$", "support": ["coindesk","spotbit_coinbase","spotbit_kraken"] },
    "nzd": { "symbol": "$", "support": ["coindesk","spotbit_coinbase"] },
    "hkd": { "symbol": "$", "support": ["coindesk","spotbit_coinbase"] },
    "jpy": { "symbol": "¥", "support": ["coindesk","spotbit_coinbase","spotbit_kraken","spotbit_bitfinex"] },
    "rub": { "symbol": "₽", "support": ["coindesk","spotbit_coinbase"] },
    "ils": { "symbol": "₪", "support": ["coindesk","spotbit_coinbase"] },
    "jod": { "symbol": "د.ا", "support": ["coindesk","spotbit_coinbase"] },
    "twd": { "symbol": "$", "support": ["coindesk","spotbit_coinbase"] },
    "brl": { "symbol": " BRL", "support": ["coindesk","spotbit_coinbase"] },
    "xau": { "symbol": " oz. ", "support": ["coindesk","spotbit_coinbase"], "weight_unit_convertible": True },
    "xag": { "symbol": " oz. ", "support": ["coindesk","spotbit_coinbase"], "weight_unit_convertible": True },
    "xpt": { "symbol": " oz. ", "support": ["spotbit_coinbase"], "weight_unit_convertible": True },
    "xpd": { "symbol": " oz. ", "support": ["spotbit_coinbase"], "weight_unit_convertible": True }
}

def update_price(specter, current_user):
    try:
        price, symbol = get_price_at(specter, current_user, timestamp="now")
        specter.update_alt_rate(price, current_user)
        specter.update_alt_symbol(symbol, current_user)
        return True
    except Exception as e:
        handle_exception(e)
        return False


"""
    Tries to get the current BTC price based on the user provider preferences.
    Returns: (success, price, symbol)
"""


# (provider, currency) = specter.price_provider.split()

def get_price_at(specter, current_user, timestamp="now"):
    try:
        if specter.price_check:
            requests_session = specter.requests_session(
                force_tor=("spotbit" in specter.price_provider)
            )
            # something like "spotbit_bitstamp":
            (exchange, currency) = parse_exchange_currency(specter.price_provider)
            try:
                currency_symbol = currency_mapping[currency]["symbol"]
                weight_unit_convertible = currency_mapping[currency].get("weight_unit_convertible", False)
            except AttributeError:
                raise SpecterError(f"Currency not supported: {currency}")

            if exchange not in currency_mapping[currency]["support"]:
                raise SpecterError(f"The currency {currency} is not supported on exchange {exchange}")

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
                    raise SpecterError("coindesk does not support historic prices")
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

            return (price, currency_symbol)
    except SpecterError as se:
        raise se
    except Exception as e:
        handle_exception(e)
        raise SpecterError(e)

def parse_exchange_currency(exchange_currency):
    # e.g. "spotbit_bitstamp_eur" or "bitstamp_eur"
    arr = exchange_currency.split("_")
    if len(arr) == 2:
        return arr[0], arr[1]
    elif len(arr) == 3:
        return f"{arr[0]}_{arr[1]}", arr[2]
    raise SpecterError(f"Cannot parse exchange_currency: {exchange_currency}")
