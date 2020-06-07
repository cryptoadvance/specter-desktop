import copy, json, logging, os, random
from .helpers import deep_update
from .rpc import autodetect_cli_confs, RpcError
from .rpc_cache import BitcoinCLICached
from .device_manager import DeviceManager
from .wallet_manager import WalletManager


logger = logging.getLogger(__name__)

def get_cli(conf):
    if "user" not in conf or conf["user"]=="":
        conf["autodetect"] = True
    if conf["autodetect"]:
        if "port" in conf:
            cli_conf_arr = autodetect_cli_confs(port=conf["port"])
        else:
            cli_conf_arr = autodetect_cli_confs()
        if len(cli_conf_arr) > 0:
            cli = BitcoinCLICached(**cli_conf_arr[0])
        else:
            return None
    else:
        cli = BitcoinCLICached(conf["user"], conf["password"], 
                          host=conf["host"], port=conf["port"], protocol=conf["protocol"])
    return cli

class Specter:
    ''' A central Object mostly holding app-settings '''
    CONFIG_FILE_NAME = "config.json"
    def __init__(self, data_folder="./data", config={}):
        if data_folder.startswith("~"):
            data_folder = os.path.expanduser(data_folder)
        self.data_folder = data_folder
        self.cli = None
        self.device_manager = None
        self.wallet_manager = None

        self.file_config = None  # what comes from config file
        self.arg_config = config # what comes from arguments

        # default config
        self.config = {
            "rpc": {
                "autodetect": True,
                "user": "",
                "password": "",
                "port": "",
                "host": "localhost",        # localhost
                "protocol": "http"          # https for the future
            },
            "auth": "none",
            "explorers": {
                "main": "",
                "test": "",
                "regtest": "",
                "signet": ""
            },
            "hwi_bridge_url": "/hwi/api/",
            # unique id that will be used in wallets path in Bitcoin Core
            # empty by default for backward-compatibility
            "uid": "",
        }

        # creating folders if they don't exist
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)

        self._info = { "chain": None }
        # health check: loads config and tests rpc
        self.check()

    def check(self):

        # if config.json file exists - load from it
        if os.path.isfile(os.path.join(self.data_folder, "config.json")):
            with open(os.path.join(self.data_folder, "config.json"), "r") as f:
                self.file_config = json.loads(f.read())
                deep_update(self.config, self.file_config)
        # otherwise - create one and assign unique id
        else:
            if self.config["uid"] == "":
                self.config["uid"] = random.randint(0,256**8).to_bytes(8,'big').hex()
            self._save()

        # init arguments
        deep_update(self.config, self.arg_config) # override loaded config
        
        self.cli = get_cli(self.config["rpc"])
        self._is_configured = (self.cli is not None)
        self._is_running = False
        if self._is_configured:
            try:
                self._info = self.cli.getblockchaininfo()
                self._is_running = True
            except Exception as e:
                logger.error("Exception %s while specter.check()" % e)
                pass

        if not self._is_running:
            self._info["chain"] = None

        chain = self._info["chain"]
        if self.wallet_manager is None or chain is None:
            wallets_path = "specter%s" % self.config["uid"]
            self.wallet_manager = WalletManager(
                os.path.join(self.data_folder, "wallets"), 
                self.cli, 
                chain=chain,
                path=wallets_path
            )
        else:
            self.wallet_manager.update(
                os.path.join(self.data_folder, "wallets"), 
                self.cli, 
                chain=chain
            )

        if self.device_manager is None:
            self.device_manager = DeviceManager(os.path.join(self.data_folder, "devices"))
        else:
            self.device_manager.update(os.path.join(self.data_folder, "devices"))

    def test_rpc(self, **kwargs):
        conf = copy.deepcopy(self.config["rpc"])
        conf.update(kwargs)
        cli = get_cli(conf)
        if cli is None:
            return {"out": "", "err": "autodetect failed", "code": -1}
        r = {}
        r['tests'] = {}
        try:
            r['tests']['recent_version'] = int(cli.getnetworkinfo()['version']) >= 170000
            r['tests']['connectable'] = True
            r['tests']['credentials'] = True
            try:
                cli.listwallets()
                r['tests']['wallets'] = True
            except RpcError as rpce:
                logger.error(rpce)
                if rpce.status_code ==  404:
                    r['tests']['wallets'] = False
                else:
                    raise rpce
            r["out"] = json.dumps(cli.getblockchaininfo(),indent=4)
            r["err"] = ""
            r["code"] = 0
        except ConnectionError as e:
            logger.error(e)
            r['tests']['connectable'] = False
            r["err"] = "Failed to connect!"
            r["code"] = -1
        except RpcError as rpce:
            logger.error(rpce)
            if rpce.status_code ==  401:
                r['tests']['credentials'] = False
            else:
                raise rpce
        except Exception as e:
            logger.error(e)
            r["out"] = ""
            if cli.r is not None and "error" in cli.r:
                r["err"] = cli.r["error"]
                r["code"] = cli.r.status_code
            else:
                r["err"] = "Failed to connect"
                r["code"] = -1
        return r
    
    def _save(self):
        with open(os.path.join(self.data_folder, self.CONFIG_FILE_NAME), "w") as f:
            f.write(json.dumps(self.config, indent=4))

    def update_rpc(self, **kwargs):
        need_update = False
        for k in kwargs:
            if self.config["rpc"][k] != kwargs[k]:
                self.config["rpc"][k] = kwargs[k]
                need_update = True
        if need_update:
            self._save()
            self.check()
    
    def update_auth(self, auth):
        ''' simply persisting the current auth-choice '''
        if self.config["auth"] != auth:
            self.config["auth"] = auth
        self._save()
    
    def update_explorer(self, explorer):
        ''' update the block explorers urls '''

        if explorer and not explorer.endswith("/"):
            # make sure the urls end with a "/"
            explorer += "/"

        # update the urls in the app config
        if self.config["explorers"][self.chain] != explorer:
            self.config["explorers"][self.chain] = explorer

    def update_hwi_bridge_url(self, url):
        ''' update the hwi bridge url to use '''
        if self.config["hwi_bridge_url"] != url:
            if url and not url.endswith("/"):
                # make sure the urls end with a "/"
                url += "/"
            self.config["hwi_bridge_url"] = url
        self._save()

    @property
    def info(self):
        return self._info

    def combine(self, psbt_arr):
        final_psbt = self.cli.combinepsbt(psbt_arr)
        return final_psbt

    def finalize(self, psbt):
        final_psbt = self.cli.finalizepsbt(psbt)
        return final_psbt

    def broadcast(self, raw):
        res = self.cli.sendrawtransaction(raw)
        return res

    def estimatesmartfee(self, blocks):
        return self.cli.estimatesmartfee(blocks)

    @property
    def chain(self):
        return self._info["chain"]

    @property
    def explorer(self):
        if "explorers" in self.config and self.chain in self.config["explorers"]:
            return self.config["explorers"][self.chain]
        else:
            return ""
