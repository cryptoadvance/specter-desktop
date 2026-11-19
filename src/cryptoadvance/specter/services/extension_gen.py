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

from cryptoadvance.specter.util.version import VersionChecker

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
        devicename,
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
        self.devicename = devicename
        self.author = author
        self.author_email = email
        vc = VersionChecker()
        version = vc._get_current_version()
        if version == "custom":
            version = vc._get_latest_version_from_github()
        self.version = version  # relevant if tmpl-sources specify a dependency (requirements.txt) #ToDo improve
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
        self.jinja_env.filters["snakecase"] = camelcase2snake_case
        self.env = Environment(loader=loader, trim_blocks=True)
        self.env.filters["camelcase"] = snake_case2camelcase
        self.env.filters["snakecase"] = camelcase2snake_case
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
        self.render("README.md", version=self.version)
        self.render("requirements.txt", version=self.version)
        self.render(".gitignore")
        self.render(f"pytest.ini")
        package_path = f"src/dummyorg/specterext/dummy"
        self.render(f"{package_path}/service.py")
        self.render(f"{package_path}/controller.py")
        self.render(f"{package_path}/config.py")
        self.render(f"{package_path}/app_config.py")
        self.render(f"{package_path}/__init__.py")
        self.render(f"{package_path}/__main__.py")
        self.render(f"{package_path}/templates/dummy/index.jinja")
        if self.devicename:
            self.render(f"{package_path}/devices/devicename.py")
            self.render(f"{package_path}/devices/__init__.py")
            self.create_binary_file(f"{package_path}/static/dummy/img/device_icon.svg")
        if not self.isolated_client:
            self.render(f"{package_path}/static/dummy/css/styles.css")
            self.create_binary_file(f"{package_path}/static/dummy/img/ghost.png")
            self.create_binary_file(f"{package_path}/static/dummy/img/logo.jpeg")
            self.render(f"{package_path}/templates/dummy/base.jinja")
            self.render(f"{package_path}/templates/dummy/transactions.jinja")
            self.render(f"{package_path}/templates/dummy/settings.jinja")
            self.render(f"{package_path}/templates/dummy/components/dummy_menu.jinja")
            self.render(f"{package_path}/templates/dummy/components/dummy_tab.jinja")

        self.render(f"tests/conftest.py", env=self.sd_env)
        self.render(f"tests/conftest_visibility.py", env=self.sd_env)
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
            url = self.env.loader.url_for_template(sourcepath)
            # fetch() retries transient CDN errors and raises TemplateNotFound
            # instead of writing an error page into the binary file.
            try:
                r = self.env.loader.fetch(url)
            except TemplateNotFound as e:
                if getattr(e, "status_code", None) == 404:
                    # Some assets (e.g. the device icon) simply don't exist in
                    # the upstream dummy extension. Skipping them is better
                    # than writing an HTML error page into a binary file.
                    logger.warning(
                        f"Asset {sourcepath} is not available at {url}, skipping"
                    )
                    return
                raise
            targetpath.write_bytes(r.content)
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

    def render(self, template, env=None, filename=None, **kargv):
        # The template path is the same that we want to store on disk
        file_name = Path(
            template.replace("dummyorg", self.org)
            .replace("dummy", self.id)
            .replace(
                "devicename",
                camelcase2snake_case(self.devicename if self.devicename else ""),
            )
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

    # GitHub's raw CDN answers 429 when it rate-limits anonymous traffic and
    # occasionally 5xx/501 while it is degraded. A single such answer used to
    # abort `ext gen` (and with it the extension-smoketest, see #2738), so all
    # of these are retried with exponential backoff.
    transient_statuses = frozenset({429, 500, 501, 502, 503, 504})
    max_attempts = 5
    timeout = 30
    backoff_base = 1
    max_backoff = 30

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

    def retry_delay(self, attempt, response=None):
        """seconds to wait before the next attempt (honours Retry-After)"""
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.strip().isdigit():
                return min(float(retry_after.strip()), self.max_backoff)
        return min(self.backoff_base * 2**attempt, self.max_backoff)

    def fetch(self, url):
        """GET url, retrying transient failures. Returns the requests.Response
        of the successful attempt and raises TemplateNotFound otherwise."""
        problem = "no attempt was made"
        status_code = None
        for attempt in range(self.max_attempts):
            response = None
            try:
                response = requests.get(url, timeout=self.timeout)
            except requests.RequestException as e:
                problem = f"{type(e).__name__}: {e}"
            else:
                if response.status_code == 200:
                    return response
                problem = f"HTTP {response.status_code}"
                status_code = response.status_code
                if response.status_code not in self.transient_statuses:
                    raise self._not_found(url, problem, status_code)
            if attempt < self.max_attempts - 1:
                delay = self.retry_delay(attempt, response)
                logger.warning(
                    f"{url} failed ({problem}), attempt {attempt + 1}/"
                    f"{self.max_attempts}, retrying in {delay}s"
                )
                time.sleep(delay)
        raise self._not_found(
            url, f"{problem} after {self.max_attempts} attempts", status_code
        )

    @staticmethod
    def _not_found(url, problem, status_code):
        """TemplateNotFound carrying the HTTP status code (if there was one) so
        callers can tell a permanently missing template from a CDN outage."""
        error = TemplateNotFound(f"{url} results in {problem}")
        error.status_code = status_code
        return error

    def get_source(self, environment, template):
        url = self.url_for_template(template)
        return self.fetch(url).text, url, None
