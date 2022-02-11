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
from ..util.reflection_fs import search_dirs_in_path

logger = logging.getLogger(__name__)

ext_mark = "specterext"
dummy_ext_url = (
    "https://raw.githubusercontent.com/cryptoadvance/specterext-dummy/master"
)


@click.group()
def ext():
    pass


def wget_if_not_exist(url, fname):
    if not Path(fname).is_file():
        r = requests.get(url)
        open(fname, "wb").write(r.content)
        print(f"    --> Created {fname}")


def create_if_not_exist(fname, content):
    if not Path(fname).is_file():
        with open(fname, "w") as w:
            w.write(content)
        print(f"    --> Created {fname}")


def replace(fname, search, replace):
    with open(fname, "r") as file:
        filedata = file.read()

    # Replace the target string
    filedata = filedata.replace(search, replace)

    # Write the file out again
    with open(fname, "w") as file:
        file.write(filedata)


@ext.command()
def gen():
    """Will generate a new extension in a more or less empty directory.
    It will ask you for the ID of the extension and the org/name and will
    then create the necessary files.
    """
    ext_id = click.prompt(
        "What should be the ID of your extension (lowercase only)", type=str
    )
    org = click.prompt(
        f"""
        what should be the prefix? This is usually something like your github-username or
        github organisation-name ?
        This will be used to create the directory structure ( ./src/mycorpname/specterext/${ext_id} )
        and later it will be used to prepare the files in order to publish this extension to pypi.
    """,
        type=str,
    )

    isolated_client = click.prompt(
        f"""
        Should the extension be working in isolated_client-mode? In that case it's won't share the
        session-cookie with specter and the integration can only happen on server-side?
    """,
        type=bool,
    )

    wget_if_not_exist(f"{dummy_ext_url}/requirements.txt", "requirements.txt")
    package_path = f"src/{org}/{ext_mark}/{ext_id}"
    Path(f"{package_path}/templates/{ext_id}/components").mkdir(
        parents=True, exist_ok=True
    )
    Path(f"{package_path}/static/{ext_id}").mkdir(parents=True, exist_ok=True)

    # Service
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/service.py", f"./{package_path}/service.py"
    )
    replace(f"./{package_path}/service.py", "dummy", ext_id)
    replace(f"./{package_path}/service.py", "Dummy", snake_case2camelcase(ext_id))
    replace(
        f"./{package_path}/service.py",
        f'blueprint_module = "{ext_id}.controller"',
        f'blueprint_module = "{org}.{ext_mark}.{ext_id}.controller"',
    )

    # Controller
    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/controller.py", f"./{package_path}/controller.py"
    )
    replace(f"./{package_path}/controller.py", "dummy", ext_id)
    replace(f"./{package_path}/controller.py", "Dummy", snake_case2camelcase(ext_id))
    if isolated_client:
        replace(f"{package_path}/controller.py", "@login_required", "")
        replace(f"{package_path}/controller.py", "@user_secret_decrypted_required", "")

    wget_if_not_exist(
        f"{dummy_ext_url}/dummy/__init__.py", f"./{package_path}/__init__.py"
    )

    # Templates
    if isolated_client:
        create_if_not_exist(
            f"{package_path}/templates/{ext_id}/index.jinja",
            f"<html> <body> Hello {ext_id} </body></html>",
        )
    else:
        wget_if_not_exist(
            f"{dummy_ext_url}/dummy/templates/dummy/index.jinja",
            f"{package_path}/templates/{ext_id}/index.jinja",
        )
        replace(f"{package_path}/templates/{ext_id}/index.jinja", "dummy", ext_id)
        replace(
            f"{package_path}/templates/{ext_id}/index.jinja",
            "Dummy",
            snake_case2camelcase(ext_id),
        )

        wget_if_not_exist(
            f"{dummy_ext_url}/dummy/templates/dummy/settings.jinja",
            f"{package_path}/templates/{ext_id}/settings.jinja",
        )
        replace(f"{package_path}/templates/{ext_id}/settings.jinja", "dummy", ext_id)
        replace(
            f"{package_path}/templates/{ext_id}/settings.jinja",
            "Dummy",
            snake_case2camelcase(ext_id),
        )
        wget_if_not_exist(
            f"{dummy_ext_url}/dummy/templates/dummy/components/dummy_menu.jinja",
            f"{package_path}/templates/{ext_id}/components/{ext_id}_menu.jinja",
        )
        replace(
            f"{package_path}/templates/{ext_id}/components/{ext_id}_menu.jinja",
            "dummy",
            ext_id,
        )
        wget_if_not_exist(
            f"{dummy_ext_url}/dummy/templates/dummy/components/dummy_tab.jinja",
            f"{package_path}/templates/{ext_id}/components/{ext_id}_tab.jinja",
        )
        replace(
            f"{package_path}/templates/{ext_id}/components/{ext_id}_tab.jinja",
            "dummy",
            ext_id,
        )

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
        # "choose Services" --> {ext_id}
"""
    )


@ext.command()
def preppub():
    """This will make your extension release-ready.
    It'll create the necessary files and will tell you how to create a package and
    publish it.
    """

    package_dirs = search_dirs_in_path("src", return_without_extid=False)
    if len(package_dirs) != 1:
        raise Exception(
            f"""
            no or more than one extension found:
            { package_dirs }
            Please create an Extension first or create the necessary files yourself
        """
        )
    ext_id = package_dirs[0].parts[-1]
    org = package_dirs[0].parts[-3]
    result = run_shell(["git", "config", "--get", "user.name"])
    if result["code"] == 0:
        author = result["out"].decode("ascii").strip()
    else:
        author = click.prompt("Please type in your Name: ", type=str)
    result = run_shell(["git", "config", "--get", "user.email"])
    if result["code"] == 0:
        email = result["out"].decode("ascii").strip()
    else:
        email = click.prompt("Please type in your E-Mail: ", type=str)
    print(
        f"""
        Your Extension ID and Organsiation would be:
            Extension ID: {ext_id}
            Organisation: {org}
        The recommended details of the python-package would be:
            name:   {org}_{ext_id}
            Author: {author}
            mail:   {email}
        The recommended Github-URL would be:
            https://github.com/{org}/{ext_mark}-{ext_id}
        However, you can also change these things afterwards.
    """
    )
    answer = click.prompt("Is this correct (y/n) ?", type=bool)

    create_if_not_exist(
        "setup.cfg",
        f"""\
[metadata]
name = {org}_{ext_id}
version = 0.0.1
author = {author}
author_email = {email}
description = A small example package
long_description = file: README.md
long_description_content_type = text/markdown
url = https://github.com/{org}/{ext_mark}-{ext_id}
project_urls =
    Bug Tracker = https://github.com/{org}/specterext-{ext_id}/issues
classifiers =
    Programming Language :: Python :: 3
    License :: OSI Approved :: MIT License
    Operating System :: OS Independent
    Framework :: specter :: Extension

[options]
package_dir =
    = src
packages = find_namespace:
python_requires = >=3.6

[options.packages.find]
where = src
""",
    )

    create_if_not_exist(
        "setup.py",
        f"""\
from setuptools import setup

if __name__ == "__main__":
    setup()
""",
    )

    create_if_not_exist(
        "pyproject.toml",
        f"""\
[build-system]
requires = [
    "cryptoadvance.specter==1.8.1"
]
build-backend = "setuptools.build_meta"
""",
    )

    create_if_not_exist(
        "MANIFEST.in",
        f"""\
recursive-include src/{org}/{ext_mark}/{dir}/templates *
recursive-include src/{org}/{ext_mark}/{ext_id}/static *
recursive-include src/{org}/{ext_mark}/{ext_id}/*/LC_MESSAGES *.mo
recursive-include src/{org}/{ext_mark}/{ext_id}/translations/*/LC_MESSAGES *.po
include requirements.txt
""",
    )

    print(
        f"""
    You are now ready to build like this:

    python3 -m pip install --upgrade build
    python3 -m build
    
    You can then install your extension like:")
    
    pip3 install dist/{org}_{ext_id}-0.0.1-py3-none-any.whl

    In order to use your extension in production, please refer to the Readme.md in the
    https://github.com/cryptoadvance/{ext_mark}-dummy#how-to-get-this-to-production
    
    To publish your package

    python3 -m pip install --upgrade twine
    python3 -m twine upload --repository testpypi dist/*

    
"""
    )
