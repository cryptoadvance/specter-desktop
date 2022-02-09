from pathlib import Path
from cryptoadvance.specter.util.reflection_fs import (
    search_dirs_in_path,
    detect_extension_style_in_cwd,
)
from typing import List


def test_search_dir_in_cwd():
    plist: List[Path] = search_dirs_in_path(Path("./tests/xtestdata_testextensions"))
    assert len(plist) == 2
    assert isinstance(plist[0], Path)
    assert str(plist[0]).startswith(
        "tests/xtestdata_testextensions/ext_root_fully_qualified_"
    )


def test_detect_extension_style_in_cwd():
    assert (
        detect_extension_style_in_cwd(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_1"
        )
        == "publish-ready"
    )  #
    assert (
        detect_extension_style_in_cwd(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_2"
        )
        == "publish-ready"
    )
    assert (
        detect_extension_style_in_cwd("tests/xtestdata_testextensions/ext_root_adhoc_1")
        == "adhoc"
    )
