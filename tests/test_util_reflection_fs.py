import os
from pathlib import Path
from cryptoadvance.specter.util.reflection_fs import (
    search_dirs_in_path,
    detect_extension_style_in_cwd,
)
from typing import List


def test_search_dir_in_cwd():
    print(os.getcwd())
    print(
        f"./tests/xtestdata_testextensions : {os.listdir('./tests/xtestdata_testextensions')}"
    )
    print(
        f"./tests/xtestdata_testextensions/ext_root_fully_qualified_1 : {os.listdir('./tests/xtestdata_testextensions/ext_root_fully_qualified_1')}"
    )
    print(
        f"./tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/ : {os.listdir('./tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/')}"
    )
    print(
        f"./tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/boatacccorp : {os.listdir('./tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/boatacccorp')}"
    )
    plist: List[Path] = search_dirs_in_path(Path("./tests/xtestdata_testextensions"))
    assert len(plist) == 3
    assert isinstance(plist[0], Path)
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/boatacccorp/specterext"
        )
        in plist
    )
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/accorp/specterext"
        )
        in plist
    )
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_2/src/boatacccorp/specterext"
        )
        in plist
    )

    plist = search_dirs_in_path(
        Path("./tests/xtestdata_testextensions"), return_without_extid=False
    )
    assert len(plist) == 3
    assert isinstance(plist[0], Path)
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/boatacccorp/specterext/tretboot"
        )
        in plist
    )
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_1/src/accorp/specterext/beiboot"
        )
        in plist
    )
    assert (
        Path(
            "tests/xtestdata_testextensions/ext_root_fully_qualified_2/src/boatacccorp/specterext/ruderboot"
        )
        in plist
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
