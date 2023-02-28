import os, time, requests, platform, tarfile, zipfile, sys, subprocess, shutil, stat, zipfile, logging
import pgpy
from pathlib import Path
from .sha256sum import sha256sum
from .file_download import download_file
from .tor import get_tor_daemon_suffix

logger = logging.getLogger(__name__)


def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def setup_tor_thread(specter=None):
    """This will extracted the tor-binary out of the tar.xz packaged with specterd and copy
    it over to the ~/.specter/tor-binaries folder
    Then it will create a torrc file and start the tor-demon
    """
    try:
        specter.update_setup_status("torbrowser", "STARTING_SETUP")
        TOR_OS_SUFFIX = {
            "Windows": "tor-win64-0.4.8.0.tar.xz",
            "Linux": "tor-linux64-0.4.8.0.tar.xz",
            "Darwin": "tor-osx64-0.4.8.0.tar.xz",
        }

        packed_name = (
            os.path.join(sys._MEIPASS, f"tor/{TOR_OS_SUFFIX[platform.system()]}")
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
            / f"../../../../pyinstaller/tor/{TOR_OS_SUFFIX[platform.system()]}"
        )
        logger.info(f"packed tor binary: {packed_name}")

        os.makedirs(os.path.join(specter.data_folder, "tor-binaries"), exist_ok=True)
        with tarfile.open(packed_name) as tar:
            file_name = f"tor{get_tor_daemon_suffix()}"
            destination_file = os.path.join(
                os.path.join(specter.data_folder, "tor-binaries"), file_name
            )
            extracted_file = tar.extractfile(file_name)
            with open(destination_file, "wb") as f:
                shutil.copyfileobj(extracted_file, f)
                if not file_name.endswith(".exe"):
                    st = os.stat(destination_file)
                    os.chmod(destination_file, st.st_mode | stat.S_IEXEC)

        if "torrc_password" not in specter.config:
            specter.generate_torrc_password()
        with open(os.path.join(specter.data_folder, "torrc"), "w") as file:
            file.write("ControlPort 9051")
            file.write(
                f"\nHashedControlPassword {specter.tor_daemon.get_hashed_password(specter.config['torrc_password'])}"
            )

        specter.tor_daemon.start_tor_daemon()
        specter.update_tor_controller()
        specter.reset_setup("torbrowser")
    except Exception as e:
        logger.exception(f"Failed to install Tor.")
        specter.update_setup_error("torbrowser", str(e))
