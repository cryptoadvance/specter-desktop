import os, time, requests, platform, tarfile, zipfile, sys, subprocess, shutil, stat, zipfile, logging
import pgpy
from pathlib import Path
from .sha256sum import sha256sum
from .file_download import download_file

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
    try:
        # There is no Tor Browser binary for Raspberry Pi 4 (armv7l)
        if platform.system() == "Linux" and "armv" in platform.machine():
            raise Exception(
                "Linux ARM devices (e.g. Raspberry Pi) must manually install Tor"
            )

        specter.update_setup_status("torbrowser", "STARTING_SETUP")
        TOR_OS_SUFFIX = {
            "Windows": "tor-win64-0.4.5.7.zip",
            "Linux": "tor-browser-linux64-10.0.15_en-US.tar.xz",
            "Darwin": "TorBrowser-10.0.15-osx64_en-US.dmg",
        }

        packed_name = (
            os.path.join(sys._MEIPASS, f"torbrowser/{TOR_OS_SUFFIX[platform.system()]}")
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
            / f"../../../../pyinstaller/torbrowser/{TOR_OS_SUFFIX[platform.system()]}"
        )

        os.makedirs(os.path.join(specter.data_folder, "tor-binaries"), exist_ok=True)
        if TOR_OS_SUFFIX[platform.system()].endswith(".dmg"):
            result = subprocess.run(
                [f'hdiutil attach "{packed_name}"'], shell=True, capture_output=True
            )
            if result.stderr == b"hdiutil: attach failed - no mountable file systems\n":
                os.remove(packed_name)
                return
            torbrowser_source_path = os.path.join(
                "/Volumes", "Tor Browser", "Tor Browser.app", "Contents", "MacOS", "Tor"
            )
            copytree(
                src=torbrowser_source_path,
                dst=os.path.join(specter.data_folder, "tor-binaries"),
            )
            disk_image_path = "/Volumes/Tor\ Browser"
            subprocess.run([f"hdiutil detach {disk_image_path}"], shell=True)
        elif TOR_OS_SUFFIX[platform.system()].endswith(".zip"):
            with zipfile.ZipFile(packed_name) as zip_file:
                for file in zip_file.filelist:
                    if file.filename.endswith("dll") or file.filename.endswith("exe"):
                        destination_exe = os.path.join(
                            os.path.join(specter.data_folder, "tor-binaries"),
                            file.filename.split("/")[-1],
                        )
                        with zip_file.open(file.filename) as zf, open(
                            destination_exe, "wb"
                        ) as f:
                            shutil.copyfileobj(zf, f)
        elif TOR_OS_SUFFIX[platform.system()].endswith(".tar.xz"):
            with tarfile.open(packed_name) as tar:
                tor_files = [
                    "libcrypto.so.1.1",
                    "libevent-2.1.so.7",
                    "libssl.so.1.1",
                    "tor",
                ]
                for tor_file in tor_files:
                    file_name = "tor-browser_en-US/Browser/TorBrowser/Tor/" + tor_file
                    destination_file = os.path.join(
                        os.path.join(specter.data_folder, "tor-binaries"), tor_file
                    )
                    extracted_file = tar.extractfile(file_name)
                    with open(destination_file, "wb") as f:
                        shutil.copyfileobj(extracted_file, f)
                        if tor_file == "tor":
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
        logger.error(f"Failed to install Tor. Error: {e}")
        specter.update_setup_error("torbrowser", str(e))
