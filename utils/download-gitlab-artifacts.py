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
    raise Exception("Can't authenticate against Gitlab ( export CI_JOB_TOKEN )")

if os.environ.get("CI_PROJECT_ROOT_NAMESPACE"):
    project_root_namespace = os.environ.get("CI_PROJECT_ROOT_NAMESPACE")
    logger.info(f"Using project_root_namespace: {project_root_namespace}")
else:
    raise Exception(
        "no CI_PROJECT_ROOT_NAMESPACE given ( export CI_PROJECT_ROOT_NAMESPACE=k9ert )"
    )

if os.environ.get("CI_PROJECT_ID"):
    project_id = os.environ.get("CI_PROJECT_ID")
    github_project = f"{project_root_namespace}/specter-desktop"
else:
    project_id = 15721074  # cryptoadvance/specter-desktop
    project_id = 15541285
    github_project = f"{project_root_namespace}/specter-desktop"

logger.info(f"Using project_id: {project_id}")
logger.info(f"Using github_project: {github_project}")


project = gl.projects.get(project_id)

if os.environ.get("CI_PIPELINE_ID"):
    pipeline_id = os.environ.get("CI_PIPELINE_ID")
else:
    pipeline_id = 387387482  # cryptoadavance v1.7.0-pre1
    pipeline_id = 389780348  # k9ert v0.0.1-pre1

logger.info(f"Using pipeline_id: {pipeline_id}")

if os.environ.get("CI_COMMIT_TAG"):
    tag = os.environ.get("CI_COMMIT_TAG")
else:
    raise Exception("no tag given ( export CI_COMMIT_TAG=v0.0.0.0-pre13 )")

logger.info(f"Using tag: {tag}")


pipeline = project.pipelines.get(pipeline_id)

target_dir = "signing_dir"

Path(target_dir).mkdir(parents=True, exist_ok=True)


class Sha256sumFile:
    def __init__(self, name, target_dir="./signing_dir"):
        self.name = name
        self.target_dir = target_dir
        self.files = {}

    def is_in_target_dir(self):
        return os.path.isfile(os.path.join(target_dir, self.name))

    def download_from_tag(self, tag, gc):
        gc.download_artifact(tag, self.name, target_dir=self.target_dir)
        gc.download_artifact(tag, self.name + ".asc", target_dir=self.target_dir)
        self.read()

    def download_hashed_files(self, gc):
        for file in self.files.keys():
            logger.info(f"Downloading {file} from {tag}")
            gc.download_artifact(tag, file, target_dir=self.target_dir)

    def read(self):
        with open(os.path.join(self.target_dir, self.name), "r") as file:
            line = file.readline()
            while line:
                line = line.split(maxsplit=2)
                self.files[line[1]] = line[0]
                line = file.readline()

    def check_hashes(self):
        returncode = subprocess.call(
            ["sha256sum", "-c", self.name], cwd=self.target_dir
        )
        if returncode != 0:
            raise Exception(
                f"Could not validate hashes for file {self.name}: {subprocess.run(['sha256sum', '-c', self.name], cwd=self.target_dir)}"
            )

    def check_sig(self):
        returncode = subprocess.call(
            ["gpg", "--verify", self.name + ".asc"], cwd=target_dir
        )
        if returncode != 0:
            raise Exception(f"Could not validate signature of file {self.name}")


def download_and_unpack_all_artifacts(pipeline):
    if os.path.isdir(target_dir):
        logger.info(f"First purging {target_dir}")
        shutil.rmtree(target_dir)
    for job in pipeline.jobs.list():
        if job.name in [
            "release_electron_linux_windows",
            "release_binary_windows",
            "release_pip",
        ]:
            zipfn = f"/tmp/_artifacts_{job.name}.zip"
            job_obj = project.jobs.get(job.id, lazy=True)

            if not os.path.isfile(zipfn):
                logger.info(f"Downloading artifacts for {job.name}")
                with open(zipfn, "wb") as f:
                    job_obj.artifacts(streamed=True, action=f.write)
            else:
                logger.info(f"Skipping Download artifacts for {job.name}")

            logger.info(f"Unzipping {zipfn} in target-folder")
            with zipfile.ZipFile(zipfn, "r") as zip:
                for zip_info in zip.infolist():
                    if zip_info.filename[-1] == "/":
                        continue
                    zip_info.filename = os.path.basename(zip_info.filename)
                    logger.info(f" Extracting {zip_info.filename}")
                    zip.extract(zip_info, target_dir)


def download_and_unpack_new_artifacts_from_github(pipeline):
    gc = github.GithubConnection(github_project)
    release = gc.fetch_existing_release(tag)
    assets = gc.list_assets(release)
    for asset in assets:
        if not asset.name.startswith("SHA256"):
            continue
        if asset.name == "SHA256SUMS" or asset.name == "SHA256SUMS.asc":
            continue
        if asset.name.endswith(".asc"):
            continue
        shasumfile = Sha256sumFile(asset.name)
        if not shasumfile.is_in_target_dir():
            shasumfile.download_from_tag(tag, gc)
            shasumfile.download_hashed_files(gc)
            shasumfile.check_hashes()
            shasumfile.check_sig()


def create_sha256sum_file():
    with open(f"{target_dir}/SHA256SUMS", "w") as shafile:
        for file in os.listdir(target_dir):
            if file.startswith("SHA256SUMS-") and not file.endswith(".asc"):
                logger.debug(f"Processing {file}")
                sha_src = Sha256sumFile(file)
                sha_src.read()
                for hashed_file in sha_src.files.keys():
                    print(f"{sha_src.files[hashed_file]} {hashed_file}\n")
                    shafile.write(f"{sha_src.files[hashed_file]} {hashed_file}\n")
    returncode = subprocess.call(["sha256sum", "-c", "SHA256SUMS"], cwd=target_dir)
    if returncode != 0:
        raise Exception(
            f"One of the hashes is not matching: {subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=target_dir)}"
        )


def check_all_hashes():
    for file in os.listdir(target_dir):
        if file.startswith("SHA256SUM") and not file.endswith(".asc"):
            returncode = subprocess.call(["sha256sum", "-c", file], cwd=target_dir)
            if returncode != 0:
                raise Exception(f"Could not validate hashes for file {file}")


def check_all_sigs():
    for file in os.listdir(target_dir):
        if file.endswith(".asc"):
            returncode = subprocess.call(["gpg", "--verify", file], cwd=target_dir)
            if returncode != 0:
                raise Exception(f"Could not validate signature of file {file}")


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
    artifact = os.path.join("signing_dir", "SHA256SUMS")
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
    if "downloadgithub" in sys.argv:
        download_and_unpack_new_artifacts_from_github(pipeline)
    if "checkhashes" in sys.argv:
        check_all_hashes()
    if "checksigs" in sys.argv:
        check_all_sigs()
    if "create" in sys.argv:
        create_sha256sum_file()
    if "upload" in sys.argv:
        upload_sha256sum_file()
