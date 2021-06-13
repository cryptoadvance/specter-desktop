import os, time, requests, secrets, platform, tarfile, zipfile, sys, shutil
from ..process_controller.bitcoind_controller import BitcoindPlainController
import pgpy
from pathlib import Path
from .sha256sum import sha256sum
import logging
from .file_download import download_file
from ..specter_error import handle_exception, ExtProcTimeoutException
from .rpcauth import generate_salt, password_to_hmac

logger = logging.getLogger(__name__)


def setup_bitcoind_thread(specter=None, internal_bitcoind_version=""):
    specter.update_setup_status("bitcoind", "STARTING_SETUP")
    try:
        BITCOIND_OS_SUFFIX = {
            "Windows": "win64.zip",
            "Linux": "x86_64-linux-gnu.tar.gz",
            "Darwin": "osx64.tar.gz",
        }
        # ARM Linux devices (e.g. Raspberry Pi 4 == armv7l) need ARM binary
        if platform.system() == "Linux" and "armv" in platform.machine():
            BITCOIND_OS_SUFFIX["Linux"] = "arm-linux-gnueabihf.tar.gz"

        packed_name = (
            os.path.join(
                sys._MEIPASS,
                f"bitcoind/bitcoin-{internal_bitcoind_version}-{BITCOIND_OS_SUFFIX[platform.system()]}",
            )
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
            / f"../../../../pyinstaller/bitcoind/bitcoin-{internal_bitcoind_version}-{BITCOIND_OS_SUFFIX[platform.system()]}"
        )
        bitcoin_binaries_folder = os.path.join(specter.data_folder, "bitcoin-binaries")
        logger.info(f"Unpacking binaries to {bitcoin_binaries_folder}")
        if BITCOIND_OS_SUFFIX[platform.system()].endswith("tar.gz"):
            with tarfile.open(packed_name, "r:gz") as so:
                so.extractall(specter.data_folder)
        else:
            with zipfile.ZipFile(packed_name, "r") as zip_ref:
                zip_ref.extractall(specter.data_folder)
        if os.path.exists(bitcoin_binaries_folder):
            shutil.rmtree(bitcoin_binaries_folder)
        os.rename(
            os.path.join(specter.data_folder, f"bitcoin-{internal_bitcoind_version}"),
            bitcoin_binaries_folder,
        )
        specter.reset_setup("bitcoind")
    except Exception as e:
        logger.error(f"Failed to install Bitcoin Core. Error: {e}")
        handle_exception(e)
        specter.update_setup_error("bitcoind", str(e))


def setup_bitcoind_directory_thread(
    specter=None, quicksync=True, pruned=True, node_alias=""
):
    try:
        if quicksync:
            prunednode_file = os.path.join(
                os.path.join(specter.data_folder, "snapshot-prunednode.zip")
            )
            prunednode_sha256sums_file = os.path.join(
                specter.data_folder, "prunednode-sha256sums.asc"
            )
            logger.info(f"Downloading latest.zip to {prunednode_file}")
            download_file(
                specter,
                "https://prunednode.today/latest.zip",
                prunednode_file,
                "bitcoind",
                "Downloading QuickSync files...",
            )
            logger.info(
                f"Downloading latest.signed.txt to {prunednode_sha256sums_file}"
            )
            download_file(
                specter,
                "https://prunednode.today/latest.signed.txt",
                prunednode_sha256sums_file,
                "bitcoind",
                "Downloading Quicksync signature...",
            )
            specter.update_setup_status("bitcoind", "VERIFY_SIGS")
            logger.info(f"Verifying signatures of {prunednode_sha256sums_file}")
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
                logger.info(
                    f"Unpacking {prunednode_file} to {os.path.expanduser(specter.node_manager.get_by_alias(node_alias).datadir)}"
                )
                with zipfile.ZipFile(prunednode_file, "r") as zip_ref:
                    zip_ref.extractall(
                        os.path.expanduser(
                            specter.node_manager.get_by_alias(node_alias).datadir
                        )
                    )
                os.remove(prunednode_file)

        logger.info(f"Writing bitcoin.conf")
        if not os.path.exists(specter.node_manager.get_by_alias(node_alias).datadir):
            os.makedirs(specter.node_manager.get_by_alias(node_alias).datadir)
        with open(
            os.path.join(
                specter.node_manager.get_by_alias(node_alias).datadir, "bitcoin.conf"
            ),
            "w+",
        ) as file:
            salt = generate_salt(16)
            password_hmac = password_to_hmac(
                salt, specter.node_manager.get_by_alias(node_alias).password
            )
            file.write(
                f"\nrpcauth={specter.node_manager.get_by_alias(node_alias).user}:{salt}${password_hmac}"
            )
            file.write(f"\nserver=1")
            file.write(f"\nlisten=1")
            file.write(f"\onion=127.0.0.1:9050")
            file.write(f"\nbind=127.0.0.1")
            file.write(f"\ntorcontrol=127.0.0.1:9051")
            file.write(f"\ntorpassword={specter.config['torrc_password']}")
            file.write(f"\nfallbackfee=0.0002")
            if quicksync or pruned:
                file.write(f"\nprune=1000")
            else:
                file.write(f"\nblockfilterindex=1")
            file.write(f"\n[test]")
            file.write(f"\nbind=127.0.0.1")
            file.write(f"\n[regtest]")
            file.write(f"\nbind=127.0.0.1")
            file.write(f"\n[signet]")
            file.write(f"\nbind=127.0.0.1")

        specter.update_setup_status("bitcoind", "START_SERVICE")

        # Specter's 'bitcoind' attribute will instantiate a BitcoindController as needed
        logger.info(
            f"Starting up Bitcoin Core... in {os.path.expanduser(specter.node_manager.get_by_alias(node_alias).datadir)}"
        )
        success = specter.node_manager.get_by_alias(node_alias).start(timeout=60)
        specter.update_active_node(specter.node_manager.get_by_alias(node_alias).alias)
        if not success:
            specter.update_setup_status("bitcoind", "FAILED")
            logger.info("No success connecting to Bitcoin Core")
        specter.check()
        specter.reset_setup("bitcoind")
        specter.setup_status["stage"] = "end"
    except ExtProcTimeoutException as e:
        e.check_logfile(
            os.path.join(
                specter.node_manager.get_by_alias(node_alias).datadir, "debug.log"
            )
        )
        logger.error(f"Failed to setup Bitcoin Core. Error: {e}")
        logger.error(e.get_logger_friendly())
        specter.update_setup_error("bitcoind", str(e))
    except Exception as e:
        logger.exception(f"Failed to setup Bitcoin Core. Error: {e}")
        specter.update_setup_error("bitcoind", str(e))
