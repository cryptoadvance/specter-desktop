import pytest
import requests
from cryptoadvance.specter.services.extension_gen import ExtGen, GithubUrlLoader
from jinja2 import FileSystemLoader, TemplateNotFound
from mock import MagicMock, patch


def make_response(status_code, text="", headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.content = text.encode()
    response.headers = headers or {}
    return response


def test_GithubUrlLoader():
    gh_url_loader: ExtGen = GithubUrlLoader()
    assert gh_url_loader.get_source(None, "/Readme.md")


def test_GithubUrlLoader_retries_transient_statuses():
    # A single 501 from the raw CDN used to break `ext gen` (see #2738)
    gh_url_loader = GithubUrlLoader()
    responses = [
        make_response(501),
        make_response(502),
        make_response(200, "hello"),
    ]
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        side_effect=responses,
    ) as get, patch("cryptoadvance.specter.services.extension_gen.time.sleep") as sleep:
        source, url, _ = gh_url_loader.get_source(None, "src/dummyorg/__init__.py")
    assert source == "hello"
    assert get.call_count == 3
    assert sleep.call_count == 2


def test_GithubUrlLoader_retries_connection_errors():
    gh_url_loader = GithubUrlLoader()
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        side_effect=[requests.ConnectionError("boom"), make_response(200, "ok")],
    ) as get, patch("cryptoadvance.specter.services.extension_gen.time.sleep"):
        source, url, _ = gh_url_loader.get_source(None, "Readme.md")
    assert source == "ok"
    assert get.call_count == 2


def test_GithubUrlLoader_gives_up_after_max_attempts():
    gh_url_loader = GithubUrlLoader()
    gh_url_loader.max_attempts = 3
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        return_value=make_response(503),
    ) as get, patch("cryptoadvance.specter.services.extension_gen.time.sleep"):
        with pytest.raises(TemplateNotFound) as excinfo:
            gh_url_loader.get_source(None, "Readme.md")
    assert get.call_count == 3
    assert "503" in str(excinfo.value)
    assert "after 3 attempts" in str(excinfo.value)


def test_GithubUrlLoader_does_not_retry_permanent_errors():
    gh_url_loader = GithubUrlLoader()
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        return_value=make_response(404),
    ) as get, patch("cryptoadvance.specter.services.extension_gen.time.sleep") as sleep:
        with pytest.raises(TemplateNotFound) as excinfo:
            gh_url_loader.get_source(None, "Readme.md")
    assert get.call_count == 1
    assert sleep.call_count == 0
    assert "404" in str(excinfo.value)


def test_GithubUrlLoader_honours_retry_after():
    gh_url_loader = GithubUrlLoader()
    responses = [
        make_response(429, headers={"Retry-After": "7"}),
        make_response(200, "ok"),
    ]
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        side_effect=responses,
    ), patch("cryptoadvance.specter.services.extension_gen.time.sleep") as sleep:
        gh_url_loader.get_source(None, "Readme.md")
    sleep.assert_called_once_with(7.0)


def test_ExtGen_does_not_write_error_body_into_binary_file(tmp_path):
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        return_value=make_response(501, "<html>501 Not Implemented</html>"),
    ), patch("cryptoadvance.specter.services.extension_gen.time.sleep"):
        extgen = ExtGen(
            str(tmp_path),
            "testorg",
            "testext",
            False,
            "MyDevice",
            "Some Author",
            "some@mail",
            dry_run=False,
        )
        with pytest.raises(TemplateNotFound):
            extgen.create_binary_file(
                "src/dummyorg/specterext/dummy/static/dummy/img/ghost.png"
            )
    assert not (
        tmp_path / "src/testorg/specterext/testext/static/testext/img/ghost.png"
    ).exists()


def test_ExtGen_skips_binary_assets_missing_upstream(tmp_path):
    # device_icon.svg does not exist in specterext-dummy; writing the 404 page
    # into the .svg (the old behaviour) is worse than leaving it out.
    with patch(
        "cryptoadvance.specter.services.extension_gen.requests.get",
        return_value=make_response(404),
    ):
        extgen = ExtGen(
            str(tmp_path),
            "testorg",
            "testext",
            False,
            "MyDevice",
            "Some Author",
            "some@mail",
            dry_run=False,
        )
        extgen.create_binary_file(
            "src/dummyorg/specterext/dummy/static/dummy/img/device_icon.svg"
        )
    assert not (
        tmp_path / "src/testorg/specterext/testext/static/testext/img/device_icon.svg"
    ).exists()


def test_ExtGen(caplog):

    with patch("cryptoadvance.specter.services.extension_gen.GithubUrlLoader") as mock:
        extgen = ExtGen(
            ".",
            "testorg",
            "testext",
            False,
            False,
            "Some Author",
            "some@mail",
            # uncomment the below line to see a real generation
            # tmpl_fs_source="../specterext-dummy",
            dry_run=True,
        )
        extgen.generate()
