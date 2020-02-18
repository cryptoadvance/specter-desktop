import logging

def test_bitcoinddocker_running(caplog):
    caplog.set_level(logging.DEBUG)
    from cryptoadvance.specter.bitcoind import BitcoindDockerController
    my_bitcoind = BitcoindDockerController(rpcport=18999) # completly different port to not interfere
    #assert my_bitcoind.detect_bitcoind_container() == True
    rpcconn = my_bitcoind.start_bitcoind(cleanup_at_exit=True)
    assert rpcconn.get_cli() != None
    assert rpcconn.get_cli().ipaddress != None
    rpcconn.get_cli().getblockchaininfo()
    # you can use the testcoin_faucet:
    random_address = "mruae2834buqxk77oaVpephnA5ZAxNNJ1r"
    my_bitcoind.testcoin_faucet(random_address, amount=25, mine_tx=True)
    my_bitcoind.stop_bitcoind()


    