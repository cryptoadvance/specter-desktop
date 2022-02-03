

from cryptoadvance.specter.specter import Specter



def test_underlying_requests():
    ''' This test might fail on MacOS
        see #1512
     '''
    specter_mock = Specter()
    requests_session = specter_mock.requests_session()
    currency = "usd"
    price = requests_session.get(
        "https://www.bitstamp.net/api/v2/ticker/btc{}".format(currency)
    ).json()["last"]
    assert type(price) == str
    assert float(price)
