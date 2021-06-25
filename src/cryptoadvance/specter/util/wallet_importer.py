import json
import logging
import requests
from cryptoadvance.specter.managers.wallet_manager import WalletManager

from cryptoadvance.specter.specter_error import SpecterError

from ..helpers import is_testnet
from .descriptor import AddChecksum, Descriptor

logger = logging.getLogger(__name__)


class WalletImporter:
    """A class to create Wallets easily by json"""

    def __init__(self, wallet_json, specter, device_manager=None):
        """this will analyze the wallet_json and specifies self. ...:
        * wallet_name
        * recv_descriptor
        * cosigners_types
        from recv_descriptor and specter.chain:
        * descriptor
        from descriptor:
        * keys
        * cosigners
        * unknown_cosigners
        * unknown_cosigners_types
        """
        if device_manager is None:
            device_manager = specter.device_manager
        try:
            self.wallet_data = json.loads(wallet_json)
            (
                self.wallet_name,
                self.recv_descriptor,
                self.cosigners_types,
            ) = WalletImporter.parse_wallet_data_import(self.wallet_data)
        except Exception as e:
            logger.warning(f"Trying to import: {wallet_json}")
            raise SpecterError(f"Unsupported wallet import format:{e}")
        try:
            self.descriptor = Descriptor.parse(
                AddChecksum(self.recv_descriptor.split("#")[0]),
                testnet=is_testnet(specter.chain),
            )
            if self.descriptor is None:
                raise SpecterError(f"Invalid wallet descriptor. (returns None)")
        except Exception as e:
            raise SpecterError(f"Invalid wallet descriptor: {e}")
        if self.wallet_name in specter.wallet_manager.wallets_names:
            raise SpecterError(f"Wallet with the same name already exists")
        (
            self.keys,
            self.cosigners,
            self.unknown_cosigners,
            self.unknown_cosigners_types,
        ) = self.descriptor.parse_signers(device_manager.devices, self.cosigners_types)
        self.wallet_type = "multisig" if self.descriptor.multisig_N > 1 else "simple"

    def create_nonexisting_signers(self, device_manager, request_form):
        """creates non existinging signer via the device_manager
        request_form is a dict which needs (where X is an integer):
        * unknown_cosigner_X_name
        * unknown_cosigner_X_type
        Apart from adding the devices, it'll also modify:
        * self.keys and
        * self.cosigners
        """
        for i, (unknown_cosigner_key, label) in enumerate(self.unknown_cosigners):
            unknown_cosigner_name = request_form["unknown_cosigner_{}_name".format(i)]
            unknown_cosigner_type = request_form.get(
                "unknown_cosigner_{}_type".format(i), "other"
            )

            device = device_manager.add_device(
                name=unknown_cosigner_name,
                device_type=unknown_cosigner_type,
                keys=[unknown_cosigner_key],
            )
            logger.info(f"Creating device {device}")
            self.keys.append(unknown_cosigner_key)
            self.cosigners.append(device)

    def create_wallet(self, wallet_manager):
        """creates the wallet. Assumes all devices are there (create with create_nonexisting_signers)
        will also keypoolrefill and import_labels
        """
        try:
            self.wallet = wallet_manager.create_wallet(
                name=self.wallet_name,
                sigs_required=self.descriptor.multisig_M,
                key_type=self.descriptor.address_type,
                keys=self.keys,
                devices=self.cosigners,
            )
        except Exception as e:
            raise SpecterError(f"Failed to create wallet: {e}")
        logger.info(f"Created Wallet {self.wallet}")
        self.wallet.keypoolrefill(0, self.wallet.IMPORT_KEYPOOL, change=False)
        self.wallet.keypoolrefill(0, self.wallet.IMPORT_KEYPOOL, change=True)
        self.wallet.import_labels(self.wallet_data.get("labels", {}))
        return self.wallet

    def rescan_as_needed(self, specter):
        """will rescan the created wallet"""
        if not hasattr(self, "wallet"):
            raise Exception("called rescan_as_needed before create_wallet")
        potential_errors = None
        try:
            # get min of the two
            # if the node is still syncing
            # and the first block with tx is not there yet
            startblock = min(
                self.wallet_data.get("blockheight", specter.info.get("blocks", 0)),
                specter.info.get("blocks", 0),
            )
            # check if pruned
            if specter.info.get("pruned", False):
                newstartblock = max(startblock, specter.info.get("pruneheight", 0))
                if newstartblock > startblock:
                    potential_errors = SpecterError(
                        f"Using pruned node - we will only rescan from block {newstartblock}"
                    )
                    startblock = newstartblock
            self.wallet.rpc.rescanblockchain(startblock, timeout=1)
            logger.info("Rescanning Blockchain ...")
        except requests.exceptions.ReadTimeout:
            # this is normal behavior in our usecase
            pass
        except Exception as e:
            logger.error("Exception while rescanning blockchain: %r" % e)
            if potential_errors:
                potential_errors = SpecterError(
                    potential_errors
                    + " and "
                    + "Failed to perform rescan for wallet: %r" % e
                )
        self.wallet.getdata()
        if potential_errors:
            raise potential_errors

    @property
    def wallet_json(self):
        """self.wallet_data in json format"""
        return json.dumps(self.wallet_data)

    @classmethod
    def parse_wallet_data_import(cls, wallet_data):
        """Parses wallet JSON for import, takes JSON in a supported format
        and returns a tuple of wallet name, wallet descriptor, and cosigners types (electrum
        and newer Specter backups).
        Supported formats: Specter, Electrum, Account Map (Fully Noded, Gordian, Sparrow etc.)
        """
        cosigners_types = []

        # Specter-DIY format
        if "recv_descriptor" in wallet_data:
            wallet_name = wallet_data.get("name", "Imported Wallet")
            recv_descriptor = wallet_data.get("recv_descriptor", None)

        # Electrum multisig
        elif "x1/" in wallet_data:
            i = 1
            xpubs = ""
            while "x{}/".format(i) in wallet_data:
                d = wallet_data["x{}/".format(i)]
                xpubs += "[{}]{}/0/*,".format(
                    d["derivation"].replace("m", d["root_fingerprint"]), d["xpub"]
                )
                cosigners_types.append({"type": d["hw_type"], "label": d["label"]})
                i += 1
            xpubs = xpubs.rstrip(",")

            if "xpub" in wallet_data["x1/"]:
                wallet_type = WalletImporter.wallet_type_by_slip132_xpub(
                    wallet_data["x1/"]["xpub"]
                )
            else:
                raise Exception('"xpub" not found in "x1/" in Electrum backup json')

            required_sigs = int(wallet_data.get("wallet_type").split("of")[0])
            recv_descriptor = "{}(sortedmulti({}, {}))".format(
                wallet_type, required_sigs, xpubs
            )
            wallet_name = "Electrum {} of {}".format(required_sigs, i - 1)

        # Electrum singlesig
        elif "keystore" in wallet_data:
            wallet_name = wallet_data["keystore"]["label"]

            if "xpub" in wallet_data["keystore"]:
                wallet_type = cls.wallet_type_by_slip132_xpub(
                    wallet_data["keystore"]["xpub"], is_multisig=False
                )
            else:
                raise Exception(
                    '"xpub" not found in "keystore" in Electrum backup json'
                )
            recv_descriptor = "{}({})".format(
                wallet_type,
                "[{}]{}/0/*,".format(
                    wallet_data["keystore"]["derivation"].replace(
                        "m", wallet_data["keystore"]["root_fingerprint"]
                    ),
                    wallet_data["keystore"]["xpub"],
                ),
            )
            cosigners_types = [
                {
                    "type": wallet_data["keystore"]["hw_type"],
                    "label": wallet_data["keystore"]["label"],
                }
            ]

        # Current Specter backups
        else:
            # Newer exports are able to reinitialize device types but stay backwards
            #   compatible with older backups.
            if "devices" in wallet_data:
                cosigners_types = wallet_data["devices"]

            wallet_name = wallet_data.get("label", "Imported Wallet")
            recv_descriptor = wallet_data.get("descriptor", None)

        return (wallet_name, recv_descriptor, cosigners_types)

    @classmethod
    def wallet_type_by_slip132_xpub(cls, xpub, is_multisig=True):
        """
        see: https://github.com/satoshilabs/slips/blob/master/slip-0132.md
        Electrum backups use SLIP-132 but note that other wallets don't make the same
        guarantee.
        """
        if is_multisig:
            if xpub.startswith("xpub") or xpub.startswith("tpub"):
                return "sh"
            elif xpub.startswith("Ypub") or xpub.startswith("Upub"):
                return "sh-wsh"
            elif xpub.startswith("Zpub") or xpub.startswith("Vpub"):
                return "wsh"
        else:
            if xpub.startswith("xpub") or xpub.startswith("tpub"):
                return "pkh"
            elif xpub.startswith("ypub") or xpub.startswith("upub"):
                return "sh-wpkh"
            elif xpub.startswith("zpub") or xpub.startswith("vpub"):
                return "wpkh"
        raise Exception(f"Unhandled xpub type: {xpub}")
