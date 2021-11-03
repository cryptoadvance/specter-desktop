import pytest
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.version import _parse_version, compare


def test_parse_version():
    assert _parse_version("v1.5.9") == {
        "major": 1,
        "minor": 5,
        "patch": 9,
        "postfix": "",
    }
    assert _parse_version("v3.4.5-pre12") == {
        "major": 3,
        "minor": 4,
        "patch": 5,
        "postfix": "pre12",
    }
    with pytest.raises(SpecterError):
        _parse_version("3.4.5-pre12")
    with pytest.raises(SpecterError):
        _parse_version("3.4.5.6-pre12")


def test_compare():
    assert compare("v1.2.3", "v2.2.3") == 1
    assert compare("v2.2.3", "v1.2.3") == -1

    assert compare("v2.1.3", "v2.2.3") == 1
    assert compare("v2.2.3", "v1.1.3") == -1

    assert compare("v2.2.3", "v2.2.5") == 1
    assert compare("v2.2.5", "v2.2.2") == -1

    assert compare("v2.2.5", "v2.2.5") == 0

    with pytest.raises(SpecterError):
        assert compare("v2.2.3-pre2", "v1.2.3") == -1
