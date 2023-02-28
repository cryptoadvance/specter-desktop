import json
import logging

import requests
from embit.descriptor import Descriptor
from embit.descriptor import Key as DescriptorKey
from embit.descriptor.arguments import AllowedDerivation
from embit.liquid.descriptor import LDescriptor
from flask_babel import lazy_gettext as _

from cryptoadvance.specter.device import Device

from ..key import Key
from ..managers.wallet_manager import WalletManager
from ..server_endpoints import flash
from ..specter_error import SpecterError

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
        DescriptorCls = LDescriptor if specter.is_liquid else Descriptor
        if device_manager is None:
            device_manager = specter.device_manager
        try:
            self.wallet_data = json.loads(wallet_json)
            (
                self.wallet_name,
                recv_descriptor,
                self.cosigners_types,
            ) = WalletImporter.parse_wallet_data_import(self.wallet_data)
        except Exception as e:
            logger.warning(f"Trying to import: {wallet_json}")
            raise SpecterError(f"Unsupported wallet import format:{e}")
        try:
            self.descriptor = DescriptorCls.from_string(recv_descriptor)
            self.check_descriptor()
        except ValueError as e:
            raise SpecterError(f"{e}: {recv_descriptor}")
        if self.wallet_name in specter.wallet_manager.wallets_names:
            raise SpecterError(f"Wallet with the same name already exists")
        (
            self.keys,
            self.cosigners,
            self.unknown_cosigners,
            self.unknown_cosigners_types,
        ) = self.parse_signers(device_manager.devices, self.cosigners_types)
        try:
            self.check_chain(specter.node)
        except Exception as e:
            logger.exception(e)
            raise SpecterError(f"Invalid chain: {e}")
        self.wallet_type = "multisig" if self.descriptor.is_basic_multisig else "simple"

    def check_chain(self, node):

        cosigner: Device
        for cosigner in self.cosigners:

            key_chain_list = [key.is_testnet for key in cosigner.keys]
            logger.debug(key_chain_list)
            if node.is_testnet not in key_chain_list:
                raise SpecterError(
                    f"The device {cosigner.alias} does not have any key for the chain {node.chain}!"
                )
        for key, label in self.unknown_cosigners:
            if key.is_testnet != node.is_testnet:
                raise SpecterError(
                    f"The device {label} has at least one key for the chain {key.metadata['chain'] } whereas your node is on the chain: {node.chain}!"
                )
        key: Key
        for key in self.keys:
            if key.is_testnet != node.is_testnet:
                raise SpecterError(
                    f"The key {key} belongs to the chain {key.metadata['chain'] } but your node is on the chain {node.chain}!"
                )

    def check_descriptor(self):
        # Sparrow fix: if all keys have None as allowed derivation - set allowed derivation to [0, None]
        if all(
            [
                k.allowed_derivation is None or k.allowed_derivation.indexes == []
                for k in self.descriptor.keys
                if k.is_extended
            ]
        ):
            for k in self.descriptor.keys:
                if k.is_extended:
                    k.allowed_derivation = AllowedDerivation([0, None])

        # Check that all keys are HD keys and all have default derivation
        for key in self.descriptor.keys:
            if not key.is_extended:
                raise SpecterError("Only HD keys are supported in descriptor")
            if key.allowed_derivation is None or key.allowed_derivation.indexes != [
                0,
                None,
            ]:
                raise SpecterError(
                    "Descriptor key has wrong derivation, only /0/* derivation is supported."
                )

    def parse_signers(self, devices, cosigners_types):
        """returns:
            * keys:
                * keys which are already existing in the device_manager
                * keys:[<cryptoadvance.specter.key.Key object at 0x7fda8451e0e0>]
            # cosigners:
                * [<cryptoadvance.specter.devices.generic.GenericDevice object at 0x7fda8451fcd0>]
        # unknown_cosigners:[(<cryptoadvance.specter.key.Key object at 0x7fda8451e830>, 'Signer - K'), (<cryptoadvance.specter.key.Key object at 0x7fda94235570>, 'Signer - Tired no WP')]

        """
        keys = []
        cosigners = []
        unknown_cosigners = []
        unknown_cosigners_types = []

        for i, descriptor_key in enumerate(self.descriptor.keys):
            # remove derivation from the key for comparison
            account_key = DescriptorKey.from_string(str(descriptor_key))
            account_key.allowed_derivation = None
            # Specter Key class
            desc_key = Key.parse_xpub(str(account_key))
            cosigner_found = False
            for cosigner in devices.values():
                for key in cosigner.keys:
                    # check key matches
                    if key.to_string(slip132=False) == desc_key.to_string(
                        slip132=False
                    ):
                        keys.append(key)
                        cosigners.append(cosigner)
                        cosigner_found = True
                        break
                if cosigner_found:
                    break
            if not cosigner_found:
                if len(cosigners_types) > i:
                    unknown_cosigners.append((desc_key, cosigners_types[i]["label"]))
                else:
                    unknown_cosigners.append((desc_key, None))
                if len(unknown_cosigners) > len(cosigners_types):
                    unknown_cosigners_types.append("other")
                else:
                    unknown_cosigners_types.append(cosigners_types[i]["type"])
        logger.debug("parse_signers returning:")
        logger.debug(f"keys:{keys}")
        logger.debug(f"cosigners:{cosigners}")
        logger.debug(f"unknown_cosigners:{unknown_cosigners}")
        logger.debug(f"unknown_cosigners_types:{unknown_cosigners_types}")
        return (keys, cosigners, unknown_cosigners, unknown_cosigners_types)

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

    @property
    def address_type(self):
        if self.descriptor.is_taproot:
            return "tr"
        res = ""
        if self.descriptor.miniscript:
            if self.descriptor.wsh:
                res = "wsh"
        else:
            if self.descriptor.wpkh:
                res = "wpkh"
            else:
                return "pkh"
        if self.descriptor.sh:
            if res:
                return f"sh-{res}"
            else:
                return "sh"
        return res

    @property
    def sigs_required(self):
        sigs_required = 1
        if self.descriptor.is_basic_multisig:
            sigs_required = self.descriptor.miniscript.args[0].num
        return sigs_required

    @property
    def sigs_total(self):
        return len(self.descriptor.keys)

    def create_wallet(self, wallet_manager):
        """creates the wallet. Assumes all devices are there (create with create_nonexisting_signers)
        will also keypoolrefill and import_labels
        """
        try:
            kwargs = {}
            if (
                isinstance(self.descriptor, LDescriptor)
                and self.descriptor.blinding_key
            ):
                kwargs["blinding_key"] = self.descriptor.blinding_key.key

            self.wallet = wallet_manager.create_wallet(
                name=self.wallet_name,
                sigs_required=self.sigs_required,
                key_type=self.address_type,
                keys=self.keys,
                devices=self.cosigners,
                **kwargs,
            )
        except Exception as e:
            logger.exception(e)
            raise SpecterError(f"Failed to create wallet: {e} (check logs for details)")
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
            self.wallet.rpc.rescanblockchain(startblock, no_wait=True)
            logger.info("Rescanning Blockchain ...")
        except Exception as e:
            logger.exception("Exception while rescanning blockchain")
            if potential_errors:
                potential_errors = SpecterError(
                    str(potential_errors)
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

        # Specter-Desktop format
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
                if "hw_type" in d:
                    cosigners_types.append({"type": d["hw_type"], "label": d["label"]})
                else:  # this can occcur if no hardware wallet was used, but the seed is available
                    cosigners_types.append(
                        {"type": "electrum", "label": f"Electrum Multisig {i}"}
                    )
                    if "seed" in d:
                        flash(
                            _(
                                "The Electrum wallet contains a seed. The seed will not be imported."
                            ),
                            "warning",
                        )
                i += 1
            xpubs = xpubs.rstrip(",")

            if "xpub" in wallet_data["x1/"]:
                wallet_type = WalletImporter.wallet_type_by_slip132_xpub(
                    wallet_data["x1/"]["xpub"]
                )
            else:
                raise SpecterError('"xpub" not found in "x1/" in Electrum backup json')

            required_sigs = int(wallet_data.get("wallet_type").split("of")[0])
            recv_descriptor = "{}(sortedmulti({},{}))".format(
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
                raise SpecterError(
                    '"xpub" not found in "keystore" in Electrum backup json'
                )
            recv_descriptor = "{}({})".format(
                wallet_type,
                "[{}]{}/0/*".format(
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
            if "seed" in wallet_data["keystore"]:
                flash(
                    _(
                        "The Electrum wallet contains a seed. The seed will not be imported."
                    ),
                    "warning",
                )
        # Current Specter backups
        else:
            # Newer exports are able to reinitialize device types but stay backwards
            #   compatible with older backups.
            if "devices" in wallet_data:
                cosigners_types = wallet_data["devices"]

            wallet_name = wallet_data.get("label", "Imported Wallet")
            recv_descriptor = wallet_data.get("descriptor", None)

        if wallet_name is None:
            raise SpecterError(
                f"Couldn't find 'name' in wallet json (alias: {wallet_data.get('alias','also not existing')})."
            )
        if recv_descriptor is None:
            raise SpecterError("Couldn't find 'recv_descriptor' in wallet json.")

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
