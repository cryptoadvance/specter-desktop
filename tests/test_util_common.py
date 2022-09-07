from cryptoadvance.specter.util.common import (
    camelcase2snake_case,
    snake_case2camelcase,
    str2bool,
    format_btc_amount,
    format_btc_amount_as_sats,
)


def test_str2bool():
    assert not str2bool(None)
    assert str2bool("true")
    assert str2bool("True")
    assert str2bool("tRuE")
    assert not str2bool("false")
    assert not str2bool("False")
    assert not str2bool("fAlsE")
    assert str2bool("On")
    assert str2bool("oN")
    assert str2bool("ON")
    assert not str2bool("Off")
    assert not str2bool("oFF")
    assert not str2bool("OFF")


def test_camelcase2snake_case():
    assert camelcase2snake_case("Service") == "service"
    assert camelcase2snake_case("DeviceType") == "device_type"


def test_snake_case2camelcase():
    assert snake_case2camelcase("service") == "Service"
    assert snake_case2camelcase("device_Type") == "DeviceType"


def test_format_btc_amount():
    btc_amount = 1.05678000
    assert (
        format_btc_amount(btc_amount)
        == """1.05<span class="thousand-digits-in-btc-amount">678</span>\
<span class="last-digits-in-btc-amount">000</span>"""
    )
    # All 0s stripped
    btc_amount = 1.05000000  # 1.05
    assert (
        format_btc_amount(btc_amount)
        == """1.05<span class="thousand-digits-in-btc-amount">\
<span class="unselectable transparent-text">0</span><span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span></span>\
<span class="last-digits-in-btc-amount">\
<span class="unselectable transparent-text">0</span><span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span></span>"""
    )
    # Maximum amount of 0s stripped
    btc_amount = 40.00000000  # 40.0
    assert (
        format_btc_amount(btc_amount)
        == """40.0<span class="unselectable transparent-text">0</span><span class="thousand-digits-in-btc-amount">\
<span class="unselectable transparent-text">0</span><span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span></span>\
<span class="last-digits-in-btc-amount">\
<span class="unselectable transparent-text">0</span><span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span></span>"""
    )
    # Last three 0s stripped
    btc_amount = 1.05678000  # 1.05678
    assert (
        format_btc_amount(btc_amount, minimum_digits_to_strip=3)
        == """1.05<span class="thousand-digits-in-btc-amount">678</span>\
<span class="last-digits-in-btc-amount">\
<span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span>\
<span class="unselectable transparent-text">0</span></span>"""
    )


def test_format_btc_amount_as_sats():
    btc_amount = 0.00560000
    assert (
        format_btc_amount_as_sats(btc_amount, enable_digit_formatting=True)
        == '<span class="thousand-digits-in-sats-amount">560,</span><span class="last-digits-in-sats-amount">000</span>'
    )
    assert format_btc_amount_as_sats(btc_amount) == "560,000"
    btc_amount = 0.10560000
    assert (
        format_btc_amount_as_sats(btc_amount, enable_digit_formatting=True)
        == '10,<span class="thousand-digits-in-sats-amount">560,</span><span class="last-digits-in-sats-amount">000</span>'
    )
    assert format_btc_amount_as_sats(btc_amount) == "10,560,000"
    btc_amount = 1.0
    assert (
        format_btc_amount_as_sats(btc_amount, enable_digit_formatting=True)
        == '100,<span class="thousand-digits-in-sats-amount">000,</span><span class="last-digits-in-sats-amount">000</span>'
    )
    assert format_btc_amount_as_sats(btc_amount) == "100,000,000"
    btc_amount = 1.56000000
    assert (
        format_btc_amount_as_sats(btc_amount, enable_digit_formatting=True)
        == '156,<span class="thousand-digits-in-sats-amount">000,</span><span class="last-digits-in-sats-amount">000</span>'
    )
    assert format_btc_amount_as_sats(btc_amount) == "156,000,000"
