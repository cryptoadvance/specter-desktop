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
@click.option("--ext-id", "ext_id", default=None, help="Use a specific Extension ID")
@click.option(
    "--isolated-client/--no-isolated-client",
    default=None,
    help="Whether the extension should be isolated on the client",
)
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
def gen(org, ext_id, isolated_client, tmpl_fs_source, dryrun):
    # fmt: off
    """Will generate a new extension in a more or less empty directory.
    \b
    It'll ask you for the missing information if you don't pass the
    necessary details (see below).

    After creation, you can get the extension to run like this in your Development Environment:

    \b
        pip3 install -e .
        python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
        # point your browser to http://localhost:25441
        # "choose Services" --> YourService

    If you want to package it, you can build it like this:

    \b
        python3 -m pip install --upgrade build
        python3 -m build
        # install it like this:
        pip3 install dist/{org}_{ext_id}-0.0.1-py3-none-any.whl

    In order to use your extension in production, please refer to the Readme.md in the
    https://github.com/cryptoadvance/{ext_mark}-dummy#how-to-get-this-to-production

    To publish your package:

    \b
        python3 -m pip install --upgrade twine
        python3 -m twine upload --repository testpypi dist/*

    """
    # fmt: on
    if ext_id == None:
        print(
            """
            We need an ID and a prefix for your extension. It'll 
            reflect in the package-layout. The id should be a 
            short string.
            The prefix is usually something like your github-username 
            or github organisation-name. Both will be used to to 
            create the directory structure 
            ( like ./src/mycorpname/specterext/myextension )
            and it will be used to prepare the files in order to 
            publish this extension to pypi.

        """
        )
        ext_id = click.prompt(
            "What should be the ID of your extension (lowercase only)", type=str
        )
    if org == None:
        org = click.prompt(
            "what should be the prefix?",
            type=str,
        )
    if isolated_client == None:
        print(
            """
            Should the extension be working in isolated_client-mode?
            In that case it's won't share the session-cookie with 
            specter and the integration can only happen on server-side?
        """
        )
        isolated_client = click.prompt(
            "Should the extension work in isolated client mode (y/n)?",
            type=bool,
        )
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

    extgen = ExtGen(
        ".",
        org,
        ext_id,
        isolated_client,
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
        Congratulations, you've created a new extension

        Here is how to get it tor run on your Development Environment:
            pip3 install -e .
            python3 -m cryptoadvance.specter server --config DevelopmentConfig --debug
            # point your browser to http://localhost:25441
            # "choose Services" --> {ext_id}

        If you want to package it, you can build it like this:
            python3 -m pip install --upgrade build
            python3 -m build
            # install it like this:
            pip3 install dist/{org}_{ext_id}-0.0.1-py3-none-any.whl

        In order to use your extension in production, please refer to 
        the Readme.md in the dummy-extension-repo.
        https://github.com/cryptoadvance/{ext_mark}-dummy#how-to-get-this-to-production
    
        To publish your package

            python3 -m pip install --upgrade twine
            python3 -m twine upload --repository testpypi dist/*

        You can get all these information again via:
        python3 -m cryptoadvance.specter ext gen --help

"""
    )
