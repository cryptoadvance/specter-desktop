from cryptoadvance.specter.util.file_download import download_file
from cryptoadvance.specter.util.flask import FlaskThread
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.specter_error import SpecterInternalException
import os
import hashlib
import logging
import shutil
import tempfile
import urllib.request
import zipfile
import tarfile
import time
import platform as platform_lib

logger = logging.getLogger(__name__)


class BinaryDownloader:
    """
    Should work as a flexible Donwload solution which can download binaries from somewhere.
    Will only download if necessary. Each time the hash will get checked. Will download
    if binary is not there or hash doesn't match.
    The status-attribute should be "ready" eventually. In that case the `get-executable`
    method should no longer throw an exception but return the path to the binary.

    As such it's recommended to pass that method to whatever needs to execute it.
    This would ensure that only verified binaries get executed.
    """

    def __init__(self, specter: Specter, download_url, binary, hash, version=""):
        self.specter = specter
        self.download_url = download_url
        self.expected_hash = hash
        self.target_dir = os.path.join(specter.data_folder, "binaries")
        self.expected_file = os.path.join(
            self.target_dir, binary if version == "" else f"{binary}-{version}"
        )
        if os.path.exists(self.expected_file):
            if verify_hash(self.expected_file, hash):
                self.status = "ready"
                return
            else:
                os.remove(self.expected_file)

        self.status = "downloading"
        self._download_thread = FlaskThread(target=self._download_and_extract)
        self._download_thread.start()

    def get_executable(self):
        """Returns the path of the binary only if the hash of the binary matches. Otherwise a SpecterInternalException"""
        if self.status == "ready":
            return self.expected_file
        if self.status.startswith("failed"):
            raise SpecterInternalException(
                f"Could not download binary {self.download_url}"
            )
        for i in range(1, 100):
            time.sleep(0.3)
            if self.status == "ready":
                return self.expected_file
        raise SpecterInternalException(
            f"Could not download binary quick enough {self.download_url}, stuck in status {self.status}"
        )

    @property
    def status(self) -> str:
        """Check the _download_and_extract method for valid stati"""
        if hasattr(self, "_status"):
            return self._status
        return "unknown"

    @status.setter
    def status(self, value: str):
        logger.info(
            f"BinaryDownloader ({self.download_url}) Status changed from {self.status} to {value}"
        )
        self._status = value

    @classmethod
    def from_github_repo(clz, specter: Specter, version: str, hash: str):
        """
        * version: e.g. 2.2.1
        * platform: one of:linux-amd64,mac-amd64 or windows-amd64
            *
        """
        # https://github.com/bitcoin-core/HWI/releases/download/2.2.1/hwi-2.2.1-linux-amd64.tar.gz
        # https://github.com/bitcoin-core/HWI/releases/download/2.2.1/hwi-2.2.1-mac-amd64.tar.gz
        # https://github.com/bitcoin-core/HWI/releases/download/2.2.1/hwi-2.2.1-windows-amd64.zip

        platform_mapping = {
            "Linux": "linux-amd64",
            "Darwin": "mac-amd64",
            "Windows": "windows-amd64",
        }
        try:
            platform = platform_mapping[platform_lib.system()]
        except KeyError as e:
            raise SpecterInternalException(f"Unsupported Platform: {e}")
        org = "bitcoin-core"
        project = "HWI"
        packageformat = "zip" if platform.startswith("windows") else "tar.gz"
        download_url = f"https://github.com/{org}/{project}/releases/download/{version}/hwi-2.2.1-{platform}.{packageformat}"
        return clz(specter, download_url, "hwi", hash, version=version)

    def _download_and_extract(self):
        # determine filename from url
        filename = self.download_url.split("/")[-1]
        # Creating target_dir if necessary
        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir)

        # download file
        logger.info(f"Start downloading {self.download_url}")
        response = self.specter.requests_session().get(self.download_url)
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_file.write(response.content)
            downloaded_file = tmp_file.name
        logger.info(f"Finished downloading {downloaded_file}")

        self.status = "extracting"
        # extract file to temp dir
        temp_dir = tempfile.mkdtemp()
        if filename.endswith(".zip"):
            with zipfile.ZipFile(downloaded_file, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
        elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
            with tarfile.open(downloaded_file, "r:gz") as tar_ref:
                tar_ref.extractall(temp_dir)
        else:
            raise SpecterInternalException("Unknown file type")

        # copy hwi binary to target dir
        extracted_files = os.listdir(temp_dir)
        for extracted_file in extracted_files:
            if extracted_file.endswith("hwi") and os.path.isfile(
                os.path.join(temp_dir, extracted_file)
            ):
                self.status = "verifying"
                # verify hash
                verified, actual_hash, expected_hash = verify_hash(
                    downloaded_file, self.expected_hash
                )
                if verified:
                    self.status = "failed_verification"
                    raise SpecterInternalException(
                        f"Hash verification failed ({actual_hash} != {expected_hash}) "
                    )
                shutil.copy2(os.path.join(temp_dir, extracted_file), self.expected_file)
                break

        # delete temp dir and downloaded file
        shutil.rmtree(temp_dir)
        os.remove(downloaded_file)
        self.status = "ready"


def verify_hash(the_file, expected_hash):
    """Returns a boolean whether the file has the expected_hash"""
    hasher = hashlib.sha256()
    with open(the_file, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest() == expected_hash, hasher.hexdigest(), expected_hash
