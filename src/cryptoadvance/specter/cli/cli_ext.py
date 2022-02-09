import logging
import os
import signal
import sys
import time
from os import path
import shutil
from pathlib import Path
from socket import gethostname
from urllib.parse import urlparse

import click
import requests

from ..server import create_app, init_app
from ..specter_error import SpecterError
from ..util.common import snake_case2camelcase
from ..util.shell import run_shell
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)

dummy_ext_url = "https://raw.githubusercontent.com/cryptoadvance/spext-dummy/master"


@click.group()
def ext():
    pass


def wget_if_not_exist(url, fname):
    if not Path(fname).is_file():
        r = requests.get(url)
        open(fname, "wb").write(r.content)


def replace(fname, search, replace):
    with open(fname, "r") as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace(search, replace)

    # Write the file out again
    with open(fname, "w") as file:
        file.write(filedata)


@ext.command()
def create():
    """Will create a new extension in a more or less empty directory.
    It will ask you for the ID of the extension and will then create the necessary files.
    """
    dir = click.prompt(
        "What should be the ID of your extension (lowercase only)", type=str
    )
    # iggyback = click.prompt("Should this get a Piggyback-Extension? ",type=bool)
    wget_if_not_exist(f"{dummy_ext_url}/requirements.txt", "requirements.txt")

    Path(f"{dir}/templates/{dir}/components").mkdir(parents=True, exist_ok=True)
    Path(f"{dir}/static/{dir}").mkdir(parents=True, exist_ok=True)

    wget_if_not_exist(f"{dummy_ext_url}/dummy/service.py", f"./{dir}/service.py")
    replace(f"./{dir}/service.py", "dummy", dir)
    replace(f"./{dir}/service.py", "Dummy", snake_case2camelcase(dir))
    wget_if_not_exist(f"{dummy_ext_url}/dummy/controller.py", f"./{dir}/controller.py")
    replace(f"./{dir}/controller.py", "dummy", dir)
    replace(f"./{dir}/controller.py", "Dummy", snake_case2camelcase(dir))
    wget_if_not_exist(f"{dummy_ext_url}/dummy/__init__.py", f"./{dir}/__init__.py")
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/templates/dummy/index.jinja",
        f"{dir}/templates/{dir}/index.jinja",
    )
    replace(f"{dir}/templates/{dir}/index.jinja", "dummy", dir)
    replace(f"{dir}/templates/{dir}/index.jinja", "Dummy", snake_case2camelcase(dir))
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/templates/dummy/settings.jinja",
        f"{dir}/templates/{dir}/settings.jinja",
    )
    replace(f"{dir}/templates/{dir}/settings.jinja", "dummy", dir)
    replace(f"{dir}/templates/{dir}/settings.jinja", "Dummy", snake_case2camelcase(dir))
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/templates/dummy/components/dummy_menu.jinja",
        f"{dir}/templates/{dir}/components/{dir}_menu.jinja",
    )
    replace(f"{dir}/templates/{dir}/components/{dir}_menu.jinja", "dummy", dir)
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/templates/dummy/components/dummy_tab.jinja",
        f"{dir}/templates/{dir}/components/{dir}_tab.jinja",
    )
    replace(f"{dir}/templates/{dir}/components/{dir}_tab.jinja", "dummy", dir)

    Path("tests").mkdir(parents=True, exist_ok=True)
    wget_if_not_exist(
        f"https://raw.githubusercontent.com/cryptoadvance/specter-desktop/master/tests/conftest.py",
        f"./tests/conftest.py",
    )
    wget_if_not_exist(
        f"https://raw.githubusercontent.com/cryptoadvance/specter-desktop/master/tests/ghost_machine.py",
        f"./tests/ghost_machine.py",
    )

    # piggyback
    # replace(f"./{dir}/service.py", "piggyback = False", f"piggyback = {piggyback}")
    # if piggyback:
    #    replace(f"./{dir}/controller.py", "@login_required", "")

    print(
        f"""
        Congratulations, you've created a new extension
        Here is how to get it tor run on your Development Environment:

        virtualenv --python=python3 .env
        source .env/bin/activate
        pip3 install -r requirements.txt
        python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
        # point your browser to http://localhost:25441
        # "choose Services" --> {dir}
"""
    )


@ext.command()
def publish():
    """This will make your extension release-ready.
    It'll create the necessary files and will tell you how to create a package and
    publish it.
    """
    dir = click.prompt("What is the ID of your extension (lowercase only)", type=str)
    user_or_org = click.prompt(
        "What is the ID of your username or organisation? (lowercase only)", type=str
    )
    if Path(dir).is_dir():
        Path(f"src/{user_or_org}/spext").mkdir(parents=True, exist_ok=True)
        shutil.move(dir, f"src/{user_or_org}/spext")

    if not Path("setup.cfg").is_file():
        with open("setup.cfg", "w") as w:
            w.write(
                f"""\
[metadata]
name = {user_or_org}_{dir}
version = 0.0.1
author = Your Name
author_email = some_mail@mail.com
description = A small example package
long_description = file: README.md
long_description_content_type = text/markdown
url = https://github.com/{user_or_org}/spex-{dir}
project_urls =
    Bug Tracker = https://github.com/pypa/sampleproject/issues
classifiers =
    Programming Language :: Python :: 3
    License :: OSI Approved :: MIT License
    Operating System :: OS Independent

[options]
package_dir =
    = src
packages = find_namespace:
python_requires = >=3.6

[options.packages.find]
where = src
"""
            )

    if not Path("pyproject.toml").is_file():
        with open("pyproject.toml", "w") as w:
            w.write(
                f"""\
[build-system]
requires = [
    "cryptoadvance.specter==1.8.1"
]
build-backend = "setuptools.build_meta"
"""
            )

    if not Path("MANIFEST.in").is_file():
        with open("MANIFEST.in", "w") as w:
            w.write(
                f"""\
recursive-include src/{user_or_org}/spext/{dir}/templates *
recursive-include src/{user_or_org}/spext/{dir}/static *
recursive-include src/{user_or_org}/spext/{dir}/*/LC_MESSAGES *.mo
recursive-include src/{user_or_org}/spext/{dir}/translations/*/LC_MESSAGES *.po
include requirements.txt
"""
            )
    replace(f"./{dir}/service.py", "", snake_case2camelcase(dir))

    print(
        f"""
    You are now ready to build like this:

    python3 -m pip install --upgrade build
    python3 -m build
    
    You can then install your extension like:")
    
    pip3 install dist/{user_or_org}_{dir}-0.0.1-py3-none-any.whl

    In order to use your extension in production, please refer to the Readme.md in the
    https://github.com/cryptoadvance/spext-dummy#how-to-get-this-to-production
    
    To publish your package

    python3 -m pip install --upgrade twine
    python3 -m twine upload --repository testpypi dist/*

    
"""
    )
