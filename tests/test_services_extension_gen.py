from cryptoadvance.specter.services.extension_gen import ExtGen, GithubUrlLoader
from jinja2 import FileSystemLoader
from mock import patch


def test_GithubUrlLoader():
    gh_url_loader: ExtGen = GithubUrlLoader()
    assert gh_url_loader.get_source(None, "/Readme.md")


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
