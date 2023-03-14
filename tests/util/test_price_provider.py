from webbrowser import get
import requests
import pytest
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.price_providers import (
    get_price_at,
    currency_mapping,
    _parse_exchange_currency,
    failsafe_request_get,
)
from mock import MagicMock


def test_underlying_requests(empty_data_folder):
    """This test might fail on MacOS
    see #1512
    """
    specter_mock = Specter(data_folder=empty_data_folder, checker_threads=False)
    requests_session = specter_mock.requests_session()
    currency = "eur"
    price = requests_session.get(
        "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
    ).json()["last"]
    assert type(price) == str
    assert float(price)


def test_failsafe_request_get(empty_data_folder):
    specter_mock = Specter(data_folder=empty_data_folder, checker_threads=False)
    requests_session = specter_mock.requests_session()
    currency = "notExisting"
    url = "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
    with pytest.raises(SpecterError) as se:
        failsafe_request_get(requests_session, url)
    assert (
        f"HttpError 404 for https://www.bitstamp.net/api/v2/ticker/btcnotExisting"
        in str(se.value)
    )

    currency = "usd"
    # timestamp most probably in the future
    url = "https://www.bitstamp.net/api/v2/ohlc/btc{}/?limit=A&step=86400&start={}".format(
        currency, 6275453759
    )
    with pytest.raises(SpecterError) as se:
        failsafe_request_get(requests_session, url)
    assert str(se.value).startswith("JSON error:")

    with pytest.raises(SpecterError) as se:
        failsafe_request_get(requests_session, "https://httpbin.org/status/404")
    # Also allow for Gateway Timeout (504 error), mainly for the CI
    assert f"HttpError 404 for https://httpbin.org/status/404" in str(
        se.value
    ) or f"HttpError 504 for https://httpbin.org/status/404" in str(se.value)

    json = failsafe_request_get(requests_session, "https://httpbin.org/json")
    assert json["slideshow"]


def test_get_price_at():
    specter_mock = MagicMock()
    # specter_mock = Specter()
    specter_mock.requests_session.return_value = requests.Session()
    specter_mock.price_provider = "bitstamp_eur"
    specter_mock.price_provider = "bitstamp_eur"
    # returns a tuple like (True, price, currency_symbol)
    mytuple = get_price_at(specter_mock)
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
            mytuple = get_price_at(specter_mock)
            assert float(mytuple[0])
            assert mytuple[1] == currency_mapping[currency]["symbol"]


def test_get_price_at_historic():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    # historic-prices:

    specter_mock.price_provider = f"bitstamp_usd"
    mytuple = get_price_at(specter_mock, 1636551359)
    assert float(mytuple[0]) > 60000


def test_get_price_at_errorhandling():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    # some unsupported stuff:

    specter_mock.price_provider = f"bitstamp_ils"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock)
    assert "The currency ils is not supported on exchange bitstamp" in str(se.value)

    specter_mock.price_provider = f"bitstamp"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock)
    assert "Cannot parse exchange_currency: bitstamp" in str(se.value)

    specter_mock.price_provider = f"coindesk_usd"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, "someOtherDate")
    assert "coindesk does not support historic prices" in str(se.value)

    specter_mock.price_provider = f"spotbit_coindesk_usd"
    with pytest.raises(SpecterError) as se:
        get_price_at(specter_mock, "someOtherDate")
    # ToDo: Better error-messaging. spotbit_coindesk does not even exist!
    assert "The currency usd is not supported on exchange spotbit_coindesk" in str(
        se.value
    )


def test_parse_exchange_currency():
    assert _parse_exchange_currency("bitstamp_eur") == ("bitstamp", "eur")
    assert _parse_exchange_currency("spotbit_bitstamp_eur") == (
        "spotbit_bitstamp",
        "eur",
    )
    with pytest.raises(SpecterError):
        _parse_exchange_currency("something_spotbit_bitstamp_eur")
    with pytest.raises(SpecterError):
        _parse_exchange_currency("bitstamp")
