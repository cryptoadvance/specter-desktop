import logging
import os
import shutil
import signal
import sys
import time
from os import path
from pathlib import Path
from socket import gethostname
from urllib.parse import urlparse

import click
import requests

from ..server import create_app, init_app
from ..services.extension_gen import ExtGen
from ..specter_error import SpecterError
from ..util.common import snake_case2camelcase
from ..util.reflection_fs import search_dirs_in_path
from ..util.shell import run_shell
from ..util.tor import start_hidden_service, stop_hidden_services

logger = logging.getLogger(__name__)

ext_mark = "specterext"
dummy_ext_url = (
    "https://raw.githubusercontent.com/cryptoadvance/specterext-dummy/master"
)


@click.group()
def ext():
    """Commands for the extension framework"""
    pass


@ext.command()
@click.option("--org", "org", default=None, help="Use a specific organsiation")
@click.option("--ext-id", "ext_id", default=None, help="Use a specific extension id")
@click.option(
    "--isolated-client/--no-isolated-client",
    default=None,
    help="Whether the extension should be isolated on the client",
)
@click.option("--devicename", "devicename", default=None, help="Implement a device")
@click.option(
    "--tmpl-fs-source",
    "tmpl_fs_source",
    help="Use a Filesystem source for the templates e.g. ~/src/specterext-dummy",
)
@click.option(
    "--dryrun/--no-dryrun",
    default=False,
    help="Output content on stdout instead of creating files",
)
def gen(org, ext_id, isolated_client, devicename, tmpl_fs_source, dryrun):
    # fmt: off
    """Will generate a new extension in a more or less empty directory.
    \b
    It'll ask you for the missing information if you don't pass the
    necessary details (see below).

    After creation, you can get the extension to run like this in your development environment:

    \b
        pip3 install -e .
        python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
        # Point your browser to http://localhost:25441
        # Click "Choose plugins" --> YourExtension

    If you want to package it, you can build it like this:

    \b
        python3 -m pip install --upgrade build
        python3 -m build
        # Install it like this:
        pip3 install dist/YourOrg_YourId-0.0.1-py3-none-any.whl

    If you want to bring your extension to production, please refer to the readme in the dummy-extension repo:
    https://github.com/cryptoadvance/specterext-dummy#how-to-get-this-to-production

    To publish your package:

    \b
        python3 -m pip install --upgrade twine
        python3 -m twine upload --repository testpypi dist/*

    """
    # fmt: on
    if ext_id == None:
        print(
            """
            We need an id and a prefix for your extension.
            The id should be a short string.
            The prefix is usually your GitHub username 
            or GitHub organisation name. 
            Both will be used to to create a directory structure like this:
            ./src/mycorpname/specterext/myextension
            They will also be used when publishing this extension to pypi.
        """
        )
        ext_id = click.prompt(
            "Enter the id of your extension (lowercase only):", type=str
        )
    if org == None:
        org = click.prompt(
            "Enter the prefix:",
            type=str,
        )
    if isolated_client == None:
        print(
            """
            Isolated client mode means that the extensions won't share the session cookie with 
            Specter Desktop and the integration only happens on the server side.
        """
        )
        isolated_client = click.prompt(
            "Should the extension work in isolated client mode (y/n)?",
            type=bool,
        )
    if devicename == None:
        print(
            """
            Do you plan to implement a Device?
        """
        )
        devicename = click.prompt(
            "Type the Name in CamelCase or [enter] if you're not interested in a Device.",
            type=str,
            default="",
        )
    elif devicename == "none":
        devicename = None
    if devicename == "":
        devicename = None

    result = run_shell(["git", "config", "--get", "user.name"])
    if result["code"] == 0:
        author = result["out"].decode("ascii").strip()
    else:
        author = click.prompt("Please type in your name: ", type=str)
    result = run_shell(["git", "config", "--get", "user.email"])
    if result["code"] == 0:
        email = result["out"].decode("ascii").strip()
    else:
        email = click.prompt("Please type in your email: ", type=str)

    extgen = ExtGen(
        ".",
        org,
        ext_id,
        isolated_client,
        devicename,
        author,
        email,
        dry_run=dryrun,
        tmpl_fs_source=tmpl_fs_source,
    )
    extgen.generate()
    # piggyback
    # replace(f"./{dir}/service.py", "piggyback = False", f"piggyback = {piggyback}")
    # if piggyback:
    #    replace(f"./{dir}/controller.py", "@login_required", "")

    print(
        f"""
        Congratulations, you've created a new extension!

        Here is how to get it to run in your development environment:
            pip3 install -e .
            python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
            # Point your browser to http://localhost:25441
            # Click "Choose plugins" --> {ext_id}

        If you want to package it, you can build it like this:
            python3 -m pip install --upgrade build
            python3 -m build
            # install it like this:
            pip3 install dist/{org}_{ext_id}-0.0.1-py3-none-any.whl

        If you want to bring your extension to production, please refer to the readme in the dummy-extension repo:
        https://github.com/cryptoadvance/specterext-dummy#how-to-get-this-to-production
    
        To publish your package

            python3 -m pip install --upgrade twine
            python3 -m twine upload --repository testpypi dist/*

        You can get all these information again via:
        python3 -m cryptoadvance.specter ext gen --help

"""
    )
