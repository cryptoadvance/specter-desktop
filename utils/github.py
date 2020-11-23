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
from cryptoadvance.specter.util.shell import run_shell, which
from github_binary_upload import publish_release_from_tag


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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
    if artifact_exists(project, tag, artifact):
        logger.info("Github artifact existing. Skipping upload.")
        exit(0)
    else:
        logger.info("Github artifact does not exist. Let's upload!")

    if not "GH_BIN_UPLOAD_PW" in os.environ:
        logger.error("GH_BIN_UPLOAD_PW not found.")
    else:
        password = os.environ["GH_BIN_UPLOAD_PW"]

    publish_release_from_tag(
        project,
        tag,
        [artifact],
        "github.com",
        "gitlab_upload_release_binaries",
        password,
    )


def artifact_exists(ci_project_root_namespace, ci_commit_tag, artifact):

    artifact_url = f"https://github.com/{ci_project_root_namespace}/specter-desktop/releases/download/{ci_commit_tag}/{artifact}"
    logger.debug(f"checking for artifact url {artifact_url}")
    r = requests.head(artifact_url)
    if r.status_code != 302:
        return False
    else:
        return True


if __name__ == "__main__":
    main()
