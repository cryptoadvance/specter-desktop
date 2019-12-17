import logging


def test_bitcoinddocker_running(caplog):
    caplog.set_level(logging.DEBUG)
    from bitcoind import BitcoindDockerController
    my_bitcoind = BitcoindDockerController()
    #assert my_bitcoind.detect_bitcoind_container() == True
    rpcconn = my_bitcoind.start_bitcoind(cleanup_at_exit=True)
    assert rpcconn.get_rpcconn() != None
    rpcconn.get_rpcconn().getblockchaininfo()
    my_bitcoind.stop_bitcoind()

    