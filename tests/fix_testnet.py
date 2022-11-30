""" A set of fixtures which assume a testnet-node on localhost. This can be helpfull while developing.

"""

from cryptoadvance.specter.user import User, hash_password
import pytest
from cryptoadvance.specter.specter import Specter
from cryptoadvance.specter.user import User


@pytest.fixture
def specter_testnet_configured(bitcoin_regtest, devices_filled_data_folder):
    """This assumes a bitcoin-testnet-node is running on loalhost"""

    config = {
        "rpc": {
            "autodetect": False,
            "datadir": "",
            "user": "bitcoin",  # change this to your credential in bitcoin.conf (for testnet)
            "password": "secret",
            "port": 18332,
            "host": "localhost",
            "protocol": "http",
        },
        "auth": {
            "method": "rpcpasswordaspin",
        },
    }
    specter = Specter(
        data_folder=devices_filled_data_folder, config=config, checker_threads=False
    )
    specter.check()
    assert specter.chain == "test"

    # Create a User
    someuser = specter.user_manager.add_user(
        User.from_json(
            user_dict={
                "id": "someuser",
                "username": "someuser",
                "password": hash_password("somepassword"),
                "config": {},
                "is_admin": False,
                "services": None,
            },
            specter=specter,
        )
    )
    specter.user_manager.save()
    specter.check()

    assert not specter.wallet_manager.working_folder is None
    try:
        yield specter
    finally:
        # Deleting all Wallets (this will also purge them on core)
        for user in specter.user_manager.users:
            for wallet in list(user.wallet_manager.wallets.values()):
                user.wallet_manager.delete_wallet(wallet)
