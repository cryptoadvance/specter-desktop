import hashlib
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import gitlab

from utils import github

logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if os.environ.get("GITLAB_PRIVATE_TOKEN"):
    logger.info("Using GITLAB_PRIVATE_TOKEN")
    gl = gitlab.Gitlab(
        "http://gitlab.com", private_token=os.environ.get("GITLAB_PRIVATE_TOKEN")
    )
elif os.environ.get("CI_JOB_TOKEN"):
    logger.info("Using CI_JOB_TOKEN")
    gl = gitlab.Gitlab("http://gitlab.com", job_token=os.environ["CI_JOB_TOKEN"])
else:
    raise Exception("Can't authenticate against Gitlab")

if os.environ.get("CI_PROJECT_ID"):
    project_id = os.environ.get("CI_PROJECT_ID")
    github_project = f"{os.environ['CI_PROJECT_ROOT_NAMESPACE']}/specter-desktop"
else:
    project_id = 15721074  # cryptoadvance/specter-desktop
    project_id = 15541285
project = gl.projects.get(project_id)

if os.environ.get("CI_PIPELINE_ID"):
    pipeline_id = os.environ.get("CI_PIPELINE_ID")
else:
    pipeline_id = 387387482  # cryptoadavance v1.7.0-pre1
    pipeline_id = 388946842  # k9ert v0.0.0-pre1

pipeline = project.pipelines.get(pipeline_id)

target_dir = "signing_dir"

Path(target_dir).mkdir(parents=True, exist_ok=True)


def download_and_unpack_all_artifacts(pipeline):
    for job in pipeline.jobs.list():
        if job.name in [
            "release_electron_linux_windows",
            "release_binary_windows",
            "release_pip",
        ]:
            zipfn = f"/tmp/_artifacts_{job.name}.zip"
            logger.info(f"Downloading artifacts for {job.name}")
            job = project.jobs.get(job.id, lazy=True)
            if not os.path.isfile(zipfn):
                with open(zipfn, "wb") as f:
                    job.artifacts(streamed=True, action=f.write)

            logger.info(f"Unzipping in target-folder")
            if os.path.isdir(target_dir):
                logger.info(f"First purging {target_dir}")
                shutil.rmtree(target_dir)
            with zipfile.ZipFile(zipfn, "r") as zip:
                for zip_info in zip.infolist():
                    if zip_info.filename[-1] == "/":
                        continue
                    zip_info.filename = os.path.basename(zip_info.filename)
                    logger.info(f" Extracting {zip_info.filename}")
                    zip.extract(zip_info, target_dir)


def create_sha256sum_file():
    with open(f"{target_dir}/SHA256SUMS.txt", "w") as shafile:
        for file in os.listdir(target_dir):
            if file.startswith("SHA256"):
                continue
            with open(os.path.join(target_dir, file), "rb") as f:
                bytes = f.read()  # read entire file as bytes
                readable_hash = hashlib.sha256(bytes).hexdigest()
                shafile.write(f"{readable_hash} {file}\n")
    returncode = subprocess.call(["sha256sum", "-c", "SHA256SUMS.txt"], cwd=target_dir)
    if returncode != 0:
        raise Exception("One of the hashes is not matching")


def calculate_publish_params():
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
    if not "GH_BIN_UPLOAD_PW" in os.environ:
        logger.error("GH_BIN_UPLOAD_PW not found.")
        exit(2)
    else:
        password = os.environ["GH_BIN_UPLOAD_PW"]
    return project, tag, password


def upload_sha256sum_file():
    artifact = os.path.join("signing_dir", "SHA256SUMS.txt")
    project, tag, password = calculate_publish_params()

    if github.artifact_exists(project, tag, Path(artifact).name):
        logger.info("Github artifact existing. Skipping upload.")
        exit(0)
    else:
        logger.info("Github artifact does not exist. Let's upload!")
    github.publish_release_from_tag(
        project,
        tag,
        [artifact],
        "github.com",
        "gitlab_upload_release_binaries",
        password,
    )


if __name__ == "__main__":
    if "download" in sys.argv:
        download_and_unpack_all_artifacts(pipeline)
    if "create" in sys.argv:
        create_sha256sum_file()
    if "upload" in sys.argv:
        upload_sha256sum_file()
