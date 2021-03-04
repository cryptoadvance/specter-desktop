import os, time, requests, secrets, platform, tarfile, zipfile, sys
from ..bitcoind import BitcoindPlainController
import pgpy
from pathlib import Path
from .sha256sum import sha256sum


def setup_bitcoind_thread(specter=None):
    try:
        BITCOIND_OS_SUFFIX = {
            "Windows": "win64.zip",
            "Linux": "x86_64-linux-gnu.tar.gz",
            "Darwin": "osx64.tar.gz",
        }
        bitcoind_url = f"https://bitcoincore.org/bin/bitcoin-core-0.21.0/bitcoin-0.21.0-{BITCOIND_OS_SUFFIX[platform.system()]}"
        response = specter.requests_session().get(bitcoind_url, stream=True)
        packed_name = os.path.join(
            specter.data_folder,
            f"bitcoind-{BITCOIND_OS_SUFFIX[platform.system()]}",
        )
        with open(packed_name, "wb") as f:
            total_length = float(response.headers["content-length"])
            downloaded = 0.0
            old_progress = 0
            specter.config["bitcoind_setup"][
                "stage"
            ] = "Downloading Bitcoin Core release files..."
            specter._save()
            for chunk in response.iter_content(chunk_size=4096):
                downloaded += len(chunk)
                f.write(chunk)
                new_progress = int((downloaded / total_length) * 10000) / 100
                if new_progress > old_progress:
                    old_progress = new_progress
                    specter.config["bitcoind_setup"]["stage_progress"] = new_progress
                    specter._save()
        specter.config["bitcoind_setup"]["stage"] = "Verifying signatures..."
        specter._save()
        bitcoind_sha256sums_url = (
            "https://bitcoincore.org/bin/bitcoin-core-0.21.0/SHA256SUMS.asc"
        )
        response = specter.requests_session().get(bitcoind_sha256sums_url, stream=True)
        bitcoind_sha256sums_file = os.path.join(
            specter.data_folder, "bitcoind-sha256sums.asc"
        )
        with open(bitcoind_sha256sums_file, "wb") as f:
            total_length = float(response.headers["content-length"])
            for chunk in response.iter_content(chunk_size=4096):
                f.write(chunk)
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

        if packed_name.endswith("tar.gz"):
            with tarfile.open(packed_name, "r:gz") as so:
                so.extractall(
                    path=os.path.join(specter.data_folder, "bitcoin-binaries")
                )
        else:
            with zipfile.ZipFile(packed_name, "r") as zip_ref:
                zip_ref.extractall(
                    os.path.join(specter.data_folder, "bitcoin-binaries")
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
    except Exception:
        pass
    finally:
        specter.config["bitcoind_setup"]["stage_progress"] = -1
        specter._save()


def setup_bitcoind_directory_thread(specter=None, quicksync=True, pruned=True):
    try:
        if quicksync:
            response = specter.requests_session().get(
                "https://prunednode.today/snapshot210224.zip", stream=True
            )
            with open(
                os.path.join(specter.data_folder, "snapshot-prunednode.zip"), "wb"
            ) as f:
                total_length = float(response.headers["content-length"])
                downloaded = 0.0
                old_progress = 0
                specter.config["bitcoind_setup"][
                    "stage"
                ] = "Downloading QuickSync files..."
                specter._save()
                for chunk in response.iter_content(chunk_size=4096):
                    downloaded += len(chunk)
                    f.write(chunk)
                    new_progress = int((downloaded / total_length) * 10000) / 100
                    if new_progress > old_progress:
                        old_progress = new_progress
                        specter.config["bitcoind_setup"][
                            "stage_progress"
                        ] = new_progress
                        specter._save()
            specter.config["bitcoind_setup"]["stage"] = "Verifying signatures..."
            specter._save()
            prunednode_sha256sums_url = (
                "https://prunednode.today/snapshot210224.signed.txt"
            )
            response = specter.requests_session().get(
                prunednode_sha256sums_url, stream=True
            )
            prunednode_sha256sums_file = os.path.join(
                specter.data_folder, "prunednode-sha256sums.asc"
            )
            with open(prunednode_sha256sums_file, "wb") as f:
                total_length = float(response.headers["content-length"])
                for chunk in response.iter_content(chunk_size=4096):
                    f.write(chunk)
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
                prunednode_hash = sha256sum(
                    os.path.join(specter.data_folder, "snapshot-prunednode.zip")
                )
                if prunednode_hash not in signed_sums:
                    raise Exception(
                        "Failed to verify prunednode.today hash is in SHA265SUMS.asc"
                    )
                with zipfile.ZipFile(
                    os.path.join(specter.data_folder, "snapshot-prunednode.zip"), "r"
                ) as zip_ref:
                    zip_ref.extractall(
                        os.path.expanduser(specter.config["rpc"]["datadir"])
                    )
                os.remove(os.path.join(specter.data_folder, "snapshot-prunednode.zip"))
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
        specter.bitcoind = BitcoindPlainController(
            bitcoind_path=specter.bitcoind_path,
            rpcport=8332,
            network="mainnet",
            rpcuser=specter.config["rpc"]["user"],
            rpcpassword=specter.config["rpc"]["password"],
        )
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
        raise e
    finally:
        specter.config["bitcoind_setup"]["stage_progress"] = -1
        specter._save()
