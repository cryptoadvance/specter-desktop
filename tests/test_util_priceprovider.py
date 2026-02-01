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
from mock import MagicMock, Mock, patch


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
    
    # Test 1: Mock 404 error for invalid currency
    currency = "notExisting"
    url = "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
    
    mock_404_response = Mock()
    mock_404_response.status_code = 404
    mock_404_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=Mock(status_code=404)
    )
    mock_404_response.json.return_value = {"error": "Not found"}
    
    with patch.object(requests_session, 'get', return_value=mock_404_response):
        with pytest.raises(SpecterError) as se:
            failsafe_request_get(requests_session, url)
        assert (
            f"HttpError 404 for https://www.bitstamp.net/api/v2/ticker/btcnotExisting"
            in str(se.value)
        )

    # Test 2: Mock JSON error response (response with "errors" key)
    currency = "usd"
    url = "https://www.bitstamp.net/api/v2/ohlc/btc{}/?limit=A&step=86400&start={}".format(
        currency, 6275453759
    )
    
    mock_json_error_response = Mock()
    mock_json_error_response.status_code = 200
    mock_json_error_response.json.return_value = {"errors": ["Invalid parameters"]}
    
    with patch.object(requests_session, 'get', return_value=mock_json_error_response):
        with pytest.raises(SpecterError) as se:
            failsafe_request_get(requests_session, url)
        assert str(se.value).startswith("JSON error:")

    # Test 3: Mock 404 error for httpbin
    mock_httpbin_404 = Mock()
    mock_httpbin_404.status_code = 404
    mock_httpbin_404.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=Mock(status_code=404)
    )
    mock_httpbin_404.json.return_value = {}
    
    with patch.object(requests_session, 'get', return_value=mock_httpbin_404):
        with pytest.raises(SpecterError) as se:
            failsafe_request_get(requests_session, "https://httpbin.org/status/404")
        # Also allow for Gateway Timeout (504 error), mainly for the CI
        assert f"HttpError 404 for https://httpbin.org/status/404" in str(
            se.value
        ) or f"HttpError 504 for https://httpbin.org/status/404" in str(se.value)

    # Test 4: Mock successful JSON response
    mock_success_response = Mock()
    mock_success_response.status_code = 200
    mock_success_response.json.return_value = {
        "slideshow": {
            "author": "Yours Truly",
            "date": "date of publication",
            "slides": [{"title": "Wake up to WonderWidgets!", "type": "all"}],
            "title": "Sample Slide Show",
        }
    }
    
    with patch.object(requests_session, 'get', return_value=mock_success_response):
        json = failsafe_request_get(requests_session, "https://httpbin.org/json")
        assert json["slideshow"]


def test_get_price_at():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    specter_mock.price_check = True
    
    # Mock responses for different providers
    def mock_get(url):
        response = Mock()
        response.status_code = 200
        
        # Bitstamp ticker endpoint
        if "bitstamp.net/api/v2/ticker" in url:
            response.json.return_value = {"last": "45000.50"}
        # Coindesk currentprice endpoint
        elif "api.coindesk.com/v1/bpi/currentprice" in url:
            currency_code = url.split("/")[-1].replace(".json", "")
            response.json.return_value = {
                "bpi": {
                    currency_code: {"rate_float": 45000.50}
                }
            }
        else:
            response.json.return_value = {}
        
        return response
    
    # Test with bitstamp_eur
    specter_mock.price_provider = "bitstamp_eur"
    with patch('requests.Session.get', side_effect=mock_get):
        mytuple = get_price_at(specter_mock)
        assert float(mytuple[0])
        assert mytuple[1] == "€"

    # Now test them all for bitstamp and coindesk (skip spotbit as it requires Tor)
    for currency in currency_mapping.keys():
        for exchange in currency_mapping[currency]["support"]:
            if exchange.startswith("spotbit_"):
                # ignore for now
                continue
            specter_mock.price_provider = f"{exchange}_{currency}"
            with patch('requests.Session.get', side_effect=mock_get):
                mytuple = get_price_at(specter_mock)
                assert float(mytuple[0])
                assert mytuple[1] == currency_mapping[currency]["symbol"]


def test_get_price_at_historic():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    specter_mock.price_check = True
    
    # Mock response for historic prices
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "ohlc": [
                {
                    "close": "62000.00",
                    "timestamp": "1636551359"
                }
            ]
        }
    }
    
    specter_mock.price_provider = f"bitstamp_usd"
    with patch('requests.Session.get', return_value=mock_response):
        mytuple = get_price_at(specter_mock, 1636551359)
        assert float(mytuple[0]) > 60000


def test_get_price_at_errorhandling():
    specter_mock = MagicMock()
    specter_mock.requests_session.return_value = requests.Session()
    specter_mock.price_check = True
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
