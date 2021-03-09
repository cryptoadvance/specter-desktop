import os, time, requests, secrets, platform, tarfile, zipfile, sys, subprocess, shutil
import pgpy
from pathlib import Path
from .sha256sum import sha256sum


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
        specter.config["torbrowser_setup"]["stage"] = "Starting Tor setup process..."
        specter._save()
        TOR_OS_SUFFIX = {
            "Windows": "torbrowser-install-win64-10.0.12_en-US.exe",
            "Linux": "tor-browser-linux64-10.0.12_en-US.tar.xz",
            "Darwin": "TorBrowser-10.0.12-osx64_en-US.dmg",
        }

        torbrowser_url = f"https://www.torproject.org/dist/torbrowser/10.0.12/{TOR_OS_SUFFIX[platform.system()]}"
        response = specter.requests_session().get(torbrowser_url, stream=True)
        packed_name = os.path.join(
            specter.data_folder,
            TOR_OS_SUFFIX[platform.system()],
        )
        with open(packed_name, "wb") as f:
            total_length = float(response.headers["content-length"])
            downloaded = 0.0
            old_progress = 0
            specter.config["torbrowser_setup"][
                "stage"
            ] = "Downloading Tor release files..."
            specter._save()
            for chunk in response.iter_content(chunk_size=4096):
                downloaded += len(chunk)
                f.write(chunk)
                new_progress = int((downloaded / total_length) * 10000) / 100
                if new_progress > old_progress:
                    old_progress = new_progress
                    specter.config["torbrowser_setup"]["stage_progress"] = new_progress
                    specter._save()
        specter.config["torbrowser_setup"]["stage"] = "Verifying signatures..."
        specter._save()
        torbrowser_signed_url = f"https://www.torproject.org/dist/torbrowser/10.0.12/{TOR_OS_SUFFIX[platform.system()]}.asc"
        response = specter.requests_session().get(torbrowser_signed_url, stream=True)
        torbrowser_signed_file = os.path.join(
            specter.data_folder, f"{TOR_OS_SUFFIX[platform.system()]}.asc"
        )
        with open(torbrowser_signed_file, "wb") as f:
            total_length = float(response.headers["content-length"])
            for chunk in response.iter_content(chunk_size=4096):
                f.write(chunk)
        torbrowser_release_pgp_key, _ = pgpy.PGPKey.from_file(
            os.path.join(sys._MEIPASS, "static/torbrowser-release-pubkey.asc")
            if getattr(sys, "frozen", False)
            else Path(__file__).parent / "../static/torbrowser-release-pubkey.asc"
        )
        torbrowser_file_sig = pgpy.PGPSignature.from_file(torbrowser_signed_file)
        with open(packed_name, "rb") as binary_file:
            signed_data = binary_file.read()
            if not torbrowser_release_pgp_key.verify(signed_data, torbrowser_file_sig):
                raise Exception("Failed to verify Tor PGP signature")

        # TODO: Unpack file for each OS
        if packed_name.endswith(".dmg"):
            result = subprocess.run(
                [f'hdiutil attach "{packed_name}"'], shell=True, capture_output=True
            )
            if result.stderr == b"hdiutil: attach failed - no mountable file systems\n":
                os.remove(packed_name)
                return
            torbrowser_source_path = os.path.join(
                "/Volumes", "Tor Browser", "Tor Browser.app", "Contents", "MacOS", "Tor"
            )
            os.makedirs(
                os.path.join(specter.data_folder, "tor-binaries"), exist_ok=True
            )
            copytree(
                src=torbrowser_source_path,
                dst=os.path.join(specter.data_folder, "tor-binaries"),
            )
            disk_image_path = "/Volumes/Tor\ Browser"
            subprocess.run([f"hdiutil detach {disk_image_path}"], shell=True)
        os.remove(packed_name)
        specter.tor_daemon.start_tor_daemon()
    except Exception:
        pass
    finally:
        specter.config["torbrowser_setup"]["stage_progress"] = -1
        specter._save()
