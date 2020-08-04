import logging
import requests, json, os
import os, sys, errno

logger = logging.getLogger(__name__)

# TODO: redefine __dir__ and help

RPC_PORTS = { "test": 18332, "regtest": 18443, "main": 8332, 'signet': 38332 }

def get_default_datadir():
    datadir = None
    if sys.platform == 'darwin':
        datadir = os.path.join(os.environ['HOME'], "Library/Application Support/Bitcoin/")
    elif sys.platform == 'win32':
        datadir = os.path.join(os.environ['APPDATA'], "Bitcoin")
    else:
        datadir = os.path.join(os.environ['HOME'], ".bitcoin")
    return datadir


def get_rpcconfig(datadir=get_default_datadir()):
    config = {
        "bitcoin.conf": {
            "default": {},
            "main": {},
            "test": {},
            "regtest": {}
        },
        "cookies": [],
    }
    if not os.path.isdir(datadir):  # we don't know where to search for files
        return config
    # load content from bitcoin.conf
    bitcoin_conf_file = os.path.join(datadir, "bitcoin.conf")
    if os.path.exists(bitcoin_conf_file):
        try:
            with open(bitcoin_conf_file, 'r') as f:
                current = config["bitcoin.conf"]["default"]
                for line in f.readlines():
                    line = line.split("#")[0]

                    for net in config["bitcoin.conf"]:
                        if f"[{net}]" in line:
                            current = config["bitcoin.conf"][net]

                    if '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    current[k.strip()] = v.strip()
        except Exception:
            print("Can't open %s file" % bitcoin_conf_file)
    folders = {
        "main": "",
        "test": "testnet3",
        "regtest": "regtest",
        "signet": "signet",
    }
    for chain in folders:
        fname = os.path.join(datadir, folders[chain], ".cookie")
        if os.path.exists(fname):
            try:
                with open(fname, 'r') as f:
                    content = f.read()
                    user, passwd = content.split(":")
                    obj = {
                        "user": user,
                        "passwd": passwd,
                        "port": RPC_PORTS[chain]
                    }
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
            default["passwd"] = config["bitcoin.conf"][network]["rpcpassword"]
        if "rpcconnect" in config["bitcoin.conf"][network]:
            default["host"] = config["bitcoin.conf"][network]["rpcconnect"]
        if "rpcport" in config["bitcoin.conf"][network]:
            default["port"] = int(config["bitcoin.conf"][network]["rpcport"])
        if "user" in default and "passwd" in default:
            if "port" not in config["bitcoin.conf"]["default"]: # only one bitcoin-cli makes sense in this case
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


def detect_cli_confs(config=None, datadir=get_default_datadir()):
    if config is None:
        config = get_rpcconfig(datadir=datadir)
    rpcconfs = get_configs(config)
    cli_arr = []
    for conf in rpcconfs:
        cli_arr.append(conf)
    return cli_arr


def autodetect_cli_confs(datadir=get_default_datadir(), port=None):
    if port == "":
        port = None
    if port is not None:
        port = int(port)
    conf_arr = detect_cli_confs(datadir=datadir)
    available_conf_arr = []
    if len(conf_arr) > 0:
        for conf in conf_arr:
            cli = BitcoinCLI(**conf)
            if port is not None:
                if int(cli.port) != port:
                    continue
            try:
                cli.getmininginfo()
                available_conf_arr.append(conf)
            except requests.exceptions.RequestException:
                pass
            except Exception as e:
                pass
    return available_conf_arr

class RpcError(Exception):
    ''' Specifically created for error-handling of the BitcoiCore-API
        if thrown, check for errors like this:
        try:
            cli.does_not_exist()
        except RpcError as rpce:
            assert rpce.error_code == -32601
            assert rpce.error_msg == "Method not found"
        See for error_codes https://github.com/bitcoin/bitcoin/blob/v0.15.0.1/src/rpc/protocol.h#L32L87
    '''
    def __init__(self, message, response):
        super(Exception, self).__init__(message)
        try:
            self.status_code = response.status_code
            error = response.json()
        except:
            # ok already a dict
            self.status_code = 500
            error = response
        try:
            self.error_code = error['error']['code']
            self.error_msg = error['error']['message']
        except Exception as e:
            self.error = "UNKNOWN API-ERROR:%s" % response.text


class BitcoinCLI:
    counter = 0
    def __init__(self, user, passwd, host="127.0.0.1", port=8332, protocol="http", path="", timeout=None, **kwargs):
        path = path.replace("//","/") # just in case
        self.user = user
        self.passwd = passwd
        self.port = port
        self.protocol = protocol
        self.host = host
        self.path = path
        self.timeout = timeout
        self.r = None

    def wallet(self, name=""):
        return BitcoinCLI(user=self.user,
                      passwd=self.passwd,
                      port=self.port,
                      protocol=self.protocol,
                      host=self.host,
                      path="{}/wallet/{}".format(self.path, name),
                      timeout=self.timeout
        )

    @property
    def url(self):
        return "{s.protocol}://{s.user}:{s.passwd}@{s.host}:{s.port}{s.path}".format(s=self)

    def test_connection(self):
        ''' returns a boolean depending on whether getblockchaininfo() succeeds '''
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
        return BitcoinCLI(
            self.user,
            self.passwd,
            self.host,
            self.port,
            self.protocol,
            self.path,
            self.timeout
        )

    def multi(self, calls: list, **kwargs):
        """Makes batch request to Core"""
        type(self).counter += len(calls)
        # some debug info for optimizations
        # methods = " ".join(list(dict.fromkeys([call[0] for call in calls])))
        # wallet = self.path.split("/")[-1]
        # print(f"{self.counter}: +{len(calls)} {wallet} {methods}")
        headers = {'content-type': 'application/json'}
        payload = [{
            "method": method,
            "params": args if args != [None] else [],
            "jsonrpc": "2.0",
            "id": i,
        } for i, (method, *args) in enumerate(calls)]
        timeout = self.timeout
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]
        url = self.url
        if "wallet" in kwargs:
            url = url+"/wallet/{}".format(kwargs["wallet"])
        r = requests.post(
            url, data=json.dumps(payload), headers=headers, timeout=timeout)
        self.r = r
        if r.status_code != 200:
            raise RpcError(
                "Server responded with error code %d: %s" % (
                    r.status_code, r.text
                ), r
            )
        r = r.json()
        return r

    def __getattr__(self, method):
        def fn(*args, **kwargs):
            r = self.multi([(method,*args)], **kwargs)[0]
            if r["error"] is not None:
                raise RpcError("Request error: %s" % r["error"]["message"], r)
            return r["result"]
        return fn


if __name__ == '__main__':

    cli = BitcoinCLI(
        "bitcoinrpc",
        "foi3uf092ury97iufhjf30982hf928uew9jd209j",
        port=18443
    )

    print(cli.url)

    print(cli.getmininginfo())

    print(cli.listwallets())

    ##### WORKING WITH WALLETS #########

    # print(cli.getbalance(wallet=""))

    # or

    w = cli.wallet("") # will load default wallet.dat

    print(w.url)

    print(w.getbalance()) # now you can run -rpcwallet commands
