""" util stuff for searching the filesystem mainly used by the reflection.py """

import logging
import os
import sys
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def detect_extension_style_in_cwd(cwd=".") -> str:
    """don't override the cwd other than in testing!!
    if you do, you probably have to mess with sys.path at the same time
    """
    if Path(cwd, "src/cryptoadvance/specter").is_dir() or getattr(sys, "frozen", False):
        return "specter-desktop"
    if Path(cwd, "src").is_dir():
        return "publish-ready"
    else:
        # Ad-Hoc style is: ./extensionid/service.py but no .py-files in cwd
        # as this screws up the discovery
        for pth in Path(cwd).iterdir():
            if pth.suffix == ".py":
                raise Exception(
                    f"""
                You have an inconsistent project file-layout in folder
                {cwd}
                Either you:
                * Have a src-folder and you can have .py-files in your projectroot OR
                * you don't have a src-folder but ./extensionid/service.py (+ __init__.py)
                But not having a ./src-folder AND some .py-file in the project-root is not allowed.
                """
                )
        return "adhoc"


def search_dirs_in_path(path: Path, dirname="spext") -> List[Path]:
    """recursively walks the filesystem collecting directories which are called "spext"
    returns a list of PATH all ending with spext
    """
    plist: List[Path] = []
    print(path)
    if not path.is_dir():
        raise Exception(f"Search path does not exist: {path}")
    for root, dirs, _ in os.walk(path):
        for dirname in dirs:
            if dirname == "spext":
                plist.append(Path(root, dirname))
    return plist
