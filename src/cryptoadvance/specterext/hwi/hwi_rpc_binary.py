import json
import logging
from cryptoadvance.specter.helpers import locked
from cryptoadvance.specter.util.shell import run_shell
from cryptoadvance.specter.util.xpub import convert_xpub_prefix

from .hwi_rpc import AbstractHWIBridge, hwilock

logger = logging.getLogger(__name__)


class HWIBinaryBridge(AbstractHWIBridge):
    """An Implementation of a HWIBridge which is using a binary executable
    of HWI
    """

    hwi_path = "/home/kim/.specter_dev/binaries/hwi"
    device_pathes = {}

    def run_hwi(self, cmd):
        if True:
            logger.debug(f"cmd: {cmd}")
        return run_shell(cmd)

    def device_path(self, device_type):
        if not self.device_pathes["device_type"]:
            res = self.enumerate()
            for device in res:
                if device["type"] == device_type:
                    self.device_pathes[device_type] = device["path"]
        return self.device_pathes.get(device_type, None)

    @locked(hwilock)
    def enumerate(self, passphrase="", chain=""):
        return self._enumerate(passphrase=passphrase, chain=chain)

    def _enumerate(self, passphrase="", chain=""):
        """
        Returns a list of all connected devices (dicts).
        Standard HWI enumerate() command + Specter.
        """
        devices = []

        result = self.run_hwi([self.hwi_path, "enumerate"])
        if result["code"] != 0:
            raise Exception(result["err"])
        logger.debug(result["out"])
        devs = json.loads(result["out"])
        # extracting fingerprint info
        for dev in devs:
            # we can't get fingerprint if device is locked
            if "needs_pin_sent" in dev and dev["needs_pin_sent"]:
                continue
            # we can't get fingerprint if passphrase is not provided
            if (
                "needs_passphrase_sent" in dev
                and dev["needs_passphrase_sent"]
                and not passphrase
            ):
                continue
            client = None
        devices += devs
        self.devices = devices
        return devices

    def detect_device(
        self, device_type=None, path=None, fingerprint=None, rescan_devices=False
    ):
        """
        Returns a hardware wallet details
        with specific fingerprint/ path/ type
        or None if not connected.
        If found multiple devices return only one.
        """
        pass

    @locked(hwilock)
    def toggle_passphrase(self, device_type=None, path=None, passphrase="", chain=""):
        super().toggle_passphrase(
            device_type=device_type, path=path, passphrase=passphrase, chain=chain
        )
        cmd = [self.hwi_path]
        if device_type:
            cmd.extend(["--device-type", device_type])
        if path:
            cmd.extend(["--device-path", path])
        cmd.append("togglepassphrase")
        res = run_shell(cmd)
        if res["code"] != 0:
            logger.error(f"Got an issue with this call: {cmd}")
            logger.error(f"{' '.join(cmd)}")
            raise Exception(res["err"])
        return json.loads(res["out"])

    @locked(hwilock)
    def prompt_pin(self, device_type=None, path=None, passphrase="", chain=""):
        super().prompt_pin(
            device_type=device_type, path=path, passphrase=passphrase, chain=chain
        )
        cmd = [self.hwi_path]
        if device_type:
            cmd.extend(["--device-type", device_type])
        if path:
            cmd.extend(["--device-path", path])
        cmd.append("promptpin")
        res = run_shell(cmd)
        if res["code"] != 0:
            logger.error(f"Got an issue with this call: {cmd}")
            logger.error(f"{' '.join(cmd)}")
            raise Exception(res["err"])
        return json.loads(res["out"])

    @locked(hwilock)
    def send_pin(self, pin="", device_type=None, path=None, passphrase="", chain=""):
        super().send_pin(
            pin=pin,
            device_type=device_type,
            path=path,
            passphrase=passphrase,
            chain=chain,
        )
        cmd = [self.hwi_path]
        if device_type:
            cmd.extend(["--device-type", device_type])
        if path is None:
            path = [dev for dev in self.devices if dev["type"] == device_type][0][
                "path"
            ]
        cmd.extend(["--device-path", path])
        cmd.append("sendpin")
        cmd.append(pin)
        res = run_shell(cmd)
        if res["code"] != 0:
            logger.error(f"Got an issue with this call: {cmd}")
            raise Exception(res["err"])
        return json.loads(res["out"])

    @locked(hwilock)
    def extract_xpubs(
        self,
        account=0,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        client = HwiBinaryClient(
            self, self.hwi_path, device_type=device_type, device_path=path
        )
        # with self._get_client(
        #     device_type=device_type,
        #     fingerprint=fingerprint,
        #     path=path,
        #     passphrase=passphrase,
        #     chain=chain,
        # ) as client:
        xpubs = self._extract_xpubs_from_client(client, account)
        return xpubs

    @locked(hwilock)
    def extract_xpub(
        self,
        derivation=None,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        pass

    @locked(hwilock)
    def display_address(
        self,
        descriptor="",
        xpubs_descriptor="",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        pass

    @locked(hwilock)
    def sign_tx(
        self,
        psbt="",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        pass

    @locked(hwilock)
    def sign_message(
        self,
        message="",
        derivation_path="m",
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        pass

    @locked(hwilock)
    def extract_master_blinding_key(
        self,
        device_type=None,
        path=None,
        fingerprint=None,
        passphrase="",
        chain="",
    ):
        pass

    def _extract_xpubs_from_client(self, client, account=0):
        """Same than HwiBridge._extract_xpubs_from_client but needs to do that without
        the hwilib dependencies
        """
        try:
            xpubs = ""
            # Client will be configured for testnet if our Specter instance is
            #   currently connected to testnet. This will prevent us from
            #   getting mainnet xpubs unless we set is_testnet here:
            client.chain = "main"

            master_fpr = client.get_master_fingerprint()

            # HWI calls to client.get_pubkey_at_path() return "xpub"-prefixed xpubs
            # regardless of derivation path. Update to match SLIP-0132 prefixes.
            # See:
            #   https://github.com/satoshilabs/slips/blob/master/slip-0132.md

            # Extract nested Segwit
            try:
                xpub = client.get_pubkey_at_path("m/49h/0h/{}h".format(account))
                ypub = convert_xpub_prefix(xpub, b"\x04\x9d\x7c\xb2")
                xpubs += "[{}/49'/0'/{}']{}\n".format(master_fpr, account, ypub)
            except Exception as e:
                logger.warning(
                    f"Failed to import Nested Segwit singlesig mainnet key. Error {e}"
                )
                logger.exception(e)

            try:
                # native Segwit
                xpub = client.get_pubkey_at_path("m/84h/0h/{}h".format(account))
                zpub = convert_xpub_prefix(xpub, b"\x04\xb2\x47\x46")
                xpubs += "[{}/84'/0'/{}']{}\n".format(master_fpr, account, zpub)
            except Exception as e:
                logger.warning(
                    f"Failed to import native Segwit singlesig mainnet key: {e}"
                )
                logger.exception(e)

            try:
                # Multisig nested Segwit
                xpub = client.get_pubkey_at_path("m/48h/0h/{}h/1h".format(account))
                Ypub = convert_xpub_prefix(xpub, b"\x02\x95\xb4\x3f")
                xpubs += "[{}/48'/0'/{}'/1']{}\n".format(master_fpr, account, Ypub)
            except Exception as e:
                logger.warning(
                    f"Failed to import Nested Segwit multisig mainnet key: {e}"
                )
                logger.exception(e)

            try:
                # Multisig native Segwit
                xpub = client.get_pubkey_at_path("m/48h/0h/{}h/2h".format(account))
                Zpub = convert_xpub_prefix(xpub, b"\x02\xaa\x7e\xd3")
                xpubs += "[{}/48'/0'/{}'/2']{}\n".format(master_fpr, account, Zpub)
            except Exception as e:
                logger.warning(
                    f"Failed to import native Segwit multisig mainnet key {e}"
                )
                logger.exception(e)

            # And testnet
            client.chain = "testnet"

            try:
                # Testnet nested Segwit
                xpub = client.get_pubkey_at_path("m/49h/1h/{}h".format(account))
                upub = convert_xpub_prefix(xpub, b"\x04\x4a\x52\x62")
                xpubs += "[{}/49'/1'/{}']{}\n".format(master_fpr, account, upub)
            except Exception as e:
                logger.warning(
                    f"Failed to import Nested Segwit singlesig testnet key: {e}"
                )
                logger.exception(e)

            try:
                # Testnet native Segwit
                xpub = client.get_pubkey_at_path("m/84h/1h/{}h".format(account))
                vpub = convert_xpub_prefix(xpub, b"\x04\x5f\x1c\xf6")
                xpubs += "[{}/84'/1'/{}']{}\n".format(master_fpr, account, vpub)
            except Exception as e:
                logger.warning(
                    f"Failed to import native Segwit singlesig testnet key: {e}"
                )
                logger.exception(e)

            try:
                # Testnet multisig nested Segwit
                xpub = client.get_pubkey_at_path("m/48h/1h/{}h/1h".format(account))
                Upub = convert_xpub_prefix(xpub, b"\x02\x42\x89\xef")
                xpubs += "[{}/48'/1'/{}'/1']{}\n".format(master_fpr, account, Upub)
            except Exception as e:
                logger.warning(
                    f"Failed to import Nested Segwit multisigsig testnet key: {e}"
                )
                logger.exception(e)

            try:
                # Testnet multisig native Segwit
                xpub = client.get_pubkey_at_path("m/48h/1h/{}h/2h".format(account))
                Vpub = convert_xpub_prefix(xpub, b"\x02\x57\x54\x83")
                xpubs += "[{}/48'/1'/{}'/2']{}\n".format(master_fpr, account, Vpub)
            except Exception as e:
                logger.warning(
                    f"Failed to import native Segwit multisig testnet key: {e}"
                )
                logger.exception(e)

            # Do proper cleanup otherwise have to reconnect device to access again
            client.close()
        except Exception as e:
            if client:
                client.close()
            raise e
        return xpubs


class HwiBinaryClient:
    """A class which behaves like a HWI client but uses the HWI binary in order to get the result
    this is used in HWIBinaryBridge._extract_xpubs_from_client as you can inject a "client" there.

    """

    def __init__(
        self,
        hwi: HWIBinaryBridge,
        hwi_path,
        device_type=None,
        device_path=None,
        passphrase="",
    ):
        self.hwi = hwi
        self.hwi_path = hwi_path
        self.device_type = device_type
        self.device_path = device_path
        self.passphrase = passphrase
        self.chain = "main"  # {main,test,regtest,signet}

    def get_pubkey_at_path(self, derivation_path):
        cmd = [self.hwi_path]
        if self.device_type:
            cmd.extend(["--device-type", self.device_type])
        if self.device_path:
            cmd.extend(["--device-path", self.device_path])

        cmd.append("getxpub")
        cmd.append(derivation_path)

        res = run_shell(cmd)
        if res["code"] != 0:
            logger.error(f"Got an issue with this call: {cmd}")
            raise Exception(res["err"])
        return json.loads(res["out"])["xpub"]

    def get_master_fingerprint(self):
        devices = self.hwi._enumerate(passphrase=self.passphrase, chain=self.chain)
        return devices[0]["fingerprint"]

    def close(self):
        """Just to mimick properly the client"""
        pass
