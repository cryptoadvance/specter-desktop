import logging
import requests, json, os
import os, sys, errno

logger = logging.getLogger(__name__)

# TODO: redefine __dir__ and help

RPC_PORTS = {"test": 18332, "regtest": 18443, "main": 8332, "signet": 38332}


def get_default_datadir():
    """Get default Bitcoin directory depending on the system"""
    datadir = None
    if sys.platform == "darwin":
        datadir = os.path.join(
            os.environ["HOME"], "Library/Application Support/Bitcoin/"
        )
    elif sys.platform == "win32":
        datadir = os.path.join(os.environ["APPDATA"], "Bitcoin")
    else:
        datadir = os.path.join(os.environ["HOME"], ".bitcoin")
    return datadir


def get_rpcconfig(datadir=get_default_datadir()):
    """returns the bitcoin.conf configurations (multiple) in a datastructure
    for all networks of a specific datadir.
    """
    config = {
        "bitcoin.conf": {"default": {}, "main": {}, "test": {}, "regtest": {}},
        "cookies": [],
    }
    if not os.path.isdir(datadir):  # we don't know where to search for files
        return config
    # load content from bitcoin.conf
    bitcoin_conf_file = os.path.join(datadir, "bitcoin.conf")
    if os.path.exists(bitcoin_conf_file):
        try:
            with open(bitcoin_conf_file, "r") as f:
                current = config["bitcoin.conf"]["default"]
                for line in f.readlines():
                    line = line.split("#")[0]

                    for net in config["bitcoin.conf"]:
                        if f"[{net}]" in line:
                            current = config["bitcoin.conf"][net]

                    if "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    # lines like main.rpcuser and so on
                    if "." in k:
                        net, k = k.split(".", 1)
                        config["bitcoin.conf"][net.strip()][k.strip()] = v.strip()
                    else:
                        current[k.strip()] = v.strip()
        except Exception:
            print("Can't open %s file" % bitcoin_conf_file)
    folders = {"main": "", "test": "testnet3", "regtest": "regtest", "signet": "signet"}
    for chain in folders:
        fname = os.path.join(datadir, folders[chain], ".cookie")
        if os.path.exists(fname):
            try:
                with open(fname, "r") as f:
                    content = f.read()
                    user, password = content.split(":")
                    obj = {"user": user, "password": password, "port": RPC_PORTS[chain]}
                    config["cookies"].append(obj)
            except:
                print("Can't open %s file" % fname)
    return config


def get_configs(config=None, datadir=get_default_datadir()):
    if config is None:
        config = get_rpcconfig(datadir=datadir)
    confs = []
    default = {}
    for network in config["bitcoin.conf"]:
        if "rpcuser" in config["bitcoin.conf"][network]:
            default["user"] = config["bitcoin.conf"][network]["rpcuser"]
        if "rpcpassword" in config["bitcoin.conf"][network]:
            default["password"] = config["bitcoin.conf"][network]["rpcpassword"]
        if "rpcconnect" in config["bitcoin.conf"][network]:
            default["host"] = config["bitcoin.conf"][network]["rpcconnect"]
        if "rpcport" in config["bitcoin.conf"][network]:
            default["port"] = int(config["bitcoin.conf"][network]["rpcport"])
        if "user" in default and "password" in default:
            if (
                "port" not in config["bitcoin.conf"]["default"]
            ):  # only one rpc makes sense in this case
                if network == "default":
                    continue
                default["port"] = RPC_PORTS[network]
            confs.append(default.copy())
    # try cookies now
    for cookie in config["cookies"]:
        o = {}
        o.update(default)
        o.update(cookie)
        confs.append(o)
    return confs


def detect_rpc_confs(config=None, datadir=get_default_datadir()):
    if config is None:
        config = get_rpcconfig(datadir=datadir)
    rpcconfs = get_configs(config)
    rpc_arr = []
    for conf in rpcconfs:
        rpc_arr.append(conf)
    return rpc_arr


def detect_rpc_confs_via_env():
    """returns an array which might contain one configmap derived from Env-Vars
    Env-Vars: BTC_RPC_USER, BTC_RPC_PASSWORD, BTC_RPC_HOST, BTC_RPC_PORT
    configmap: {"user":"user","password":"password","host":"host","port":"port","protocol":"https"}
    """
    rpc_arr = []
    if (
        os.getenv("BTC_RPC_USER")
        and os.getenv("BTC_RPC_PASSWORD")
        and os.getenv("BTC_RPC_HOST")
        and os.getenv("BTC_RPC_PORT")
    ):
        logger.info("Detected RPC-Config on Environment-Variables")
        env_conf = {
            "user": os.getenv("BTC_RPC_USER"),
            "password": os.getenv("BTC_RPC_PASSWORD"),
            "host": os.getenv("BTC_RPC_HOST"),
            "port": os.getenv("BTC_RPC_PORT"),
            "protocol": os.getenv("BTC_RPC_PROTOCOL", "https"),  # https by default
        }
        rpc_arr.append(env_conf)
    return rpc_arr


def autodetect_rpc_confs(datadir=get_default_datadir(), port=None):
    """Returns an array of valid and working configurations which
    got autodetected.
    autodetection checks env-vars and bitcoin-data-dirs
    """
    if port == "":
        port = None
    if port is not None:
        port = int(port)
    conf_arr = []
    conf_arr.extend(detect_rpc_confs_via_env())
    conf_arr.extend(detect_rpc_confs(datadir=datadir))
    available_conf_arr = []
    if len(conf_arr) > 0:
        for conf in conf_arr:
            rpc = BitcoinRPC(**conf)
            if port is not None:
                if int(rpc.port) != port:
                    continue
            try:
                rpc.getmininginfo()
                available_conf_arr.append(conf)
            except requests.exceptions.RequestException as e:
                logger.info(f"requests exception: {rpc.host}:{rpc.port} {e}")
            except Exception as e:
                logger.info(f"exception: {rpc.host}:{rpc.port} {e}")
    return available_conf_arr


class RpcError(Exception):
    """Specifically created for error-handling of the BitcoiCore-API
    if thrown, check for errors like this:
    try:
        rpc.does_not_exist()
    except RpcError as rpce:
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"
    See for error_codes https://github.com/bitcoin/bitcoin/blob/v0.15.0.1/src/rpc/protocol.h#L32L87
    """

    def __init__(self, message, response):
        super(Exception, self).__init__(message)
        self.status_code = 500  # default
        try:
            self.status_code = response.status_code
            error = response.json()
        except Exception as e:
            # it's a dict already
            error = response
        try:
            self.error_code = error["error"]["code"]
            self.error_msg = error["error"]["message"]
        except Exception as e:
            self.error = "UNKNOWN API-ERROR:%s" % response.text


class BitcoinRPC:
    counter = 0

    def __init__(
        self,
        user="bitcoin",
        password="secret",
        host="127.0.0.1",
        port=8332,
        protocol="http",
        path="",
        timeout=None,
        session=None,
        **kwargs,
    ):
        path = path.replace("//", "/")  # just in case
        self.user = user
        self.password = password
        self.port = port
        self.protocol = protocol
        self.host = host
        self.path = path
        self.timeout = timeout
        self.r = None
        # session reuse speeds up requests
        if session is None:
            session = requests.Session()
            # check if we need to connect over Tor
            if ".onion" in self.host:
                # configure Tor proxies
                session.proxies["http"] = "socks5h://localhost:9050"
                session.proxies["https"] = "socks5h://localhost:9050"
        self.session = session

    def wallet(self, name=""):
        return BitcoinRPC(
            user=self.user,
            password=self.password,
            port=self.port,
            protocol=self.protocol,
            host=self.host,
            path="{}/wallet/{}".format(self.path, name),
            timeout=self.timeout,
            session=self.session,
        )

    @property
    def url(self):
        return "{s.protocol}://{s.user}:{s.password}@{s.host}:{s.port}{s.path}".format(
            s=self
        )

    def test_connection(self):
        """ returns a boolean depending on whether getblockchaininfo() succeeds """
        try:
            self.getblockchaininfo()
            return True
        except:
            return False

    def clone(self):
        """
        Returns a clone of self.
        Usefull if you want to mess with the properties
        """
        return BitcoinRPC(
            self.user,
            self.password,
            self.host,
            self.port,
            self.protocol,
            self.path,
            self.timeout,
            self.session,
        )

    def multi(self, calls: list, **kwargs):
        """Makes batch request to Core"""
        type(self).counter += len(calls)
        # some debug info for optimizations
        # methods = " ".join(list(dict.fromkeys([call[0] for call in calls])))
        # wallet = self.path.split("/")[-1]
        # print(f"{self.counter}: +{len(calls)} {wallet} {methods}")
        headers = {"content-type": "application/json"}
        payload = [
            {
                "method": method,
                "params": args if args != [None] else [],
                "jsonrpc": "2.0",
                "id": i,
            }
            for i, (method, *args) in enumerate(calls)
        ]
        timeout = self.timeout
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
        url = self.url
        if "wallet" in kwargs:
            url = url + "/wallet/{}".format(kwargs["wallet"])
        r = self.session.post(
            url, data=json.dumps(payload), headers=headers, timeout=timeout
        )
        self.r = r
        if r.status_code != 200:
            raise RpcError(
                "Server responded with error code %d: %s" % (r.status_code, r.text), r
            )
        r = r.json()
        return r

    def __getattr__(self, method):
        def fn(*args, **kwargs):
            r = self.multi([(method, *args)], **kwargs)[0]
            if r["error"] is not None:
                raise RpcError("Request error: %s" % r["error"]["message"], r)
            return r["result"]

        return fn


if __name__ == "__main__":

    rpc = BitcoinRPC(
        "bitcoinrpc", "foi3uf092ury97iufhjf30982hf928uew9jd209j", port=18443
    )

    print(rpc.url)

    print(rpc.getmininginfo())

    print(rpc.listwallets())

    ##### WORKING WITH WALLETS #########

    # print(rpc.getbalance(wallet=""))

    # or

    w = rpc.wallet("")  # will load default wallet.dat

    print(w.url)

    print(w.getbalance())  # now you can run -rpcwallet commands
