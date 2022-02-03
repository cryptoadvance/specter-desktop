
from webbrowser import get
import requests
import pytest
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.price_providers import get_price_at, currency_mapping, parse_exchange_currency
from mock import MagicMock


def test_underlying_requests():
    ''' This test might fail on MacOS
        see #1512
     '''
    specter_mock = Specter()
    requests_session = specter_mock.requests_session()
    currency = "eur"
    price = requests_session.get(
        "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
    ).json()["last"]
    assert type(price) == str
    assert float(price)

def test_get_price_at():
    specter_mock = MagicMock()
    #specter_mock = Specter()
    specter_mock.requests_session.return_value = requests.Session()
    specter_mock.price_provider = "bitstamp_eur"
    specter_mock.price_provider = "bitstamp_eur"
    # returns a tuple like (True, price, currency_symbol)
    mytuple = get_price_at(specter_mock, None)
    assert float(mytuple[0])
    assert mytuple[1] == "€"

    # Now test them all for bitstamp
    # https://www.bitstamp.net/api/#ticker
    for currency in currency_mapping.keys():
        for exchange in currency_mapping[currency]["support"]:
            if exchange.startswith("spotbit_"):
                # ignore for now
                continue
            specter_mock.price_provider = f"{exchange}_{currency}"
            mytuple = get_price_at(specter_mock, None)
            assert float(mytuple[0])
            assert mytuple[1] == currency_mapping[currency]["symbol"]

def test_get_price_at_historic():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    # historic-prices:    
    
    specter_mock.price_provider = f"bitstamp_usd"
    mytuple = get_price_at(specter_mock, None, 1636551359)
    assert float(mytuple[0]) > 60000

def test_get_price_at_errorhandling():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    # some unsupported stuff:
    
    specter_mock.price_provider = f"bitstamp_ils"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, None)
    assert "The currency ils is not supported on exchange bitstamp" in str(se.value)
    
    specter_mock.price_provider = f"bitstamp"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, None)
    assert "Cannot parse exchange_currency: bitstamp" in str(se.value)
    
    specter_mock.price_provider = f"coindesk_usd"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, None, "someOtherDate")
    assert "coindesk does not support historic prices" in str(se.value)

    specter_mock.price_provider = f"spotbit_coindesk_usd"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, None, "someOtherDate")
    # ToDo: Better error-messaging. spotbit_coindesk does not even exist!
    assert "The currency usd is not supported on exchange spotbit_coindesk" in str(se.value)

def test_parse_exchange_currency():
    assert parse_exchange_currency("bitstamp_eur") == ("bitstamp" , "eur")
    assert parse_exchange_currency("spotbit_bitstamp_eur") == ("spotbit_bitstamp" , "eur")
    with pytest.raises(SpecterError):
        parse_exchange_currency("something_spotbit_bitstamp_eur")
    with pytest.raises(SpecterError):
        parse_exchange_currency("bitstamp")