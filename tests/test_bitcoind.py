import logging


def test_bitcoinddocker_running(caplog):
    caplog.set_level(logging.DEBUG)
    from bitcoind import BitcoindDockerController
    my_bitcoind = BitcoindDockerController(rpcport=18999) # completly different port to not interfere
    #assert my_bitcoind.detect_bitcoind_container() == True
    rpcconn = my_bitcoind.start_bitcoind(cleanup_at_exit=True)
    assert rpcconn.get_cli() != None
    assert rpcconn.get_cli().ipaddress != None
    rpcconn.get_cli().getblockchaininfo()
    my_bitcoind.stop_bitcoind()


    