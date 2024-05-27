import hashlib
import logging
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from glob import glob


logging.basicConfig(format="%(levelname)s:%(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


import os
import subprocess
import hashlib
import logging
import gitlab

logger = logging.getLogger(__name__)


class Sha256sumFile:
    """
    A class that provides functionality to manage SHA256 checksums for files within a
    specified directory.

    Attributes:
        name (str): The name of the file that contains the SHA256 checksums for other files.
        target_dir (str): The path to the directory where the checksum file and other related
                          files are stored or will be downloaded to. Defaults to `./signing_dir`.
        hashed_files (dict): A dictionary storing file names as keys and their corresponding
                             SHA256 hashes as values.

    The `hashed_files` dictionary data structure is used to map each file name (a string)
    to its SHA256 hash (also a string). The SHA256 hash is computed for each corresponding
    file present in the `target_dir`, allowing for verification of file integrity by comparing
    computed hashes against stored hashes.
    """

    def __init__(self, name, target_dir="./signing_dir"):
        """
        Initializes a Sha256sumFile instance with the provided checksum file name and target directory.

        Parameters:
            name (str): The name of the checksum file.
            target_dir (str): The directory path where the checksum file and other files are present or downloaded.
        """
        self.name = name
        self.target_dir = target_dir
        self.hashed_files = {}

    def is_in_target_dir(self):
        """
        Checks if the checksum file is present in the target directory.

        Returns:
            bool: True if the checksum file is present; False otherwise.
        """
        return os.path.isfile(os.path.join(self.target_dir, self.name))

    def download_from_tag(self, tag, gc):
        """
        Downloads the checksum file and its signature from a specific tag using a given client (gc).

        Parameters:
            tag (str): The tag associated with the artifacts to be downloaded.
            gc (object): The client object which provides the `download_artifact` method for downloading.
        """
        gc.download_artifact(tag, self.name, target_dir=self.target_dir)
        gc.download_artifact(tag, self.name + ".asc", target_dir=self.target_dir)
        self.read()

    def download_hashed_files(self, tag, gc):
        """
        Downloads all files listed in the hashed_files dictionary from a specific tag using a given client (gc).

        Parameters:
            tag (str): The tag associated with the artifacts to be downloaded.
            gc (object): The client object which provides the `download_artifact` method for downloading.
        """
        for file in self.hashed_files.keys():
            logger.info(f"Downloading {file} from {tag}")
            gc.download_artifact(tag, file, target_dir=self.target_dir)

    def read(self):
        """
        Reads the checksum file and populates the hashed_files dictionary with file names and their corresponding hashes.
        """
        with open(os.path.join(self.target_dir, self.name), "r") as file:
            line = file.readline()
            while line:
                line = line.split(maxsplit=2)
                self.hashed_files[line[1]] = line[0]
                line = file.readline()

    def print(self):
        """
        Prints each file's hash and name from the hashed_files dictionary to the standard output.
        """
        for hashed_file, hash in self.hashed_files.items():
            print(f"{hash} {hashed_file}")

    def write(self):
        """
        Writes the hashed_files dictionary entries to the checksum file in the target directory.
        """
        with open(os.path.join(self.target_dir, self.name), "w") as file:
            for hashed_file, hash in self.hashed_files.items():
                file.write(f"{hash} {hashed_file}\n")

    def add_file(self, file):
        """
        Computes the SHA256 hash for a given file and adds the file and its hash to the hashed_files dictionary.

        Parameters:
            file (str): The filename for which the SHA256 hash should be computed and added.
        """
        self.hashed_files[file] = Sha256sumFile.sha256_checksum(file, self.target_dir)

    def check_hashes(self):
        """
        Verifies the integrity of the files by checking their SHA256 hashes against the entries in the checksum file.

        Raises:
            Exception: If the verification of any file fails, an exception is raised with
            the subprocess output that caused the failure.
        """
        try:
            subprocess.run(
                ["sha256sum", "-c", self.name], cwd=self.target_dir, check=True
            )
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"Could not validate hashes for file {self.name}: {e.output}"
            )

    def check_sig(self):
        """
        Verifies the signature of the checksum file using gpg.

        Raises:
            Exception: If the verification of the file signature fails, an exception is raised.
        """
        returncode = subprocess.call(
            ["gpg", "--verify", self.name + ".asc"], cwd=self.target_dir
        )
        if returncode != 0:
            raise Exception(f"Could not validate signature of file {self.name}")

    @classmethod
    def sha256_checksum(cls, filename, folder, block_size=65536):
        """
        Computes the SHA256 hash of a given file.

        Parameters:
            filename (str): The name of the file for which to compute the SHA256 hash.
            folder (str): The path to the directory containing the file.
            block_size (int): The block size used for reading the file. Defaults to 65536.

        Returns:
            str: The SHA256 hash of the file.
        """
        sha256 = hashlib.sha256()
        with open(os.path.join(folder, filename), "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                sha256.update(block)
        return sha256.hexdigest()


class ReleaseHelper:
    """
    A class that manages software build artifacts for a CI/CD pipeline.

    This class is designed to perform operations such as downloading artifacts from CI
    pipelines, verifying SHA256 checksums, verifying GPG signatures, and uploading
    artifacts to GitHub releases.

    The class relies on a number of environment variables being present:
        CI_COMMIT_TAG: The git tag to work with (format: export CI_COMMIT_TAG=<tag_name>).
        CI_PIPELINE_ID: The pipeline ID for which artifacts are managed
                        (format: export CI_PIPELINE_ID=<pipeline_id>).
        CI_PROJECT_ROOT_NAMESPACE: The root namespace of the CI project
                                   (required for uploading to GitHub).
        GH_BIN_UPLOAD_PW: Password or token for GitHub to authenticate uploads.

    Attributes:
        target_dir (str): The directory path where artifacts are to be managed.
        tag (str): The git tag associated with the artifacts being managed.
        pipeline_id (str): The CI pipeline ID for artifact management operations.
        pipeline (Pipeline): A pipeline object fetched from the CI server.
        github_project (str): The GitHub repository in which the release should be created or updated.
        password (str): The password or token used to authenticate with GitHub.

    Methods:
        download_and_unpack_all_artifacts(): Downloads and unpacks artifacts from a CI pipeline.
        download_and_unpack_new_artifacts_from_github():
            Downloads and unpacks new artifacts from GitHub.
        create_sha256sum_file(): Creates a SHA256SUMS file with checksums of all artifacts.
        check_all_hashes(): Verifies checksums for all artifacts.
        check_all_sigs(): Verifies GPG signatures for all artifacts.
        calculate_publish_params(): Calculates and validates necessary parameters for publishing.
        upload_sha256sum_file(): Uploads the SHA256SUMS file to a GitHub release.
        upload_sha256sumsig_file(): Uploads the SHA256SUMS.asc signature file to a GitHub release.

    Note: The actual implementation of the methods and the use of additional classes
    like `github.GithubConnection` or `Sha256sumFile` are assumed to exist and are
    not defined in this documentation.
    """

    def __init__(self):
        self.target_dir = "signing_dir"
        Path(self.target_dir).mkdir(parents=True, exist_ok=True)

    @property
    def gl(self):
        # https://python-gitlab.readthedocs.io/en/stable/api-usage.html
        import gitlab

        if os.environ.get("GITLAB_PRIVATE_TOKEN"):
            logger.info("Using GITLAB_PRIVATE_TOKEN")
            gl = gitlab.Gitlab(
                "http://gitlab.com",
                private_token=os.environ.get("GITLAB_PRIVATE_TOKEN"),
            )
        elif os.environ.get("CI_JOB_TOKEN"):
            logger.info("Using CI_JOB_TOKEN")
            self.gl = gitlab.Gitlab(
                "http://gitlab.com", job_token=os.environ["CI_JOB_TOKEN"]
            )
        else:
            raise Exception(
                "Can't authenticate against Gitlab ( export GITLAB_PRIVATE_TOKEN )"
            )
        return gl

    @property
    def gitlab_project(self):
        if hasattr(self, "_gitlab_project"):
            return self._gitlab_project
        try:
            from gitlab.v4.objects import Project

            self._gitlab_project: Project = self.gl.projects.get(self.ci_project_id)
        except gitlab.exceptions.GitlabAuthenticationError as e:
            logger.fatal(e)
            logger.error("Your token might be expired or wrong. Get a new one here:")
            logger.error("  https://gitlab.com/-/profile/personal_access_tokens")
            exit(2)

        if (
            self._gitlab_project.attributes["namespace"]["path"]
            != self.ci_project_root_namespace
        ):
            logger.fatal(
                f"project_root_namespace ({ self.ci_project_root_namespace }) does not match namespace of Project ({self._gitlab_project.attributes['namespace']['path']}) "
            )
            logger.error("You might want to: unset CI_PROJECT_ID")
            exit(2)
        return self._gitlab_project

    @property
    def ci_project_id(self):
        if hasattr(self, "_ci_project_id"):
            return self._ci_project_id
        if os.environ.get("CI_PROJECT_ID"):
            self._ci_project_id = os.environ.get("CI_PROJECT_ID")
            logger.info(f"Using ci_project_id: {self.ci_project_id} ")
        else:
            logger.error("No Project given. choose one:")
            for project in self.gl.projects.list(search="specter-desktop"):
                logger.info(
                    f"     export CI_PROJECT_ID={project.id}  # {project.name_with_namespace}"
                )
                if project.name_with_namespace.startswith("cryptoadvance"):
                    self._ci_project_id = project.id
            logger.warn("{self._ci_project_id} has been chosen as self._ci_project_id")
        return self._ci_project_id

    @property
    def github_project(self):
        if hasattr(self, "_github_project"):
            return self._github_project
        self._github_project = f"{self.ci_project_root_namespace}/specter-desktop"
        logger.info(f"Using github_project: {self._github_project}")
        return self._github_project

    @property
    def ci_commit_tag(self):
        if hasattr(self, "_ci_commit_tag"):
            return self._ci_commit_tag
        if os.environ.get("CI_COMMIT_TAG"):
            self._ci_commit_tag = os.environ.get("CI_COMMIT_TAG")
        else:
            raise Exception("no tag given ( export CI_COMMIT_TAG=v0.0.0.0-pre13 )")
        logger.info(f"Using tag: {self._ci_commit_tag}")
        return self._ci_commit_tag

    @property
    def ci_project_root_namespace(self):
        if hasattr(self, "_ci_project_root_namespace"):
            return self._ci_project_root_namespace
        if os.environ.get("CI_PROJECT_ROOT_NAMESPACE"):
            self._ci_project_root_namespace = os.environ.get(
                "CI_PROJECT_ROOT_NAMESPACE"
            )
            logger.info(
                f"Using project_root_namespace: {project_root_namespace} ( export CI_PROJECT_ROOT_NAMESPACE={project_root_namespace} )"
            )
        else:
            self._ci_project_root_namespace = "cryptoadvance"
            logger.warn(
                f"Using project_root_namespace: {self._ci_project_root_namespace} ( export CI_PROJECT_ROOT_NAMESPACE={self._ci_project_root_namespace} )"
            )
        return self._ci_project_root_namespace

    @property
    def ci_pipeline_id(self):
        if hasattr(self, "_ci_pipeline_id"):
            return self._ci_pipeline_id

        if os.environ.get("CI_PIPELINE_ID"):
            self._ci_pipeline_id = os.environ.get("CI_PIPELINE_ID")
        else:
            logger.info(
                "no CI_PIPELINE_ID given, trying to find an appropriate one ..."
            )
            pipelines = self.gitlab_project.pipelines.list()
            for pipeline in pipelines:
                if pipeline.ref == self.ci_commit_tag:
                    self._ci_pipeline_id = pipeline.id
                    self._ci_pipeline = pipeline
                    logger.info(f"Found matching pipeline: {pipeline}")
            if not hasattr(self, "_ci_pipeline"):
                logger.error(
                    f"Could not find tag {self.ci_commit_tag} in the pipeline-refs:"
                )
                for pipeline in self.gitlab_project.pipelines.list():
                    logger.error(pipeline.ref)
                raise Exception(
                    "no CI_PIPELINE_ID given ( export CI_PIPELINE_ID= ) or maybe you're on the wrong project ( export CI_PROJECT_ROOT_NAMESPACE= )"
                )

        logger.info(f"Using pipeline_id: {self.ci_pipeline.id}")
        return self._ci_pipeline_id

    @property
    def ci_pipeline(self):
        if hasattr(self, "_ci_pipeline"):
            return self._ci_pipeline
        self._ci_pipeline = self.gitlab_project.pipelines.get(self.ci_pipeline_id)
        return self._ci_pipeline

    def download_and_unpack_all_artifacts(self):
        if os.path.isdir(self.target_dir):
            logger.info(f"First purging {self.target_dir}")
            shutil.rmtree(self.target_dir)
        for job in self.ci_pipeline.jobs.list():
            if job.name in [
                "release_electron_linux_windows",
                "release_binary_windows",
                "release_pip",
            ]:
                zipfn = f"/tmp/_artifacts_{job.name}.zip"
                job_obj = self.gitlab_project.jobs.get(job.id, lazy=True)

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
                        zip.extract(zip_info, self.target_dir)

    def download_and_unpack_new_artifacts_from_github(self):

        gc = github.GithubConnection(self.github_project)
        release = gc.fetch_existing_release(self.ci_commit_tag)
        assets = gc.list_assets(release)
        for asset in assets:
            if not asset.name.startswith("SHA256"):
                continue
            if asset.name == "SHA256SUMS" or asset.name == "SHA256SUMS.asc":
                continue
            if asset.name.endswith(".asc"):
                continue
            logger.info("iterating file " + asset.name)
            shasumfile = Sha256sumFile(asset.name)
            if not shasumfile.is_in_target_dir():
                shasumfile.download_from_tag(self.ci_commit_tag, gc)
                shasumfile.download_hashed_files(self.ci_commit_tag, gc)
                shasumfile.check_hashes()
                shasumfile.check_sig()
        logger.info("All files have valid signatures")

    def create_sha256sum_file(self):
        with open(f"{self.target_dir}/SHA256SUMS", "w") as shafile:
            for file in os.listdir(self.target_dir):
                if file.startswith("SHA256SUMS-") and not file.endswith(".asc"):
                    logger.debug(f"Processing {file}")
                    sha_src = Sha256sumFile(file)
                    sha_src.read()
                    for hashed_file in sha_src.hashed_files.keys():
                        print(f"{sha_src.hashed_files[hashed_file]} {hashed_file}\n")
                        shafile.write(
                            f"{sha_src.hashed_files[hashed_file]} {hashed_file}\n"
                        )
        returncode = subprocess.call(
            ["sha256sum", "-c", "SHA256SUMS"], cwd=self.target_dir
        )
        if returncode != 0:
            raise Exception(
                f"One of the hashes is not matching: {subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=self.target_dir)}"
            )

    def check_all_hashes(self):
        for file in os.listdir(self.target_dir):
            if file.startswith("SHA256SUM") and not file.endswith(".asc"):
                logger.info(f"Checking hashes in {file}")
                if file.endswith("windows"):
                    logger.info(f"Converting dos2unix for {file}")
                    dos2unix(os.path.join("signing_dir", file))
                returncode = subprocess.call(
                    ["sha256sum", "-c", file], cwd=self.target_dir
                )
                if returncode != 0:
                    raise Exception(f"Could not validate hashes for file {file}")
        logger.info("All files SHA256SUM* (not .asc) has valid hashes")

    def check_all_sigs(self):
        for file in os.listdir(self.target_dir):
            if file.endswith(".asc"):
                logger.info(f"Checking signature for {file}")
                returncode = subprocess.call(
                    ["gpg", "--verify", file], cwd=self.target_dir
                )
                if returncode != 0:
                    raise Exception(
                        f"Could not validate signature of file {file}: {subprocess.run(['gpg', '--verify', file], cwd=self.target_dir)}"
                    )
        logger.info("All files *.asc has valid signatures")

    def calculate_publish_params(self):
        if not "CI_PROJECT_ROOT_NAMESPACE" in os.environ:
            logger.error("CI_PROJECT_ROOT_NAMESPACE not found")
            exit(2)
        else:
            self.github_project = (
                f"{os.environ['CI_PROJECT_ROOT_NAMESPACE']}/specter-desktop"
            )
        if not "CI_COMMIT_TAG" in os.environ:
            logger.error("CI_COMMIT_TAG not found")
            exit(2)
        else:
            tag = os.environ["CI_COMMIT_TAG"]
        if not "GH_BIN_UPLOAD_PW" in os.environ:
            logger.error("GH_BIN_UPLOAD_PW not found.")
            exit(2)
        else:
            self.password = os.environ["GH_BIN_UPLOAD_PW"]

    def upload_sha256sum_file(self):
        artifact = os.path.join("signing_dir", "SHA256SUMS")
        self.calculate_publish_params()

        if github.artifact_exists(
            self.github_project, self.ci_commit_tag, Path(artifact).name
        ):
            logger.info(f"Github artifact {artifact} existing. Skipping upload.")
            exit(0)
        else:
            logger.info(f"Github artifact {artifact} does not exist. Let's upload!")
        github.publish_release_from_tag(
            self.github_project,
            self.ci_commit_tag,
            [artifact],
            "gitlab_upload_release_binaries",
            self.password,
        )

    def upload_sha256sumsig_file(self):
        artifact = os.path.join("signing_dir", "SHA256SUMS.asc")
        self.calculate_publish_params()

        if github.artifact_exists(
            self.github_project, self.ci_commit_tag, Path(artifact).name
        ):
            logger.info(f"Github artifact {artifact} existing. Skipping upload.")
            exit(0)
        else:
            logger.info(f"Github artifact {artifact} does not exist. Let's upload!")
        github.publish_release_from_tag(
            self.github_project,
            self.ci_commit_tag,
            [artifact],
            "gitlab_upload_release_binaries",
            self.password,
        )


def dos2unix(filename):
    content = ""
    outsize = 0
    with open(filename, "rb") as infile:
        content = infile.read()
    with open(filename, "wb") as output:
        for line in content.splitlines():
            outsize += len(line) + 1
            output.write(line + b"\n")


def sha256sum(filenames):
    sha_file = Sha256sumFile("SHA256SUMS", target_dir=".")
    for filename in filenames:
        logger.info(f"Adding {filename}")
        sha_file.add_file(filename)
    sha_file.print()


if __name__ == "__main__":
    if "sha256sums" in sys.argv:
        # Used by build-win.ci.bat
        sha256sum(sys.argv[2:])
        exit(0)
    if "install_wheel" in sys.argv:
        # List all .whl files in the 'dist' directory
        wheel_files = glob(
            str(Path("dist", "cryptoadvance.specter-*-py3-none-any.whl"))
        )
        print("found those wheel files: " + str(wheel_files))

        # Loop through the wheel files and install them
        for wheel_file in wheel_files:
            cmd = f"pip3 install {wheel_file}"
            res = os.system(cmd)
            print(f"Result of command: {cmd}")
            print(res)
            # If the installation fails, exit with the error code
            if res != 0:
                exit(res)
        # Exit with a success code if all installations were successful
        exit(0)

    rh = ReleaseHelper()
    try:
        from utils import github
    except Exception as e:
        logger.fatal(e)
        logger.error("You might have called this script wrong. Execute it like:")
        logger.error("python3 -m utils.release_helper ...")

    if "download" in sys.argv:
        rh.download_and_unpack_all_artifacts()
    if "downloadgithub" in sys.argv:
        rh.download_and_unpack_new_artifacts_from_github()
    if "checkhashes" in sys.argv:
        rh.check_all_hashes()
    if "checksigs" in sys.argv:
        rh.check_all_sigs()
    if "create" in sys.argv:
        rh.create_sha256sum_file()
    if "upload_shasums" in sys.argv:
        rh.upload_sha256sum_file()
    if "upload_shasumssig" in sys.argv:
        rh.upload_sha256sumsig_file()
