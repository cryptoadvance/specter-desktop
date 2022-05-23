import logging
import os
import shutil
import signal
import sys
import time
from datetime import datetime
from os import path
from os.path import exists, getmtime, join
from pathlib import Path
from socket import gethostname
from sre_constants import BRANCH
from urllib.parse import urlparse

import click
import requests
from jinja2 import BaseLoader, Environment, FileSystemLoader, TemplateNotFound

from ..server import create_app, init_app
from ..specter_error import SpecterError
from ..util.common import camelcase2snake_case, snake_case2camelcase
from ..util.reflection_fs import search_dirs_in_path
from ..util.shell import run_shell
from ..util.tor import start_hidden_service, stop_hidden_services

ext_mark = "specterext"
logger = logging.getLogger(__name__)


class ExtGen:
    def __init__(
        self,
        base_path,
        ext_org,
        ext_id,
        isolated_client,
        author,
        email,
        dry_run=False,
        branch="master",
        tmpl_fs_source=None,
    ):
        self.base_path = base_path
        self.org = ext_org
        self.id = ext_id
        self.isolated_client = isolated_client
        self.author = author
        self.author_email = email
        self.version = "1.8.1"  # relevant if tmpl-sources specify a dependency (requirements.txt) #ToDo improve
        self.branch = branch
        self.tmpl_fs_source = tmpl_fs_source

        self.dry_run = dry_run
        self.create_envs()

    def create_envs(self):
        if self.tmpl_fs_source == None:
            loader = GithubUrlLoader(branch=self.branch)
        else:
            loader = FileSystemLoader(self.tmpl_fs_source)
        self.jinja_env = Environment(
            loader=loader,
            trim_blocks=True,
            block_start_string="<<",
            block_end_string=">>",
            variable_start_string="<=",
            variable_end_string="=>",
            comment_start_string="<#",
            comment_end_string="#>",
        )
        self.jinja_env.filters["camelcase"] = snake_case2camelcase
        self.env = Environment(loader=loader, trim_blocks=True)
        self.env.filters["camelcase"] = snake_case2camelcase
        self.sd_env = Environment(
            loader=GithubUrlLoader(
                base_url="https://raw.githubusercontent.com/cryptoadvance/specter-desktop/",
                branch=self.branch,
            )
        )

    def env_for_template(self, template):
        """chooses the right env for the template"""
        if Path(template).name in ["conftest.py", "fix_ghost_machine.py"]:
            return self.sd_env
        if Path(template).suffix.endswith("jinja"):
            return self.jinja_env
        return self.env

    def generate(self):
        self.generate_basics()
        self.generate_preppub()

    def generate_basics(self):
        self.render("requirements.txt", version=self.version)
        self.render(".gitignore")
        package_path = f"src/dummyorg/specterext/dummy"
        self.render(f"{package_path}/service.py")
        self.render(f"{package_path}/controller.py")
        self.render(f"{package_path}/config.py")
        self.render(f"{package_path}/__init__.py")
        self.render(f"{package_path}/__main__.py")
        self.render(f"{package_path}/templates/dummy/index.jinja")
        if not self.isolated_client:
            self.render(f"{package_path}/static/dummy/css/styles.css")
            self.create_binary_file(f"{package_path}/static/dummy/img/ghost.png")
            self.create_binary_file(f"{package_path}/static/dummy/img/logo.jpeg")
            self.render(f"{package_path}/templates/dummy/base.jinja")
            self.render(f"{package_path}/templates/dummy/transactions.jinja")
            self.render(f"{package_path}/templates/dummy/settings.jinja")
            self.render(f"{package_path}/templates/dummy/components/dummy_menu.jinja")
            self.render(f"{package_path}/templates/dummy/components/dummy_tab.jinja")

        self.render(f"pytest.ini", env=self.sd_env)
        self.render(f"tests/conftest.py", env=self.sd_env)
        self.render(f"tests/fix_ghost_machine.py", env=self.sd_env)
        self.render(f"tests/fix_devices_and_wallets.py", env=self.sd_env)
        self.render(f"tests/fix_testnet.py", env=self.sd_env)
        self.render(f"tests/fix_keys_and_seeds.py", env=self.sd_env)

    def create_binary_file(self, sourcepath):
        """textfiles can all be rendered. Binaries must be wgettet or copied"""
        targetpath = Path(
            sourcepath.replace("dummyorg", self.org).replace("dummy", self.id)
        )
        if self.dry_run:
            print(f"-------------------------------------")
            print(" Creation of targetpath skipped because dryrun")
            print(f"-------------------------------------")
            return
        if targetpath.is_file():
            return
        targetpath.parents[0].mkdir(parents=True, exist_ok=True)
        if self.tmpl_fs_source != None:
            sourcepath = Path(self.tmpl_fs_source, sourcepath)
            shutil.copy(sourcepath, targetpath)
            print(f"    --> Created {targetpath} (copied)")
        else:
            r = requests.get(self.env.loader.url_for_template(sourcepath))
            open(targetpath, "wb").write(r.content)
            print(f"    --> Created {targetpath} (via Github)")

    def generate_preppub(self):
        self.render("pyproject.toml", version=self.version)
        self.render("setup.py")
        # Author and Email
        if not self.author:
            result = run_shell(["git", "config", "--get", "user.name"])
            if result["code"] == 0:
                author = result["out"].decode("ascii").strip()
            else:
                author = click.prompt("Please type in your Name: ", type=str)
        if not self.author_email:
            result = run_shell(["git", "config", "--get", "user.email"])
            if result["code"] == 0:
                email = result["out"].decode("ascii").strip()
            else:
                email = click.prompt("Please type in your E-Mail: ", type=str)
        self.render("setup.cfg")
        self.render("MANIFEST.in")

    def render(self, template, env=None, **kargv):
        # The template path is the same that we want to store on disk
        file_name = Path(
            template.replace("dummyorg", self.org).replace("dummy", self.id)
        )
        if env == None:
            env = self.env_for_template(template)
        template = env.get_template(template)

        if not self.dry_run:
            file_name.parents[0].mkdir(parents=True, exist_ok=True)
        rendered_text = template.render(ext=self, **kargv)
        if self.dry_run:
            print()
            print(
                f"File: {file_name} ({env.block_start_string} {env.block_end_string})"
            )
            # print(f"Url: ")
            print("-------------------------------------------------")
            print(rendered_text)
            print("-------------------------------------------------")
            print()
        else:
            fq_fname = Path(self.base_path, file_name)
            if not fq_fname.is_file():
                with open(fq_fname, "w") as file:
                    file.write(rendered_text)
                    print(f"    --> Created {fq_fname}")


class GithubUrlLoader(BaseLoader):
    """A Jinja2 TemplateLoader which is loading templates directly from github.
    If you don't specify it, it'll be https://github.com/cryptoadvance/specterext-dummy
    """

    dummy_base_url = "https://raw.githubusercontent.com/cryptoadvance/specterext-dummy"

    def __init__(self, base_url=None, branch=None):
        if base_url == None:
            base_url = self.dummy_base_url
        if branch == None:
            branch = "master"
        self.base_url = base_url + "/" + branch

    def url_for_template(self, template):
        if template[0] == "/":
            template = template[1:]
        url = self.base_url + "/" + template
        return url

    def get_source(self, environment, template):
        url = self.url_for_template(template)
        r = requests.get(url)
        if r.status_code != 200:
            raise TemplateNotFound(f"{url} results in {r.status_code}")
        source = r.text
        return source, url, None
