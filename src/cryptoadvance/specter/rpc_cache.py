from .rpc import BitcoinCLI
from .corecache import CoreCache

class BitcoinCLICached:
    def __init__(self, user="", passwd="", host="127.0.0.1", port=8332, protocol="http", path="", timeout=30, cli=None, **kwargs):
        if cli:
            self.cli = cli
            self.cache = CoreCache(cli)
        else:
            self.cli = BitcoinCLI(user, passwd, host, port, protocol, path, timeout)
            self.cache = None

    @property
    def url(self):
        return self.cli.url

    def test_connection(self):
        return self.cli.test_connection()

    def clone(self):
        ''' returns a clone of self. Usefull if you want to mess with the properties '''
        if self.cache:
            return BitcoinCLICached(cli=self.cli)
        return BitcoinCLICached(self.cli.user, self.cli.passwd, self.cli.host, self.cli.port, self.cli.protocol, self.cli.path, self.cli.timeout)
    
    def wallet(self, name=""):
        return BitcoinCLICached(cli=self.cli.wallet(name))
    
    def listtransactions(self, *args, **kwargs):
        cli_transactions = self.cli.listtransactions(*args, **kwargs)
        if self.cache:
            return self.cache.update_txs(cli_transactions)
        return cli_transactions

    def __getattr__(self, method):
        return self.cli.__getattr__(method)
