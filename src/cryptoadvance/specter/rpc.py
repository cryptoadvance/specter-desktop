import requests, json, os
import os, sys, errno

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

def get_rpcconfig():
    path = get_default_datadir()
    config = {
        "bitcoin.conf": {},
        "cookies": [],
    }
    if not os.path.isdir(path): # we don't know where to search for files
        return config
    # load content from bitcoin.conf
    bitcoin_conf_file = os.path.join(path, "bitcoin.conf")
    if os.path.exists(bitcoin_conf_file):
        try:
            with open(bitcoin_conf_file, 'r') as f:
                for line in f.readlines():
                    line = line.split("#")[0]
                    if '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    config["bitcoin.conf"][k.strip()] = v.strip()
        except:
            print("Can't open %s file" % bitcoin_conf_file)
    folders = {
        "main": "", 
        "test": "testnet3",
        "regtest": "regtest",
        "signet": "signet",
    }
    for chain in folders:
        fname = os.path.join(path, folders[chain], ".cookie")
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

def get_configs(config=None):
    if config is None:
        config = get_rpcconfig()
    confs = []
    default = {}
    if "rpcuser" in config["bitcoin.conf"]:
        default["user"] = config["bitcoin.conf"]["rpcuser"]
    if "rpcpassword" in config["bitcoin.conf"]:
        default["passwd"] = config["bitcoin.conf"]["rpcpassword"]
    if "rpcconnect" in config["bitcoin.conf"]:
        default["host"] = config["bitcoin.conf"]["rpcconnect"]
    if "rpcport" in config["bitcoin.conf"]:
        default["port"] = int(config["bitcoin.conf"]["rpcport"])
    if "user" in default and "passwd" in default:
        if "port" in default: # only one bitcoin-cli makes sense in this case
            confs.append(default)
            return confs
        else:
            for network in RPC_PORTS:
                o = {"port": RPC_PORTS[network]}
                o.update(default)
                confs.append(o)
            return confs
    # try cookies now
    for cookie in config["cookies"]:
        o = {}
        o.update(default)
        o.update(cookie)
        confs.append(o)
    return confs

def detect_cli(config=None):
    if config is None:
        config = get_rpcconfig()
    rpcconfs = get_configs(config)
    cli_arr = []
    for conf in rpcconfs:
        cli_arr.append(BitcoinCLI(**conf))
    return cli_arr

def autodetect_cli(port=None):
    if port == "":
        port = None
    if port is not None:
        port = int(port)
    cli_arr = detect_cli()
    available_cli_arr = []
    if len(cli_arr) > 0:
        print("trying %d different configs" % len(cli_arr))
        for cli in cli_arr:
            if port is not None:
                if int(cli.port) != port:
                    continue
            try:
                cli.getmininginfo()
                available_cli_arr.append(cli)
            except requests.exceptions.RequestException:
                pass
            except Exception as e:
                pass
    else:
        print("Bitcoin-cli not found :(")
    print("Detected %d bitcoin daemons" % len(available_cli_arr))
    return available_cli_arr

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
        self.status_code = response.status_code
        try:
            error = json.loads(response.text)
            self.status_code = response.status_code
            self.error_code = error['error']['code']
            self.error_msg = error['error']['message']
        except Exception as e:
            self.error = "UNKNOWN API-ERROR:%s" % response.text


class BitcoinCLI:
    def __init__(self, user, passwd, host="127.0.0.1", port=8332, protocol="http", path="", timeout=30, **kwargs):
        path = path.replace("//","/") # just in case
        self.user = user
        self.passwd = passwd
        self.port = port
        self.protocol = protocol
        self.host = host
        self.path = path
        self.timeout = timeout
        self.r = None
        def wallet(name=""):
            return BitcoinCLI(user=self.user,
                          passwd=self.passwd,
                          port=self.port,
                          protocol=self.protocol,
                          host=self.host,
                          path="{}/wallet/{}".format(self.path, name),
                          timeout=self.timeout
            )
        self.wallet = wallet

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
        ''' returns a clone of self. Usefull if you want to mess with the properties '''
        return BitcoinCLI(self.user, self.passwd, self.host, self.port, self.protocol, self.path, self.timeout)

    def __getattr__(self, method):
        # if hasattr(self, method):
            # self.
        headers = {'content-type': 'application/json'}
        def fn(*args, **kwargs):
            payload = {
                "method": method,
                "params": args,
                "jsonrpc": "2.0",
                "id": 0,
            }
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
                raise RpcError("Server responded with error code %d: %s" % (r.status_code, r.text), r)
            r = r.json()
            if r["error"] is not None:
                raise Exception(r["error"])
            return r["result"]
        return fn

if __name__ == '__main__':

    cli = BitcoinCLI("bitcoinrpc", "foi3uf092ury97iufhjf30982hf928uew9jd209j", port=18443)
    
    print(cli.url)

    print(cli.getmininginfo())

    print(cli.listwallets())

    ##### WORKING WITH WALLETS #########

    print(cli.getbalance(wallet=""))

    # or

    w = cli.wallet("") # will load default wallet.dat

    print(w.url)

    print(w.getbalance()) # now you can run -rpcwallet commands
