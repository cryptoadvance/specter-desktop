import requests, json, os

# TODO: redefine __dir__ and help

RPC_PORTS = { "test": 18332, "regtest": 18443, "main": 8332 }

class BitcoinCLI:
    def __init__(self, user, passwd, host="127.0.0.1", port=18332, protocol="http", path="", timeout=3):
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
                raise Exception("Server responded with error code %d: %s" % (r.status_code, r.text))
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
