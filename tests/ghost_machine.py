import pytest

# Using https://iancoleman.io/bip39/ and https://jlopp.github.io/xpub-converter/
# mnemonic = "ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine"


# m/44'/0'/0'


@pytest.fixture
def ghost_machine_xpub_44():
    xpub = "xpub6CGap5qbgNCEsvXg2gAjEho17zECMA9PbZa7QkrEWTPnPRaubE6qKots5pNwhyFtuYSPa9gQu4jTTZi8WPaXJhtCHrvHQaFRqayN1saQoWv"
    return xpub


# m/49'/0'/0'


@pytest.fixture
def ghost_machine_xpub_49():
    xpub = "xpub6BtcNhqbaFaoC3oEfKky3Sm22pF48U2jmAf78cB3wdAkkGyAgmsVrgyt1ooSt3bHWgzsdUQh2pTJ867yTeUAMmFDKNSBp8J7WPmp7Df7zjv"
    return xpub


@pytest.fixture
def ghost_machine_ypub():
    ypub = "ypub6WisgNWWiw8H3LzMVgYbFXrXCnPW562EgHBKv14wKdYdoNnPwS34Uke231m2sxFCvL7gNx1FVUor1NjYBLtB9zvpBi8cQ37bn7qTVqo3fjR"
    return ypub


@pytest.fixture
def ghost_machine_tpub_49():
    tpub = "tpubDC5CZBbVc15fpTeqkyUBKgHqYCqkeaUtPjvGz7RJEttndfcN29psPcxTSj5RNJaWYaRQq8kqovLBrZA2tju3ThSAP9fY1eiSvorchnseFZu"
    return tpub


@pytest.fixture
def ghost_machine_upub():
    upub = "upub5DCn7wm4SgVmzmtdoi8DVVfxhBJkqL1L6mmKHNgVky1Fj5VyBxV6NzKD957sr5fWXkY5y8THtqSVWWpjLnomBYw4iXpxaPbkXg5Gn6s5tQf"
    return upub


# m/84'/0'/0'


@pytest.fixture
def ghost_machine_xpub_84():
    xpub = "xpub6CjsHfiuBnHMPBkxThQ4DDjTw2Qq3VMEVcPBoMBGejZGkj3WQR15LeJLmymPpSzYHX21C8SdFWHgMw2RUBdAQ2Aj4MMS93a68mxPQeS8oHr"
    return xpub


@pytest.fixture
def ghost_machine_zpub():
    zpub = "zpub6rQPu14jV9NK5n9C8QyJdPvUGxhivjLEKqRdN8y3QkK2rvfxujLCamccpPgZpGJP6oFch5dkApzn8WFYuaTBzVXvo2kHJsD4gE5gBnCBYj1"
    return zpub


@pytest.fixture
def ghost_machine_tpub_84():
    tpub = "tpubDC4DsqH5rqHqipMNqUbDFtQT3AkKkUrvLsN6miySvortU3s1LGaNVAb7wX2No2VsuxQV82T8s3HJLv3kdx1CPjsJ3onC1Zo5mWCQzRVaWVX"
    return tpub


@pytest.fixture
def ghost_machine_vpub():
    vpub = "vpub5Y24kG7ZrCFRkRnHia2sdnt5N7MmsrNry1jMrP8XptMEcZZqkjQA6bc1f52RGiEoJmdy1Vk9Qck9tAL1ohKvuq3oFXe3ADVse6UiTHzuyKx"
    return vpub
