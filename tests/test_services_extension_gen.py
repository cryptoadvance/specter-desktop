from cryptoadvance.specter.services.extension_gen import ExtGen, GithubUrlLoader
from jinja2 import FileSystemLoader


def test_GithubUrlLoader():
    gh_url_loader: ExtGen = GithubUrlLoader()
    assert gh_url_loader.get_source(None, "/Readme.md")


def test_ExtGen(caplog):

    extgen = ExtGen(
        ".",
        "testorg",
        "testext",
        False,
        "Some Author",
        "some@mail",
        loader=FileSystemLoader("../specterext-dummy"),
        dry_run=True,
    )
    extgen.generate()
    assert False
