""" We assume that this script is running on a gitlab-runner and therefore has some variables set.
    Specifically:
    CI_PROJECT_ROOT_NAMESPACE=k9ert
    CI_COMMIT_TAG=v0.9.6-pre2


"""

import logging
import os
import sys
from pathlib import Path
import requests

import argparse
import collections
import getpass
import json
import logging
import os
import re
import subprocess
import sys
from typing import (
    cast,
    Any,
    Callable,
    List,
    Optional,
)  # noqa: F401  # pylint: disable=unused-import

try:
    # Allow an import of this module without `requests` and `yacl` being installed for meta data queries
    # (e.g. version information)
    import requests
    from yacl import setup_colored_stderr_logging
except ImportError:
    pass


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


github_api_root_url = f"https://api.github.com"

github_username = "gitlab_upload_release_binaries"


def main():
    if sys.argv[1] != "upload":
        # Maybe something more fancy in the future:
        logger.error("Command {sys.argv[1]} not found! Only 'upload' right now")
        exit(2)

    artifact = sys.argv[2]
    if not Path(artifact).exists():
        logger.error(f"local artifact {artifact} does not exist.")
        exit(2)
    if not "CI_PROJECT_ROOT_NAMESPACE" in os.environ:
        logger.error("CI_PROJECT_ROOT_NAMESPACE not found")
        exit(2)
    else:
        project = f"{os.environ['CI_PROJECT_ROOT_NAMESPACE']}/specter-desktop"
    if not "CI_COMMIT_TAG" in os.environ:
        logger.error("CI_COMMIT_TAG not found")
        exit(2)
    else:
        tag = os.environ["CI_COMMIT_TAG"]
    if len(sys.argv) != 3:
        logger.error("argument artifact not found.")
    if artifact_exists(project, tag, Path(artifact).name):
        logger.info("Github artifact existing. Skipping upload.")
        exit(0)
    else:
        logger.info(f"Github artifact {artifact} does not exist. Let's upload!")

    if not "GH_BIN_UPLOAD_PW" in os.environ:
        logger.error("GH_BIN_UPLOAD_PW not found.")
    else:
        password = os.environ["GH_BIN_UPLOAD_PW"]

    publish_release_from_tag(
        project,
        tag,
        [artifact],
        github_username,
        password,
    )


def artifact_exists(project, tag, artifact):
    artifact_url = f"https://github.com/{project}/releases/download/{tag}/{artifact}"
    logger.debug(f"checking for artifact url {artifact_url}")
    r = requests.head(artifact_url)
    if r.status_code != 302:
        return False
    else:
        return True


__copyright__ = "Copyright © 2019 Forschungszentrum Jülich GmbH. All rights reserved."
__license__ = "MIT"
__version_info__ = (0, 1, 5)
__version__ = ".".join(map(str, __version_info__))


DEFAULT_GITHUB_ROOT = "github.com"


class MissingDependencyError(Exception):
    pass


class FileCommandError(Exception):
    pass


class InvalidFileCommandOutputError(Exception):
    pass


class NoTagsAvailableError(Exception):
    pass


class HTTPError(Exception):
    pass


class JSONError(Exception):
    pass


class InvalidUploadUrlError(Exception):
    pass


class InvalidServerNameError(Exception):
    pass


class MissingProjectError(Exception):
    pass


class MissingTagError(Exception):
    pass


class CredentialsReadError(Exception):
    pass


class AttributeDict(dict):  # type: ignore
    def __getattr__(self, attr: str) -> Any:
        return self[attr]

    def __setattr__(self, attr: str, value: Any) -> None:
        self[attr] = value


Release = collections.namedtuple("Release", ["id", "asset_upload_url"])
Asset = collections.namedtuple("Asset", ["id", "name"])


def setup_stderr_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    setup_colored_stderr_logging(format_string="[%(levelname)s] %(message)s")


def get_mimetype(filepath: str) -> str:
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            'The file "{}" does not exist or is not a regular file.'.format(filepath)
        )
    if not os.access(filepath, os.R_OK):
        raise PermissionError('The file "{}" is not readable.'.format(filepath))

    if os.name == "nt":
        try:
            import mimetypes

            mime_type = mimetypes.types_map[f".{filepath.split('.')[-1]}"]
        except ModuleNotFoundError:
            raise Exception(
                "mimetypes module not found. Do something like pip install mimetypes"
            )
    else:
        try:
            file_command_output = subprocess.check_output(
                ["file", "--mime", filepath], universal_newlines=True
            )  # type: str
            mime_type = file_command_output.split()[1][:-1]
        except subprocess.CalledProcessError as e:
            raise FileCommandError(
                "The `file` command returned with exit code {:d}".format(e.returncode)
            )
        except IndexError:
            raise InvalidFileCommandOutputError(
                'The file command output "{}" could not be parsed.'.format(
                    file_command_output
                )
            )
    return mime_type


def strip_asset_upload_url(asset_upload_url_with_get_params: str) -> str:
    match_obj = re.match(r"([^{]+)(?:\{.*\})?", asset_upload_url_with_get_params)
    if not match_obj:
        raise InvalidUploadUrlError(
            'The upload url "{}" is not in the expected format.'.format(
                asset_upload_url_with_get_params
            )
        )
    asset_upload_url = match_obj.group(1)  # type: str
    return asset_upload_url


class GithubConnection:
    def __init__(self, project):
        self.github_api_root_url = github_api_root_url
        self.project = project
        self.username = github_username
        self.password = os.environ["GH_BIN_UPLOAD_PW"]

    def fetch_existing_release(self, tag) -> Optional[Release]:
        try:
            release_query_url = "{}/repos/{}/releases/tags/{}".format(
                self.github_api_root_url, self.project, tag
            )
            response = requests.get(
                release_query_url,
                auth=(self.username, self.password),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            logger.info(
                'Fetched the existing release "%s" in the GitHub repository "%s"',
                tag,
                self.project,
            )
            response_json = response.json()
            asset_upload_url_with_get_params = response_json["upload_url"]
            asset_upload_url = strip_asset_upload_url(asset_upload_url_with_get_params)
            release = Release(response_json["id"], asset_upload_url)
            return release
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise HTTPError(
                'Could not fetch the release "{}" due to a severe HTTP error.'.format(
                    tag
                )
            )

    def list_assets(self, release: Release) -> List[Asset]:
        try:
            asset_list_url = "{}/repos/{}/releases/{}/assets".format(
                self.github_api_root_url, self.project, release.id
            )
            response = requests.get(asset_list_url, auth=(self.username, self.password))
            response.raise_for_status()
            assets = [
                Asset(asset_dict["id"], asset_dict["name"])
                for asset_dict in response.json()
            ]
            return assets
        except requests.HTTPError:
            raise HTTPError(
                'Could not get a list of assets for project "{}".'.format(self.project)
            )
        except json.decoder.JSONDecodeError:
            raise JSONError("Got an invalid json string.")
        except KeyError as e:
            raise JSONError(
                'Got an unexpected json object missing the key "{}".'.format(e.args[0])
            )

    def download_artifact(self, tag, artifact, target_dir="."):
        artifact_url = (
            f"https://github.com/{self.project}/releases/download/{tag}/{artifact}"
        )
        response = requests.get(artifact_url)

        # If the HTTP GET request can be served
        if response.status_code == 200:

            # Write the file contents in the response to a file specified by local_file_path
            with open(os.path.join(target_dir, artifact), "wb") as local_file:
                for chunk in response.iter_content(chunk_size=128):
                    local_file.write(chunk)
        else:
            raise Exception(
                f"Status-code {response.status_code} for url {artifact_url}"
            )


def publish_release_from_tag(
    project: str,
    tag: Optional[str],
    asset_filepaths: List[str],
    username: str,
    password: str,
    dry_run: bool = False,
) -> None:
    if "requests" not in sys.modules:
        raise MissingDependencyError(
            'The "requests" package is missing. Please install and run again.'
        )

    def fetch_latest_tag() -> str:
        try:
            tags_url = "{}/repos/{}/tags".format(github_api_root_url, project)
            response = requests.get(
                tags_url,
                auth=(username, password),
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            tags = response.json()
            if not tags:
                raise NoTagsAvailableError(
                    'The given repository "{}" has no tags yet.'.format(project)
                )
            latest_tag = tags[0]["name"]  # type: str
            logger.info(
                'Fetched the latest tag "%s" from the GitHub repository "%s"',
                latest_tag,
                project,
            )
            return latest_tag
        except requests.HTTPError:
            raise HTTPError(
                'Could not query the latest tag of the repository "{}" due to a http error.'.format(
                    project
                )
            )
        except (json.decoder.JSONDecodeError, IndexError):
            raise JSONError("Got an invalid json string.")
        except KeyError as e:
            raise JSONError(
                'Got an unexpected json object missing the key "{}".'.format(e.args[0])
            )

    def publish_release(tag: str) -> Release:
        def fetch_existing_release() -> Optional[Release]:
            try:
                release_query_url = "{}/repos/{}/releases/tags/{}".format(
                    github_api_root_url, project, tag
                )
                response = requests.get(
                    release_query_url,
                    auth=(username, password),
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                logger.info(
                    'Fetched the existing release "%s" in the GitHub repository "%s"',
                    tag,
                    project,
                )
                response_json = response.json()
                asset_upload_url_with_get_params = response_json["upload_url"]
                asset_upload_url = strip_asset_upload_url(
                    asset_upload_url_with_get_params
                )
                release = Release(response_json["id"], asset_upload_url)
                return release
            except requests.HTTPError as e:
                if e.response.status_code == 404:
                    return None
                raise HTTPError(
                    'Could not fetch the release "{}" due to a severe HTTP error.'.format(
                        tag
                    )
                )

        def create_release() -> Release:
            try:
                release_creation_url = "{}/repos/{}/releases".format(
                    github_api_root_url, project
                )
                response = requests.post(
                    release_creation_url,
                    auth=(username, password),
                    json={
                        "tag_name": tag,
                        "name": tag,
                        "body": "",
                        "draft": False,
                        "prerelease": False,
                    },
                )
                response.raise_for_status()
                logger.info(
                    'Created the release "%s" in the GitHub repository "%s"',
                    tag,
                    project,
                )
                response_json = response.json()
                asset_upload_url_with_get_params = response_json["upload_url"]
                asset_upload_url = strip_asset_upload_url(
                    asset_upload_url_with_get_params
                )
                release = Release(response_json["id"], asset_upload_url)
                return release
            except requests.HTTPError:
                raise HTTPError('Could not create the release "{}".'.format(tag))
            except json.decoder.JSONDecodeError:
                raise JSONError("Got an invalid json string.")
            except KeyError as e:
                raise JSONError(
                    'Got an unexpected json object missing the key "{}".'.format(
                        e.args[0]
                    )
                )

        release = fetch_existing_release()
        if release is None:
            release = create_release()
        return release

    def list_assets(release: Release) -> List[Asset]:
        try:
            asset_list_url = "{}/repos/{}/releases/{}/assets".format(
                github_api_root_url, project, release.id
            )
            response = requests.get(asset_list_url, auth=(username, password))
            response.raise_for_status()
            assets = [
                Asset(asset_dict["id"], asset_dict["name"])
                for asset_dict in response.json()
            ]
            return assets
        except requests.HTTPError:
            raise HTTPError(
                'Could not get a list of assets for project "{}".'.format(project)
            )
        except json.decoder.JSONDecodeError:
            raise JSONError("Got an invalid json string.")
        except KeyError as e:
            raise JSONError(
                'Got an unexpected json object missing the key "{}".'.format(e.args[0])
            )

    def delete_asset(asset: Asset) -> None:
        try:
            asset_delete_url = "{}/repos/{}/releases/assets/{}".format(
                github_api_root_url, project, asset.id
            )
            response = requests.delete(asset_delete_url, auth=(username, password))
            response.raise_for_status()
            logger.info(
                'Deleted the asset "%s" attached to release "%s" of the GitHub repository "%s"',
                asset.name,
                tag,
                project,
            )
        except requests.HTTPError:
            raise HTTPError(
                'Could not get a list of assets for project "{}".'.format(project)
            )
        except json.decoder.JSONDecodeError:
            raise JSONError("Got an invalid json string.")
        except KeyError as e:
            raise JSONError(
                'Got an unexpected json object missing the key "{}".'.format(e.args[0])
            )

    def upload_asset(release: Release, asset_filepath: str) -> None:
        asset_filename = os.path.basename(asset_filepath)
        try:
            asset_mimetype = get_mimetype(asset_filepath)
            with open(asset_filepath, "rb") as f:
                response = requests.post(
                    "{}?name={}".format(release.asset_upload_url, asset_filename),
                    auth=(username, password),
                    data=f,
                    headers={"Content-Type": asset_mimetype},
                )
            response.raise_for_status()
            logger.info(
                'Uploaded the asset "%s" attached to release "%s" of the GitHub repository "%s"',
                asset_filename,
                tag,
                project,
            )
        except requests.HTTPError:
            raise HTTPError('Could not upload the asset "{}".'.format(asset_filename))

    if tag is None:
        logger.info(
            'No tag given, fetching the latest tag from the GitHub repository "%s"',
            project,
        )
        tag = fetch_latest_tag()
    if dry_run:
        logger.info(
            'Would create the release "%s" in the GitHub repository "%s"', tag, project
        )
        assets = []  # type: List[Asset]
    else:
        release = publish_release(tag)
        assets = list_assets(release)
    for asset_filepath in asset_filepaths:
        asset_matches = [
            asset for asset in assets if asset.name == os.path.basename(asset_filepath)
        ]
        if dry_run:
            for asset_match in asset_matches:
                logger.info(
                    'Would delete the asset "%s" attached to release "%s" of the GitHub repository "%s"',
                    asset_match.name,
                    tag,
                    project,
                )
            logger.info(
                'Would upload the asset "%s" attached to release "%s" of the GitHub repository "%s"',
                os.path.basename(asset_filepath),
                tag,
                project,
            )
        else:
            for asset_match in asset_matches:
                delete_asset(asset_match)
            upload_asset(release, asset_filepath)


if __name__ == "__main__":
    main()
