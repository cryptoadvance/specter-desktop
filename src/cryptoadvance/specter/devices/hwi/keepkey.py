from .trezor import TrezorClient


class KeepkeyClient(TrezorClient):
    def __init__(self, path, password="", expert=False):
        super(KeepkeyClient, self).__init__(path, password, expert)
        self.type = "Keepkey"
