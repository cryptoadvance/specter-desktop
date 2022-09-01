from cryptoadvance.specter.util.common import (
    camelcase2snake_case,
    snake_case2camelcase,
    str2bool,
    replace_substring,
    btcamount_formatted,
    satamount_formatted,
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


def test_replace_substring():
    text = "satoshi"
    assert replace_substring(text, 2, 4, "shim") == "sashimi"
    assert (
        replace_substring(text, 3, 3, " ") == "sat\u0020i"
    )  # In Python " " has the unicode code 32 (\u0020)
    assert replace_substring(text, 3, 3, "\u2007") == "sat\u2007i"


def test_btcamount_formatted():
    btc_amount = 1.05060000
    assert btcamount_formatted(btc_amount) == "1.05\u2008060\u2008000"
    assert "1.05\u2008060\u2008000" != "1.05 060 000"
    assert "1.05\u0020060\u0020000" == "1.05 060 000"
    assert (
        btcamount_formatted(btc_amount, minimum_digits_to_strip=3)
        == "1.05\u200806\u2007\u2008\u2007\u2007\u2007"
    )  # 1.0506
    btc_amount = 1.00000000
    assert (
        btcamount_formatted(btc_amount)
        == "1.0\u2007\u2008\u2007\u2007\u2007\u2008\u2007\u2007\u2007"
    )  # 1.0
    assert (
        btcamount_formatted(btc_amount, maximum_digits_to_strip=8)
        == "1\u2008\u2007\u2007\u2008\u2007\u2007\u2007\u2008\u2007\u2007\u2007"
    )  # 1
    btc_amount = 0.00050000
    assert btcamount_formatted(btc_amount, minimum_digits_to_strip=3) == None


def test_satamount_formatted():
    btc_amount = 0.00560000
    assert satamount_formatted(btc_amount) == "560,000"
    btc_amount = 0.10560000
    assert satamount_formatted(btc_amount) == "10,560,000"
    btc_amount = 1.0
    assert satamount_formatted(btc_amount) == "100,000,000"
    btc_amount = 1.56000000
    assert satamount_formatted(btc_amount) == "156,000,000"
