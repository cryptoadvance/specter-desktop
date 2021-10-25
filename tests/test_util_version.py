import pytest
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.version import _parse_version, compare
from cryptoadvance.specter.util.version import VersionChecker
from mock import Mock, patch


@patch("cryptoadvance.specter.util.version.importlib_metadata.version")
@patch("cryptoadvance.specter.util.version.VersionChecker._version_txt_content")
def test_VersionChecker(VersionChecker_version_txt_content, imp_lib_mock, caplog):
    imp_lib_mock.return_value = "1.2.3"
    VersionChecker_version_txt_content.return_value = "2.3.4"

    # We're mocking cryptoadvance by another package because that package is installed but not cryptoadvance.specter
    vc = VersionChecker(name="joke")

    assert vc.installation_type == "pip"
    asssert = vc._get_current_version() == "1.2.3"
    asssert = vc._get_current_version() == "1.2.3"
    assert vc.current == "1.2.3"

    assert vc._get_binary_version() == (
        "1.2.3",
        "v1.7.0",
    )  # will break with a new release
    # assert vc._get_pip_version() == ("1.2.3", "v5.3.0")    # Might break anytime
    # assert vc.info == "h"


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
