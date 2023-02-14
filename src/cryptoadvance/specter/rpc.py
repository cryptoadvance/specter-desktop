import datetime
import errno
import json
import logging
import os
import sys

import requests
import urllib3

from .helpers import is_ip_private
from .specter_error import SpecterError, handle_exception, BrokenCoreConnectionException
from urllib3.exceptions import NewConnectionError
from requests.exceptions import ConnectionError

logger = logging.getLogger(__name__)

# TODO: redefine __dir__ and help

RPC_PORTS = {
    "testnet": 18332,
    "test": 18332,
    "regtest": 18443,
    "main": 8332,
    "mainnet": 8332,
    "signet": 38332,
}


def get_default_datadir(node_type="BTC"):
    """Get default Bitcoin directory depending on the system"""
    datadir = None
    if node_type == "BTC":
        last_part = "Bitcoin"
    elif node_type == "ELM":
        last_part = "Elements"
    else:
        raise SpecterError(f"Unknown node_type {node_type}")

    if sys.platform == "darwin":
        # Not tested yet!
        datadir = os.path.join(
            os.environ["HOME"], f"Library/Application Support/{last_part}/"
        )
    elif sys.platform == "win32":
        # Not tested yet!
        datadir = os.path.join(os.environ["APPDATA"], last_part)
    else:
        datadir = os.path.join(os.environ["HOME"], f".{last_part.lower()}")
    return datadir


def get_rpcconfig(datadir=get_default_datadir()) -> dict:
    """Returns the bitcoin.conf configurations for all networks.
    If the bitcoin.conf is empty or doesn't exist, it returns the (empty) dict defined at the start.
    Example for regtest:
    {'bitcoin.conf': {'default': {'regtest': '1', 'server': '1', 'rpcuser': 'satoshi', 'rpcpassword': 'secret', 'disablewallet': '0', 'fallbackfee': '0.000001'
            }, 'main': {}, 'test': {}, 'regtest': {'rpcport': '18443'}
        }, 'cookies': []
    }
    """
    config = {
        "bitcoin.conf": {"default": {}, "main": {}, "test": {}, "regtest": {}},
        "cookies": {},
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
        except Exception as e:
            handle_exception(e)
            print("Can't open %s file" % bitcoin_conf_file)
    folders = {"main": "", "test": "testnet3", "regtest": "regtest", "signet": "signet"}
    for chain in folders:
        fname = os.path.join(datadir, folders[chain], ".cookie")
        if os.path.exists(fname):
            logger.debug(f"Found a cookie file for chain {chain}")
            try:
                with open(fname, "r") as f:
                    content = f.read()
                    user, password = content.split(":")
                    obj = {"user": user, "password": password, "port": RPC_PORTS[chain]}
                    config["cookies"][chain] = obj
            except Exception as e:
                handle_exception(e)
                print("Can't open %s file" % fname)
    return config


def _detect_rpc_confs_via_datadir(config=None, datadir=get_default_datadir()):
    """returns the bitcoin.conf configuration for the network
    specified in bitcoin.conf with testnet=1, regtest=1, etc. as
    well as the network's auth cookie information.
    """

    confs = []
    conf = {}
    networks = []
    selected_network = "main"

    if config is None:
        config = get_rpcconfig(datadir=datadir)

    if "default" in config["bitcoin.conf"]:
        default = config["bitcoin.conf"]["default"]
        networks.append("default")
        if "regtest" in default and default["regtest"] == "1":
            selected_network = "regtest"
        elif "testnet" in default and default["testnet"] == "1":
            selected_network = "test"
        elif "signet" in default and default["signet"] == "1":
            selected_network = "signet"

    logger.debug(f"Bitcoin network set to {selected_network}")

    # Network specific options take precedence over default ones,
    # as per https://github.com/bitcoin/bitcoin/blob/master/doc/bitcoin-conf.md#network-specific-options
    networks.append(selected_network)

    for network in networks:
        if "rpcuser" in config["bitcoin.conf"][network]:
            conf["user"] = config["bitcoin.conf"][network]["rpcuser"]
        if "rpcpassword" in config["bitcoin.conf"][network]:
            conf["password"] = config["bitcoin.conf"][network]["rpcpassword"]
        if "rpcconnect" in config["bitcoin.conf"][network]:
            conf["host"] = config["bitcoin.conf"][network]["rpcconnect"]
        if "rpcport" in config["bitcoin.conf"][network]:
            conf["port"] = int(config["bitcoin.conf"][network]["rpcport"])
    if conf:
        confs.append(conf)

    # Check for cookies as auth fallback, rpcpassword in bitcoin.conf takes precedence
    # as per https://github.com/bitcoin/bitcoin/blob/master/doc/init.md#configuration
    # Only take the selected network cookie info
    if "cookies" in config and selected_network in config["cookies"]:
        cookie = config["cookies"][selected_network]
        o = {}
        o.update(conf)
        o.update(cookie)
        confs.append(o)

    return confs


def _detect_rpc_confs_via_env(prefix):
    """returns an array which might contain one configmap derived from Env-Vars
    Env-Vars for prefix=BTC: BTC_RPC_USER, BTC_RPC_PASSWORD, BTC_RPC_HOST, BTC_RPC_PORT
    configmap: {"user":"user","password":"password","host":"host","port":"port","protocol":"https"}
    """
    rpc_arr = []
    if (
        os.getenv(f"{prefix}_RPC_USER")
        and os.getenv(f"{prefix}_RPC_PASSWORD")
        and os.getenv(f"{prefix}_RPC_HOST")
        and os.getenv(f"{prefix}_RPC_PORT")
        and os.getenv(f"{prefix}_RPC_PROTOCOL")
    ):
        logger.info(f"Detected RPC-Config on Environment-Variables for prefix {prefix}")
        env_conf = {
            "user": os.getenv(f"{prefix}_RPC_USER"),
            "password": os.getenv(f"{prefix}_RPC_PASSWORD"),
            "host": os.getenv(f"{prefix}_RPC_HOST"),
            "port": os.getenv(f"{prefix}_RPC_PORT"),
            "protocol": os.getenv(f"{prefix}_RPC_PROTOCOL"),
        }
        rpc_arr.append(env_conf)
    return rpc_arr


def autodetect_rpc_confs(
    node_type,
    datadir=get_default_datadir(),
    port=None,
    proxy_url="socks5h://localhost:9050",
    only_tor=False,
):
    """Returns an array of valid and working configurations which
    got autodetected.
    autodetection checks env-vars and bitcoin-data-dirs
    """
    if port == "":
        port = None
    if port is not None:
        port = int(port)
    conf_arr = []
    conf_arr.extend(_detect_rpc_confs_via_env(node_type))
    conf_arr.extend(_detect_rpc_confs_via_datadir(datadir=datadir))
    available_conf_arr = []
    if len(conf_arr) > 0:
        for conf in conf_arr:
            rpc = BitcoinRPC(**conf, proxy_url=proxy_url, only_tor=only_tor)
            try:
                rpc.getmininginfo()
                available_conf_arr.append(conf)
            except requests.exceptions.RequestException as e:
                pass
                # no point in reporting that here
            except SpecterError as e:
                # Timeout
                pass
            except RpcError:
                pass
            except BrokenCoreConnectionException:
                # If conf's auth doesn't work, let's try cookie's auth if found
                pass
                # have to make a list of acceptable exception unfortunately
                # please enlarge if you find new ones
    return available_conf_arr


class RpcError(Exception):
    """Specifically created for error-handling of the BitcoinCore-API
    if thrown, check for errors like this:
    try:
        rpc.does_not_exist()
    except RpcError as rpce:
        assert rpce.status_code == 401 # A https-status-code
        assert rpce.error_code == -32601
        assert rpce.error_msg == "Method not found"
    See for error_codes https://github.com/bitcoin/bitcoin/blob/v0.15.0.1/src/rpc/protocol.h#L32L87
    You can create these RpcErrors via a response-object:
        RpcError("some Message",response)
    or directly via:
        raise RpcError("some Message", status_code=500, error_code=-32601, error_msg="Requested wallet does not exist or is not loaded")
    The message is swallowed if there is a proper error_msg.
    """

    def __init__(
        self, message, response=None, status_code=None, error_code=None, error_msg=None
    ):
        super(Exception, self).__init__(message)
        if response is not None:
            self.init_via_response(response)
        else:

            self.status_code = status_code or 500
            self.error_code = error_code or -99
            self.error_msg = error_msg or str(self)

    def init_via_response(self, response):
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
        except Exception:
            self.error_code = -99
            self.error_msg = str(self) + " - UNKNOWN API-ERROR:%s" % response.text


class BitcoinRPC:
    counter = 0

    # These are used for tracing the calls without too many duplicates
    last_call_hash = None
    last_call_hash_counter = 0

    # https://docs.python-requests.org/en/master/user/quickstart/#timeouts
    # None means until connection closes. It's specified in seconds
    default_timeout = None  # seconds

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
        proxy_url="socks5h://localhost:9050",
        only_tor=False,
        **kwargs,
    ):
        path = path.replace("//", "/")  # just in case
        self.user = user
        self._password = password
        self.port = port
        self.protocol = protocol
        self.host = host
        self.path = path
        self.timeout = timeout or self.__class__.default_timeout
        self.proxy_url = proxy_url
        self.only_tor = only_tor
        self.r = None
        self.last_call_hash = None
        self.last_call_hash_counter = 0
        # session reuse speeds up requests
        if session is None:
            self._create_session()
        else:
            self.session = session

    def _create_session(self):
        session = requests.Session()
        session.auth = (self.user, self.password)
        # check if we need to connect over Tor
        if not is_ip_private(self.host):
            if self.only_tor or ".onion" in self.host:
                # configure Tor proxies
                session.proxies["http"] = self.proxy_url
                session.proxies["https"] = self.proxy_url
        self.session = session

    def wallet(self, name=""):
        """Return new instance connected to a specific wallet"""
        return type(self)(
            user=self.user,
            password=self.password,
            port=self.port,
            protocol=self.protocol,
            host=self.host,
            path="{}/wallet/{}".format(self.path, name),
            timeout=self.timeout,
            session=self.session,
            proxy_url=self.proxy_url,
            only_tor=self.only_tor,
        )

    @property
    def url(self):
        return "{s.protocol}://{s.host}:{s.port}{s.path}".format(s=self)

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = value
        self._create_session()

    def test_connection(self):
        """returns a boolean depending on whether getblockchaininfo() succeeds"""
        try:
            self.getblockchaininfo()
            return True
        except:
            return False

    def clone(self):
        """
        Returns a clone of self.
        Useful if you want to mess with the properties
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
            self.proxy_url,
            self.only_tor,
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

        if kwargs.get("no_wait"):
            # Zero is treated like None, i.e. infinite wait
            timeout = 0.001

        url = self.url
        if "wallet" in kwargs:
            url = url + "/wallet/{}".format(kwargs["wallet"])
        ts = self.trace_call_before(url, payload)
        try:
            r = self.session.post(
                url, data=json.dumps(payload), headers=headers, timeout=timeout
            )
        except (ConnectionError, NewConnectionError, ConnectionRefusedError) as ce:
            raise BrokenCoreConnectionException()

        except (requests.exceptions.Timeout, urllib3.exceptions.ReadTimeoutError) as to:
            # Timeout is effectively one of the two:
            # ConnectTimeout: The request timed out while trying to connect to the remote server
            # ReadTimeout: The server did not send any data in the allotted amount of time.
            # ReadTimeoutError: Raised when a socket timeout occurs while receiving data from a server
            if kwargs.get("no_wait"):
                # Used for rpc calls that don't immediately return (e.g. rescanblockchain) so we don't
                # expect any data back anyway. __getattr__ expects a list of formatted json.
                self.trace_call_after(url, payload, timeout)
                return [{"error": None, "result": None}]

            logger.error(
                "Timeout after {} secs while {} call({: <28}) payload:{} Exception: {}".format(
                    timeout,
                    self.__class__.__name__,
                    "/".join(url.split("/")[3:]),
                    payload,
                    to,
                )
            )
            logger.exception(to)
            raise SpecterError(
                "Timeout after {} secs while {} call({: <28}). Check the logs for more details.".format(
                    timeout,
                    self.__class__.__name__,
                    "/".join(url.split("/")[3:]),
                    payload,
                )
            )
        self.trace_call_after(url, payload, ts)
        self.r = r
        if r.status_code != 200:
            logger.debug(f"last call FAILED: {r.text}")
            if r.text.startswith("Work queue depth exceeded"):
                raise SpecterError(
                    "Your Bitcoind is running hot (Work queue depth exceeded)! Bitcoind gets more requests than it can process. Please refrain from doing anything for some minutes."
                )
            raise RpcError(
                "Server responded with error code %d: %s" % (r.status_code, r.text), r
            )
        r = r.json()
        return r

    @classmethod
    def trace_call_before(cls, url, payload):
        """get a timestamp if needed in order to measure how long the call takes"""
        if logger.level == logging.DEBUG:
            return datetime.datetime.now()

    @classmethod
    def trace_call_after(cls, url, payload, timestamp):
        """logs out the call and its payload (if necessary), reduces noise by suppressing repeated calls"""
        if logger.level == logging.DEBUG:
            timediff_ms = int(
                (datetime.datetime.now() - timestamp).total_seconds() * 1000
            )
            current_hash = hash(
                json.dumps({"url": url, "payload": payload}, sort_keys=True)
            )
            if cls.last_call_hash == None:
                cls.last_call_hash = current_hash
                cls.last_call_hash_counter = 0
            elif cls.last_call_hash == current_hash:
                cls.last_call_hash_counter = cls.last_call_hash_counter + 1
                return
            else:
                if cls.last_call_hash_counter > 0:
                    logger.debug(f"call repeated {cls.last_call_hash_counter} times")
                    cls.last_call_hash_counter = 0
                    cls.last_call_hash = current_hash
                else:
                    cls.last_call_hash = current_hash
            logger.debug(
                "call({: <28})({: >5}ms)  payload:{}".format(
                    "/".join(url.split("/")[3:]), timediff_ms, payload
                )
            )

    def __getattr__(self, method):
        def fn(*args, **kwargs):
            r = self.multi([(method, *args)], **kwargs)[0]
            if r["error"] is not None:
                raise RpcError(
                    f"Request error for method {method}{args}: {r['error']['message']}",
                    r,
                )
            return r["result"]

        return fn

    def __repr__(self) -> str:
        return f"<BitcoinRpc {self.url}>"


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
