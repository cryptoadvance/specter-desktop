from unittest.mock import MagicMock
import pytest
from cryptoadvance.specter.specter_error import SpecterError
from cryptoadvance.specter.util.version import _parse_version, compare
from cryptoadvance.specter.util.version import VersionChecker
from mock import Mock, patch, PropertyMock


@patch(
    "cryptoadvance.specter.util.version.VersionChecker._get_latest_version_from_github"
)
@patch(
    "cryptoadvance.specter.util.version.VersionChecker.installation_type",
    new_callable=PropertyMock,
)
@patch("cryptoadvance.specter.util.version.VersionChecker._get_current_version")
def test_VersionChecker(
    mock_get_current_version,
    mock_installation_type,
    mock_latest,
    caplog,
):
    mock_latest.return_value = "v9.10.21"
    mock_installation_type.return_value = "pip"
    mock_get_current_version.return_value = "1.2.3"

    # We're mocking cryptoadvance by another package because that package is installed but not cryptoadvance.specter
    vc = VersionChecker(name="joke")

    assert vc.installation_type == "pip"
    asssert = vc._get_current_version() == "1.2.3"
    assert vc.current == "1.2.3"

    assert vc._get_binary_version() == (
        "1.2.3",
        "v9.10.21",
    )

    # Same tests with "app"
    mock_installation_type.return_value = "app"
    vc = VersionChecker(name="joke")
    assert vc.installation_type == "app"
    assert vc._get_current_version() == "1.2.3"
    assert vc.current == "1.2.3"

    assert vc._get_binary_version() == (
        "1.2.3",
        "v9.10.21",
    )


@patch("cryptoadvance.specter.util.version.requests")
@patch(
    "cryptoadvance.specter.util.version.VersionChecker.installation_type",
    new_callable=PropertyMock,
)
def test_VersionChecker_get_binary_version(
    mock_installation_type,
    mock_requests_session: MagicMock,
    caplog,
):
    mock_requests_session.Session().get().json.return_value = {
        "releases": {
            "1.9.0rc5": None,
            "0.10.0": None,
            "1.14.0": None,
            "1.14.1": None,
            "1.2.0": None,
        }
    }
    vc = VersionChecker(name="joke")
    assert compare(vc._get_latest_version_from_github(), "1.14.0") == -1


def test_parse_version():
    assert _parse_version("v1.5.9") == {
        "major": 1,
        "minor": 5,
        "patch": 9,
        "postfix": "",
    }
    assert _parse_version("1.5.9") == {
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
    assert _parse_version("3.4.5rc12") == {
        "major": 3,
        "minor": 4,
        "patch": 5,
        "postfix": "pre12",
    }
    assert _parse_version("2.0.0rc20.dev0+ga99ede2a.d20230215") == {
        "major": 2,
        "minor": 0,
        "patch": 0,
        "postfix": "pre20",
    }
    assert _parse_version("2.0.0.dev1897+gcccf4a9") == {
        "major": 2,
        "minor": 0,
        "patch": 0,
        "postfix": "",
    }


def test_compare():
    assert compare("v1.2.3", "v2.2.3") == 1
    assert compare("v2.2.3", "v1.2.3") == -1

    assert compare("v2.1.3", "v2.2.3") == 1
    assert compare("v2.2.3", "v1.1.3") == -1

    assert compare("v2.2.3", "v2.2.5") == 1
    assert compare("v2.2.5", "v2.2.2") == -1

    assert compare("v2.2.5", "v2.2.5") == 0
    assert compare("v2.2.5-pre5", "v2.2.5-pre5") == 0

    assert compare("v2.2.3-pre2", "v1.2.3") == -1
    assert compare("v2.2.3", "v1.2.3-pre2") == -1
    assert compare("v2.2.5-pre6", "v2.2.5-pre5") == -1
    assert compare("v2.2.5-pre5", "v2.2.5-pre6") == 1
