import os, time, requests, secrets, platform, tarfile, zipfile, sys
from ..bitcoind import BitcoindPlainController
import pgpy
from pathlib import Path
from .sha256sum import sha256sum
import logging
from .file_download import download_file

logger = logging.getLogger(__name__)


def setup_bitcoind_thread(specter=None, internal_bitcoind_version=""):
    try:
        BITCOIND_OS_SUFFIX = {
            "Windows": "win64.zip",
            "Linux": "x86_64-linux-gnu.tar.gz",
            "Darwin": "osx64.tar.gz",
        }
        # ARM Linux devices (e.g. Raspberry Pi 4 == armv7l) need ARM binary
        if platform.system() == "Linux" and "armv" in platform.machine():
            BITCOIND_OS_SUFFIX["Linux"] = "arm-linux-gnueabihf.tar.gz"
        bitcoind_url = f"https://bitcoincore.org/bin/bitcoin-core-{internal_bitcoind_version}/bitcoin-{internal_bitcoind_version}-{BITCOIND_OS_SUFFIX[platform.system()]}"
        packed_name = os.path.join(
            specter.data_folder,
            f"bitcoind-{BITCOIND_OS_SUFFIX[platform.system()]}",
        )
        download_file(
            specter,
            bitcoind_url,
            packed_name,
            "bitcoind",
            "Downloading Bitcoin Core release files...",
        )
        bitcoind_sha256sums_url = f"https://bitcoincore.org/bin/bitcoin-core-{internal_bitcoind_version}/SHA256SUMS.asc"
        bitcoind_sha256sums_file = os.path.join(
            specter.data_folder, "bitcoind-sha256sums.asc"
        )
        download_file(
            specter,
            bitcoind_sha256sums_url,
            bitcoind_sha256sums_file,
            "bitcoind",
            "Downloading Bitcoin Core signatures...",
        )
        specter.config["bitcoind_setup"]["stage"] = "Verifying signatures..."
        specter._save()
        with open(bitcoind_sha256sums_file, "r") as f:
            signed_sums = f.read()
            bitcoind_release_pgp_key, _ = pgpy.PGPKey.from_file(
                os.path.join(sys._MEIPASS, "static/bitcoin-release-pubkey.asc")
                if getattr(sys, "frozen", False)
                else Path(__file__).parent / "../static/bitcoin-release-pubkey.asc"
            )
            bitcoind_sha256sums_msg = pgpy.PGPMessage.from_file(
                bitcoind_sha256sums_file
            )
            if not bitcoind_release_pgp_key.verify(bitcoind_sha256sums_msg):
                raise Exception("Failed to verify Bitcoin Core PGP signature")
            bitcoind_hash = sha256sum(packed_name)
            if bitcoind_hash not in signed_sums:
                raise Exception("Failed to verify bitcoind hash is in SHA265SUMS.asc")

        bitcoin_binaries_folder = os.path.join(specter.data_folder, "bitcoin-binaries")
        if packed_name.endswith("tar.gz"):
            with tarfile.open(packed_name, "r:gz") as so:
                so.extractall(specter.data_folder)
        else:
            with zipfile.ZipFile(packed_name, "r") as zip_ref:
                zip_ref.extractall(specter.data_folder)
        os.rename(
            os.path.join(specter.data_folder, f"bitcoin-{internal_bitcoind_version}"),
            bitcoin_binaries_folder,
        )
        os.remove(packed_name)
        specter.config["rpc"]["user"] = "bitcoin"
        specter.config["rpc"]["password"] = secrets.token_urlsafe(16)
        specter._save()
        if not os.path.exists(specter.config["rpc"]["datadir"]):
            os.makedirs(specter.config["rpc"]["datadir"])
        with open(
            os.path.join(specter.config["rpc"]["datadir"], "bitcoin.conf"),
            "w",
        ) as file:
            file.write(f'\nrpcuser={specter.config["rpc"]["user"]}')
            file.write(f'\nrpcpassword={specter.config["rpc"]["password"]}')
            file.write(f"\nserver=1")
            file.write(f"\nlisten=1")
            file.write(f"\nproxy=127.0.0.1:9050")
            file.write(f"\nbind=127.0.0.1")
            file.write(f"\ntorcontrol=127.0.0.1:9051")
            file.write(f"\ntorpassword={specter.config['torrc_password']}")
        specter.config["bitcoind_internal_version"] = internal_bitcoind_version
        specter._save()
    except Exception as e:
        logger.error(f"Failed to install Bitcoin Core. Error: {e}")
        specter.config["bitcoind_setup"]["error"] = str(e)
        specter._save()
    finally:
        specter.config["bitcoind_setup"]["stage_progress"] = -1
        specter._save()


def setup_bitcoind_directory_thread(specter=None, quicksync=True, pruned=True):
    try:
        if quicksync:
            prunednode_file = os.path.join(
                os.path.join(specter.data_folder, "snapshot-prunednode.zip")
            )
            prunednode_sha256sums_file = os.path.join(
                specter.data_folder, "prunednode-sha256sums.asc"
            )
            download_file(
                specter,
                "https://prunednode.today/latest.zip",
                prunednode_file,
                "bitcoind",
                "Downloading QuickSync files...",
            )
            download_file(
                specter,
                "https://prunednode.today/latest.signed.txt",
                prunednode_sha256sums_file,
                "bitcoind",
                "Downloading Quicksync signature...",
            )
            specter.config["bitcoind_setup"]["stage"] = "Verifying signatures..."
            specter._save()
            with open(prunednode_sha256sums_file, "r") as f:
                signed_sums = f.read()
                prunednode_release_pgp_key, _ = pgpy.PGPKey.from_file(
                    os.path.join(
                        sys._MEIPASS, "static/pruned-node-today-release-pubkey.asc"
                    )
                    if getattr(sys, "frozen", False)
                    else Path(__file__).parent
                    / "../static/pruned-node-today-release-pubkey.asc"
                )
                prunednode_sha256sums_msg = pgpy.PGPMessage.from_file(
                    prunednode_sha256sums_file
                )
                if not prunednode_release_pgp_key.verify(prunednode_sha256sums_msg):
                    raise Exception("Failed to verify prunednode.today PGP signature")
                prunednode_hash = sha256sum(prunednode_file)
                if prunednode_hash not in signed_sums:
                    raise Exception(
                        "Failed to verify prunednode.today hash is in SHA265SUMS.asc"
                    )
                with zipfile.ZipFile(prunednode_file, "r") as zip_ref:
                    zip_ref.extractall(
                        os.path.expanduser(specter.config["rpc"]["datadir"])
                    )
                os.remove(prunednode_file)
                with open(
                    os.path.join(specter.config["rpc"]["datadir"], "bitcoin.conf"),
                    "a",
                ) as file:
                    file.write(f'\nrpcuser={specter.config["rpc"]["user"]}')
                    file.write(f'\nrpcpassword={specter.config["rpc"]["password"]}')
        else:
            with open(
                os.path.join(specter.config["rpc"]["datadir"], "bitcoin.conf"),
                "a",
            ) as file:
                if pruned:
                    file.write(f"\nprune=1000")
                else:
                    file.write(f"\nblockfilterindex=1")

        specter.config["bitcoind_setup"]["stage"] = "Starting up Bitcoin Core..."
        specter._save()

        # Specter's 'bitcoind' attribute will instantiate a BitcoindController as needed
        specter.bitcoind.start_bitcoind(
            datadir=os.path.expanduser(specter.config["rpc"]["datadir"])
        )
        specter.set_bitcoind_pid(specter.bitcoind.bitcoind_proc.pid)
        specter.update_use_external_node(False)
        time.sleep(15)
        success = specter.update_rpc(
            port=8332,
            autodetect=True,
            user=specter.config["rpc"]["user"],
            password=specter.config["rpc"]["password"],
        )
        if not success:
            specter.config["bitcoind_setup"][
                "stage"
            ] = "Failed to start Bitcoin Core..."
            specter._save()
        specter.check()
    except Exception as e:
        logger.exception(f"Failed to setup Bitcoin Core. Error: {e}")
        specter.config["bitcoind_setup"]["error"] = str(e)
        specter._save()
    finally:
        specter.config["bitcoind_setup"]["stage_progress"] = -1
        specter._save()
