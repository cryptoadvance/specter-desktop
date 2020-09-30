import logging
import pytest

def test_home(caplog, client):
    ''' The root of the app '''
    caplog.set_level(logging.INFO)
    caplog.set_level(logging.DEBUG,logger="cryptoadvance.specter")
    login(client, 'secret')
    result = client.get('/')
    # By default there is no authentication
    assert result.status_code == 302 # REDIRECT.
    result = client.get('/about')
    assert b'Welcome to Specter' in result.data
    result = client.get('/new_device', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'Setting up a new device' in result.data
    result = client.get('/settings', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'settings - Specter Desktop' in result.data
    result = client.get('/new_wallet', follow_redirects=True)
    assert result.status_code == 200 # OK.
    assert b'Select the type of the wallet' in result.data

    # Login logout testing
    result = client.get('/login', follow_redirects=False)
    assert result.status_code == 200
    assert b'Password' in result.data
    result = login(client, 'secret')
    assert b'Logged in successfully.' in result.data
    result = logout(client)
    assert b'You were logged out' in result.data
    result = login(client, 'non_valid_password')
    assert b'Invalid username or password' in result.data        
    result = login(client, 'blub')
    assert b'Invalid username or password' in result.data


def test_settings_general(caplog, client):
    login(client, 'secret')
    result = client.get('/settings/general', follow_redirects=True)
    assert b'Network:' in result.data
    assert b'regtest' in result.data

def test_settings_general_restore_wallet(caplog, client): 
    login(client, 'secret')
    restore_wallets = """
        [{"name":"btc+Hot+Wallet","alias":"simple","description":"Single+(Segwit)","address_type":"bech32","address":"bcrt1qgh00vt35pmvjsedlh45vcnmts3ntgxj6w8gsa8",
        "address_index":0,"change_address":"bcrt1qvfh56wqnx37yzhxh0sd2wqcq9hcqv0h9n3p5tr","change_index":0,"keypool":20,"change_keypool":20,
        "recv_descriptor":"wpkh([0c28f912/84h/1h/0h]tpubDDpeUiiTJ2qdFGPCtkZHxdDP1fmDb74qcujm1QyTkFE7uvye2Y32P1X18tirrWLokSu3gX37SGufhNdmTkWVVuB2tGM61iQCXvLZZvCvChu/0/*)#am92xxvq",
        "change_descriptor":"wpkh([0c28f912/84h/1h/0h]tpubDDpeUiiTJ2qdFGPCtkZHxdDP1fmDb74qcujm1QyTkFE7uvye2Y32P1X18tirrWLokSu3gX37SGufhNdmTkWVVuB2tGM61iQCXvLZZvCvChu/1/*)#v0qtmnuc",
        "keys":[{"original":"vpub5ZnVM9YwHPoDGsp7mqzxLXh1LcNfiUanF472658YeKiU4SgUSzrozSXtrSiuLC5j9G8XZzL7yrNXEcv2dVqE1zMY5zCwAN6zQWcs2mkJiME","fingerprint":"0c28f912","derivation":"m/84h/1h/0h",
        "type":"wpkh","xpub":"tpubDDpeUiiTJ2qdFGPCtkZHxdDP1fmDb74qcujm1QyTkFE7uvye2Y32P1X18tirrWLokSu3gX37SGufhNdmTkWVVuB2tGM61iQCXvLZZvCvChu"}],"devices":["btchot"],"sigs_required":1,"pending_psbts":{},
        "fullpath":"/home/kim/.specter/wallets/regtest/simple.json","last_block":"795bf8af85caec61d7f2afe8de16376fc82fb7ffb8c15c19538fb2b20aece35c","blockheight":555,"labels":{"Address+#0":["bcrt1qgh00vt35pmvjsedlh45vcnmts3ntgxj6w8gsa8"],"Address+#1":["bcrt1qt2xpsvztclcks4q4m0yunre9a3zu4pyc4zdf66"],"Address+#10":["bcrt1q6c46ryqva9h3h4hszgsdt6lpfpkpa9jl8zk3ym"],"Address+#11":["bcrt1qf3afewnuwmcmtufvfm3psch0f2u2e8dtcy0fda"],"Address+#12":["bcrt1q0zy88yjdqzggsus8fqk3fggvn6ggyr3lyds2cy"],"Address+#13":["bcrt1qcmnt2q3lzczgzeslnxmsptwypwck0u9zep66vn"],"Address+#14":["bcrt1qfvyk5hs6x7dv9a6h4jarzehh4450z5glyrfwc9"],"Address+#15":["bcrt1q9jwhkkajz3lc3g5fghnckce2h57th2s3rftm03"],"Address+#16":["bcrt1qyeaa967e249v629xh77xecu9jg2ll2c872vydf"],"Address+#17":["bcrt1q03tgpu4fk0xdp4j8u5qev7tcackjz0467wvg8x"],"Address+#18":["bcrt1qp3gwnzszege0lsd0u6e93yhh82gtnqyx4ayp4t"],"Address+#19":["bcrt1qh998ru3hj0ytqzyrnd336yf3kakaq9xzr2lgtl"],"Address+#2":["bcrt1qs4zevx7889na3fjpeq0anv7ysyplpaqex4064g"],"Address+#20":["bcrt1qj4u5pntf8tfj6ypq8r3wy0wtalvswwshh3vmaw"],"Address+#3":["bcrt1qd9lht7qwwa57gt2hyuq94efpxy6d28ux9dsmsr"],"Address+#4":["bcrt1qzsk2sfyvc233e6scyr3njnaqpvzxt0nej7x0l5"],"Address+#5":["bcrt1qdj6crjvykkglhyuwcdw8278plfjw4zh4ukdp0w"],"Address+#6":["bcrt1q8eag5udkswndxxsu90zv3sa4twhl7kzfpkh4vu"],"Address+#7":["bcrt1qmp8du6m4ppxh0laq7m6weckr2apqt0qufv335d"],"Address+#8":["bcrt1q30harpktj46tjxp95tzqskqnpfu692gqmmrxx0"],"Address+#9":["bcrt1q260370a32494ypeu5p22qt3r6s6uxzs3jfmuv9"],"Change+#0":["bcrt1qvfh56wqnx37yzhxh0sd2wqcq9hcqv0h9n3p5tr"],"Change+#1":["bcrt1q9vrxy7vfnet88dmmhvv956p9pt6rlhgyna004v"],"Change+#10":["bcrt1qrhvf7g3vfle266n3wegvu57f8093nt054uj5zn"],"Change+#11":["bcrt1qrdjcc2rm9p4xkk44hgpv5tvgev9x8zptjle78r"],"Change+#12":["bcrt1q6pnltus7eesm68xuagp3lpg8u4d95mczm07qec"],"Change+#13":["bcrt1qcdlr9gv45d8tlwckt9k6wc2kjw9el0cvwjz0ev"],"Change+#14":["bcrt1q6s5zkys5tkmpp0tzr4w4rsj2x0hw38xd4wtw85"],"Change+#15":["bcrt1qptwll3zgaj6up8zn9epuy9pplmzcnztmk7esz7"],"Change+#16":["bcrt1qsq6uce38zyemaxwwcvnk4mdwd25ke4h9ttnsrp"],"Change+#17":["bcrt1q6mkt2zqt49xluc06hkpglefrajxdvlr96rgaku"],"Change+#18":["bcrt1qh8cv59r7xm668wrd26p5r9l8rzjy4723pt8yg2"],"Change+#19":["bcrt1qqu7xcy5xq8emfytjtca603y6gamf8keunslnef"],"Change+#2":["bcrt1qp4rcnrjrj9enase9t5mrqc9ak4ft4ge8jk99g0"],"Change+#3":["bcrt1qkt7apm6wyu3hyla320um4gflgeu0f5e45v0xdu"],"Change+#4":["bcrt1qta69rrfq3uz9w5zffe4agtqjw8j8xcfvkp4zmn"],"Change+#5":["bcrt1q90aqfc3n4wq9dflml84e3zqc84v2hl0t7ej8d6"],"Change+#6":["bcrt1qrtwfy7jfvsvu6tertyyzcv7m3zysgudn3ruygk"],"Change+#7":["bcrt1qpf9az5swm23r9rveahgxrzqe0j86nacekp0pcn"],"Change+#8":["bcrt1qarwc5k2zjnqzys0fde9lm3g89d8xrh3n8w9ecp"],"Change+#9":["bcrt1q2x4we425u7rr2q4hcxw5d68u4yz9xhhzq5qp7y"]}},{"name":"SimpleMyNiceDevice","alias":"simplemynicedevice","description":"Single+(Segwit)","address_type":"bech32","address":"bcrt1qavs8svrqcgnrzktvsn27z3w7acq0dljgnf8k89","address_index":0,"change_address":"bcrt1qx70x540rcy26usrdxpv27l5qfhx7rmv9sjdx6c","change_index":0,"keypool":20,"change_keypool":20,"recv_descriptor":"wpkh([1831e62e/84h/1h/0h]tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY/0/*)#zpjep3zd","change_descriptor":"wpkh([1831e62e/84h/1h/0h]tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY/1/*)#n4hcuyj4","keys":[{"original":"vpub5Z8h5qLg5f2vEKbwDtoyqsiFwbFUiu7kD47LceVRS6Um4m94rfuxjRxghaYYywPh3dqhyd6rZ4TQ9bBCzfWRZgwpdydgbmmGLkx9s6MGKaU","fingerprint":"1831e62e","derivation":"m/84h/1h/0h","type":"wpkh","xpub":"tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY"}],"devices":["mynicedevice"],"sigs_required":1,"pending_psbts":{},"fullpath":"/home/kim/.specter/wallets/regtest/simplemynicedevice.json","last_block":"795bf8af85caec61d7f2afe8de16376fc82fb7ffb8c15c19538fb2b20aece35c","blockheight":555,"labels":{"Address+#0":["bcrt1qavs8svrqcgnrzktvsn27z3w7acq0dljgnf8k89"],"Address+#1":["bcrt1q8rljpakhphcfpxm8xemrly20ql6yd5wjuuutj9"],"Address+#10":["bcrt1q9mdntq8jk8zzljws62dzh8hj0rm6hfdr004pc4"],"Address+#11":["bcrt1ql3dz29lxpze477yk6gmnggkp3rgf77k97mr0f4"],"Address+#12":["bcrt1q9msq63tvdfs95tqhjjn56tnx89h70z5smyl30g"],"Address+#13":["bcrt1qjlzqrd7c32n0qzwxy6ajlvs430kjg7ddw4wmdj"],"Address+#14":["bcrt1q9nkj49r20reerdg876quavk04dzhqee4kamlzw"],"Address+#15":["bcrt1q66ax3vd4gpvw0t0yxcy603zuluy9k00furn33f"],"Address+#16":["bcrt1qvgprv9rrqzagjwls373qedhrnnleej4xsfqgpr"],"Address+#17":["bcrt1qyc53ydgnjlap6xmh9sqhdr97mt202nc504q3kp"],"Address+#18":["bcrt1qxaj0kfylekkme6n0xn3mshqzs87wn4286f2zap"],"Address+#19":["bcrt1qr89qp6gfzayj0n7z95ldxpd5mpelsvgcjqmmqp"],"Address+#2":["bcrt1qsa6daky377pfa6l7fy5l4jqfsuzvcm446dr4c5"],"Address+#20":["bcrt1qmkrf7q6xwglr4qy6ud5huxmnyt5u5sfgjuhdau"],"Address+#3":["bcrt1q4tgdvyjj0yf7nndhgg9lmq2jxgcvjg8gjeanzr"],"Address+#4":["bcrt1qh52a7czwnfxjqscjjs93v93yxtl8xn8a40fxt4"],"Address+#5":["bcrt1qy2rf22rsr2e666znuz4eu6xzjavjdve94cx5mv"],"Address+#6":["bcrt1q924yzyjp5atqncpchqktw34tc940r5srlnuayx"],"Address+#7":["bcrt1qwq0jwjwqsp88e5nyjya0spcrpgsq2rjwe4x9jr"],"Address+#8":["bcrt1q2j98qnftddzd7wyntz8z670zdzruwjcjj86xr8"],"Address+#9":["bcrt1q09tzudywksddasce227y0vrdzc2vn4rfqrsxgk"],"Change+#0":["bcrt1qx70x540rcy26usrdxpv27l5qfhx7rmv9sjdx6c"],"Change+#1":["bcrt1qqppsgsm6ptvvr70vc09qjndgxu6f5u0p8k70x4"],"Change+#10":["bcrt1qtlyw98ptysa9du729us9es898tytfv4mvtgqjl"],"Change+#11":["bcrt1q407v4s0hltmgkt9gwtlm0j3462zym6et3vxmy8"],"Change+#12":["bcrt1qr797mc9avjkk33pk4yjssujlcxq6l8hywt94mw"],"Change+#13":["bcrt1q6mfq6ppdarvdx5wmekj70qj83usf94ep5zdx62"],"Change+#14":["bcrt1qhj69sl8pcgzgka9q0vx0xelcc48wqd0l5aklhf"],"Change+#15":["bcrt1q6r7hn5d0rp88uq3dmytld3uyetk3jqknmr52nk"],"Change+#16":["bcrt1qlaqt33z3wh4zzlsvj5cr4deeprckjhgme48gcf"],"Change+#17":["bcrt1qyjsenxez4frcwwxlma0shdznt96d70n0eq8qlj"],"Change+#18":["bcrt1q7jugneskcs3gh65vswnyt6ps5f9sv6xralkjd4"],"Change+#19":["bcrt1qrk6hxfwlta7medgx84lectem3x2s7s3ag8gch9"],"Change+#2":["bcrt1qqv3vxjje9093t8yg94k2p4ee8hqeuz4n6hdnyd"],"Change+#3":["bcrt1q2m7xte8sfp3xyda5gvpv99cpnvalds5rmm0k3m"],"Change+#4":["bcrt1qryyt3c8gzrqxrxnajnwx9nmheqs7v8r4vnwuhh"],"Change+#5":["bcrt1qtwu40gd48rpt4u9tt9kd3qlln5k2p8jvtk48e5"],"Change+#6":["bcrt1qkeeva9ahznrt5kx84frqyvpgtxsgd370g5lwvl"],"Change+#7":["bcrt1qhxhnwvea8ueu6094eanehac2hd8u06fv9xsw5s"],"Change+#8":["bcrt1q8rpmqpnz6nl4r2tyhetwtutkjgeyjkn8mdsqgt"],"Change+#9":["bcrt1qpz3yg44mkrqev2p2dmgcyzxpm3z8vxg70qaka4"]}}]
    """
    restore_devices = """
        [{"name":"myNiceDevice","alias":"mynicedevice","type":"specter","keys":[{"original":"vpub5Z8h5qLg5f2vEKbwDtoyqsiFwbFUiu7kD47LceVRS6Um4m94rfuxjRxghaYYywPh3dqhyd6rZ4TQ9bBCzfWRZgwpdydgbmmGLkx9s6MGKaU","fingerprint":"1831e62e","derivation":"m/84h/1h/0h","type":"wpkh","xpub":"tpubDDArDQWC6J5LCiB2LoNKTyEdcee2bXboauk5XzLLY1zQvFSESD6B7zwnz2YWWFemepcE69or1UzYcLtwpvBh3bmKSFmqT84UUAfrQCcaTMY"}],"fullpath":"/home/kim/.specter/devices/mynicedevice.json"},{"name":"btchot","alias":"btchot","type":"bitcoincore","keys":[{"original":"upub5EmTFhjqMF8gZxNQVrKm6r17kQXxVKSLD35qzQTGTLk8oiWfVLJ7DS7A5vfS35xh8L2PYJc52s2ipd9etbH35RBR5y8RMvcZ4SgdAxAkea6","fingerprint":"0c28f912","derivation":"m/49h/1h/0h","type":"sh-wpkh","xpub":"tpubDDdsgwaGWZiaPe8cT7fiw2czbS4xJZutW1Eoh9C4wGdfiJd4KXdtE4kQPacyZJsh99uiQJucwwvRAfUxSYNKMZgWkaxzoBjFTaTy6eW23vo"},{"original":"vpub5ZnVM9YwHPoDGsp7mqzxLXh1LcNfiUanF472658YeKiU4SgUSzrozSXtrSiuLC5j9G8XZzL7yrNXEcv2dVqE1zMY5zCwAN6zQWcs2mkJiME","fingerprint":"0c28f912","derivation":"m/84h/1h/0h","type":"wpkh","xpub":"tpubDDpeUiiTJ2qdFGPCtkZHxdDP1fmDb74qcujm1QyTkFE7uvye2Y32P1X18tirrWLokSu3gX37SGufhNdmTkWVVuB2tGM61iQCXvLZZvCvChu"},{"original":"Upub5S9TthRDjzLbvxPSdzKTgn5gt6ySD3VggUhXvzGHrFRWTeYbNpMWv393Kt51vfSpSXfNzxgYR4ngVrz9DAgQiNupMWsuJUfdnBMpzwvzGET","fingerprint":"0c28f912","derivation":"m/48h/1h/0h/1h","type":"sh-wsh","xpub":"tpubDE7oChXDLMN8L4zGebCSgtMm1LUAowHefBCpiTjYxQUdk465ScK1qYvMpq55tT8vDtUizNyySwHsijhgTtcjr3JFBfc5LLKLHasJLgkZBZ9"},{"original":"Vpub5kyjCN68tft5q456dEsqHrQexej4wuh2S9Sdy4dvGTvvh85KMCt7PsninSvYV71jnWHrM8MF43FD5mviiChvJWVx96VJaj866zBRZM8KdhA","fingerprint":"0c28f912","derivation":"m/48h/1h/0h/2h","type":"wsh","xpub":"tpubDE7oChXDLMN8NsUooUyC5sbDuv5McBVVVjRhy9DHzccAvRoaALg3hKuuGBy2Sz3vADzPb547dFPrRN2hFEEEdwCn6uX42fxJLfdFWbUw1fT"}],"fullpath":"/home/kim/.specter/devices/btchot.json"}]
    """
    result = client.get('/settings/general', follow_redirects=True)
    assert b'Load Specter backup:' in result.data
    result = client.post("/settings/general", data=dict(action="restore", explorer="", unit="btc", loglevel="debug", restoredevices=restore_devices, restorewallets=restore_wallets))
    assert b"Specter data was successfully loaded from backup." in result.data

def login(client, password):
    ''' login helper-function '''
    result = client.post('/login', data=dict(
        password=password
    ), follow_redirects=True)
    assert b'We could not check your password, maybe Bitcoin Core is not running or not configured?' not in result.data
    return result

def logout(client):
    ''' logout helper-method '''
    return client.get('/logout', follow_redirects=True)
