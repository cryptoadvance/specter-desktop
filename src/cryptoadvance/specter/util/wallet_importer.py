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
        # Here's a trimmed version of what an example Electrum file looks like (varies for different wallet types)
        # {
        #     "addr_history": {
        #         "tb1q2zqu0rxg70scs9umwwkjxvq7zdcle2ny6pda8v": [],
        #         "tb1q3p86mshyyrmzp2mw50eqeefxtkz8qfl8tsfgrs": [],
        #         "tb1q46u2rm20rp9rzauxxhdefregggag8cpelh0sqa": [
        #             [
        #                 "14f6bd3dec07c15773b29b4c7f7d3c913197840dfdf567b6b078e224f021b4ac",
        #                 2035683
        #             ],
        #             [
        #                 "23196c7657b60d1fde716c789881ffeee93554b9040c200589c65ceeac051cfb",
        #                 2035683
        #             ]
        #         ],
        #         "tb1q4k59fgwhwey8k4rs2l80p73dwtza0z0gvpjjfc": [],
        #         "tb1q56f5wgc7wqeqygpfgua64gucafp3wp6293ggcg": [],
        #         "tb1q8uysvaz8dysekwws868knvxngh5qfjzrlxqf2j": [
        #             [
        #                 "23196c7657b60d1fde716c789881ffeee93554b9040c200589c65ceeac051cfb",
        #                 2035683
        #             ]
        #         ],
        #         "tb1q8ydkp6qhq79ktwpcwjgt9dl7eer32vpw8gvduy": [
        #             [
        #                 "c9a54c381293a387a8c1c90e542d11cccf42cd0aeab20be3d1fcd10b465dcfde",
        #                 0
        #             ]
        #         ],
        #         "tb1qazyz882jeruqlppfralemm3r07pw6cpk426fhw": [],
        #         "tb1qch2j8ks2qt6thtf7wdpk6v9gquu8tfca6lsh0n": [],
        #         "tb1qcx2dultr5x9dc6jz0ye3wq240xfsdxnnl7vpsm": [
        #             [
        #                 "c9a54c381293a387a8c1c90e542d11cccf42cd0aeab20be3d1fcd10b465dcfde",
        #                 0
        #             ]
        #         ],
        #         "tb1qe686y2y39ncnafpzxxuyfztsy70thl9k4l4crk": [],
        #         "tb1qg33wumlly0mn33s776n8njqek3l2rmy8d97r02": [],
        #         "tb1qh48nqrg595g0vfqcw46kt8aun63t9puap5uww5": [],
        #         "tb1qhlgkkqtdglq64xa8wnwz4446mzj97g0jq9ck65": [],
        #         "tb1qjrd86fxf5chezp2pkjzv8v45rzxe8japwxatt2": [],
        #         "tb1qlty269zlah8h9afx0cxvn05qrzyndvnz28ae6d": [],
        #         "tb1qmcnxezw6qh8vys5sxpwfcqgs2t3gyuy7setdky": [],
        #         "tb1qphhms4gdrfpxh5ed2zekhvnwrk84jk5z56qj82": [],
        #         "tb1qq5huaklp886yyqmxju47xm42dgn5demx5yd848": [],
        #         "tb1qqfp0y5qtf0cx7hzat7r3g69gxx96fkg3vnu4cz": [],
        #         "tb1qqu0p6m8ux64kkflx9wa5sc8k39v8crfsn96qky": [],
        #         "tb1qtu73qp3eneht3rfauwz3rttvs7m7l5lahkq66m": [],
        #         "tb1qtvca6a7gp76km7k5kyg7e6lxhvx3qme6x9p53a": [],
        #         "tb1qtxh9dqg07p32e93vpzhfmv7sgp9je5phps5gpy": [],
        #         "tb1qu0wcfv6n96xm6nx5lczcc4gc5h3fjmsfqsmaar": [],
        #         "tb1qx0ld4mml0hkrwuejmetl77rma08ehc4d75qruy": [],
        #         "tb1qxf7jgjd8k0nmm8g8vclx9zg5drr3hfls3p8c6m": [
        #             [
        #                 "23196c7657b60d1fde716c789881ffeee93554b9040c200589c65ceeac051cfb",
        #                 2035683
        #             ],
        #             [
        #                 "c9a54c381293a387a8c1c90e542d11cccf42cd0aeab20be3d1fcd10b465dcfde",
        #                 0
        #             ]
        #         ],
        #         "tb1qy0pklnhg7rks54gzlu003muyllym3xflkd8e7m": [],
        #         "tb1qyt9mkqgf5gfj0lxhmuzv4xamnra8jlxyhpr5x9": [],
        #         "tb1qz9fe873jvrwd0clcknjgj8z6t3uylc50lgvh2q": []
        #     },
        #     "addresses": {
        #         "change": [
        #             "tb1qxf7jgjd8k0nmm8g8vclx9zg5drr3hfls3p8c6m",
        #             "tb1qcx2dultr5x9dc6jz0ye3wq240xfsdxnnl7vpsm",
        #             "tb1q3p86mshyyrmzp2mw50eqeefxtkz8qfl8tsfgrs",
        #             "tb1qe686y2y39ncnafpzxxuyfztsy70thl9k4l4crk",
        #             "tb1qlty269zlah8h9afx0cxvn05qrzyndvnz28ae6d",
        #             "tb1q56f5wgc7wqeqygpfgua64gucafp3wp6293ggcg",
        #             "tb1qqfp0y5qtf0cx7hzat7r3g69gxx96fkg3vnu4cz",
        #             "tb1qhlgkkqtdglq64xa8wnwz4446mzj97g0jq9ck65",
        #             "tb1q4k59fgwhwey8k4rs2l80p73dwtza0z0gvpjjfc",
        #             "tb1qq5huaklp886yyqmxju47xm42dgn5demx5yd848"
        #         ],
        #         "receiving": [
        #             "tb1q46u2rm20rp9rzauxxhdefregggag8cpelh0sqa",
        #             "tb1q8uysvaz8dysekwws868knvxngh5qfjzrlxqf2j",
        #             "tb1qtvca6a7gp76km7k5kyg7e6lxhvx3qme6x9p53a",
        #             "tb1q8ydkp6qhq79ktwpcwjgt9dl7eer32vpw8gvduy",
        #             "tb1qtu73qp3eneht3rfauwz3rttvs7m7l5lahkq66m",
        #             "tb1qu0wcfv6n96xm6nx5lczcc4gc5h3fjmsfqsmaar",
        #             "tb1qx0ld4mml0hkrwuejmetl77rma08ehc4d75qruy",
        #             "tb1qazyz882jeruqlppfralemm3r07pw6cpk426fhw",
        #             "tb1qz9fe873jvrwd0clcknjgj8z6t3uylc50lgvh2q",
        #             "tb1qy0pklnhg7rks54gzlu003muyllym3xflkd8e7m",
        #             "tb1qh48nqrg595g0vfqcw46kt8aun63t9puap5uww5",
        #             "tb1qjrd86fxf5chezp2pkjzv8v45rzxe8japwxatt2",
        #             "tb1qg33wumlly0mn33s776n8njqek3l2rmy8d97r02",
        #             "tb1qmcnxezw6qh8vys5sxpwfcqgs2t3gyuy7setdky",
        #             "tb1q2zqu0rxg70scs9umwwkjxvq7zdcle2ny6pda8v",
        #             "tb1qyt9mkqgf5gfj0lxhmuzv4xamnra8jlxyhpr5x9",
        #             "tb1qphhms4gdrfpxh5ed2zekhvnwrk84jk5z56qj82",
        #             "tb1qqu0p6m8ux64kkflx9wa5sc8k39v8crfsn96qky",
        #             "tb1qch2j8ks2qt6thtf7wdpk6v9gquu8tfca6lsh0n",
        #             "tb1qtxh9dqg07p32e93vpzhfmv7sgp9je5phps5gpy"
        #         ]
        #     },
        #     "fiat_value": {},
        #     "frozen_coins": {},
        #     "imported_channel_backups": {},
        #     "keystore": {
        #         "derivation": "m/0'",
        #         "pw_hash_version": 1,
        #         "root_fingerprint": "8e0c95ad",
        #         "seed": "toss despair unaware moral shield process morning cook enlist park talent snack",
        #         "seed_type": "segwit",
        #         "type": "bip32",
        #         "xprv": "...",
        #         "xpub": "vpub5VGXXixD2pHLFtcKtCF57e8mx2JW6fie8VydXijC8sRKAL4RshgjEmzbmV915NeVB9pd23DVYem6zWM7HXFLNwaffNVHowdD9SJWwESyQhp"
        #     },
        #     "labels": {
        #         "14f6bd3dec07c15773b29b4c7f7d3c913197840dfdf567b6b078e224f021b4ac": "this is a txid label",
        #         "c9a54c381293a387a8c1c90e542d11cccf42cd0aeab20be3d1fcd10b465dcfde": "this is an address label",
        #         "tb1q8ydkp6qhq79ktwpcwjgt9dl7eer32vpw8gvduy": "this is an address label"
        #     },
        #     "lightning_payments": {},
        #     "lightning_preimages": {},
        #     "onchain_channel_backups": {},
        #     "qt-console-history": [],
        #     "seed_type": "segwit",
        #     "seed_version": 41,
        #     "stored_height": 2035683,
        #     "submarine_swaps": {},
        #     "use_encryption": false,
        #     "wallet_type": "standard",
        # }
        elif "keystore" in wallet_data:
            wallet_name = wallet_data["keystore"].get("label", "Electrum Wallet")

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
                    "type": wallet_data["keystore"].get("hw_type", "other"),
                    "label": wallet_data["keystore"].get("label", "Electrum Wallet"),
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
