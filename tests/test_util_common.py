from cryptoadvance.specter.util.common import camelcase2snake_case, str2bool


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
