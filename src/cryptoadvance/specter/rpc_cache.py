import logging
from .rpc import BitcoinCLI, RpcError
from .corecache import CoreCache

logger = logging.getLogger(__name__)

class BitcoinCLICached:
    def __init__(self, user="", passwd="", host="127.0.0.1", port=8332, protocol="http", path="", timeout=30, cli=None, **kwargs):
        if cli:
            # If cli argument is not empty it should contain a wallet settting in it
            # Only CLI with a wallet configured should have caching
            self.cli = cli
            self.cache = CoreCache(cli)
        else:
            self.cli = BitcoinCLI(user, passwd, host, port, protocol, path, timeout)
            self.cache = None

    @classmethod
    def from_wallet_cli(cls, cli):
        """ Initialize BitcoinCLICached from a CLI with wallet configured.
            This call is internally used when the `wallet` method is called and configures the CLI wallet.
        """
        return cls(cli=cli)
 
    def scan_addresses(self, wallet):
        scanning = self.cli.getwalletinfo()["scanning"]
        if self.cache.scan_addresses or scanning:
            for tx in self.cli.listtransactions("*", 1000, 0, True):
                address_info = self.cli.getaddressinfo(tx["address"])
                if "hdkeypath" in address_info:
                    path = address_info["hdkeypath"].split('/')
                    change = int(path[-2]) == 1
                    while int(path[-1]) > (wallet.change_index if change else wallet.address_index):
                        wallet.getnewaddress(change=change)
            if not scanning:
                self.cache.scanning_ended()
            self.cache.update_addresses(wallet.addresses, change=False)
            self.cache.update_addresses(wallet.change_addresses, change=True)

    @property
    def url(self):
        return self.cli.url

    @property
    def passwd(self):
        return self.cli.passwd

    @passwd.setter
    def passwd(self,value):
        self.cli.passwd = value

    def test_connection(self):
        return self.cli.test_connection()

    def clone(self):
        ''' returns a clone of self. Usefull if you want to mess with the properties '''
        if self.cache:
            return BitcoinCLICached.from_wallet_cli(cli=self.cli)
        return BitcoinCLICached(self.cli.user, self.cli.passwd, self.cli.host, self.cli.port, self.cli.protocol, self.cli.path, self.cli.timeout)
    
    def wallet(self, name=""):
        try:
            return BitcoinCLICached.from_wallet_cli(cli=self.cli.wallet(name))
        except RpcError as rpce:
            raise rpce
        except Exception as e:
            raise e
    
    def listtransactions(self, *args, **kwargs):
        cli_transactions = self.cli.listtransactions(*args, **kwargs)
        if self.cache:
            return self.cache.update_txs(cli_transactions)
        return cli_transactions

    def deriveaddresses(self, *args, **kwargs):
        addresses = self.cli.deriveaddresses(*args, **kwargs)
        if self.cache:
            if "internal" not in kwargs or kwargs["internal"] == True: 
                change = "change" in kwargs and kwargs["change"] == True
                self.cache.update_addresses(addresses, change=change)
        return addresses

    def rescanblockchain(self, *args, **kwargs):
        if self.cache:
            self.cache.scanning_started()
        return self.cli.rescanblockchain(*args, **kwargs)

    def __getattr__(self, method):
        try:
            return self.cli.__getattr__(method)
        except RpcError as rpce:
            raise rpce
        except Exception as e:
                raise e
