# Purpose
Let's find a place to docoment non straightforward design decisions.

## 02nd Oct 2020 - Kim
It's already mentioned in Development.md. I spend far too much time figuring out that we have created a nasty workaround in server.py.
So the problem looks like this: The fixtures are creating the app anew for each test in test_controller. For some reason hwi-view-endpoints are somehow treated differently then the normal endpoints. As a result, the second test gets a app-object which, for some reason doesn't have the normal endpoints, but just the hwi-endpoint. A healthy app.view_functions looks like this:
```
{'static': <bound method _PackageBoundObject.send_static_file of <Flask 'cryptoadvance.specter.server'>>, 'hwi_server.index': <function index at 0x7f3d67e64d40>, 'hwi_server.api': <function api at 0x7f3d67e64c20>, 'hwi_server.hwi_bridge_settings': <function hwi_bridge_settings at 0x7f3d67e64b00>, 'combine': <function combine at 0x7f3d674bed40>, 'broadcast': <function broadcast at 0x7f3d6739a200>, 'index': <function index at 0x7f3d6739a320>, 'about': <function about at 0x7f3d6739a680>, 'login': <function login at 0x7f3d6739ac20>, 'register': <function register at 0x7f3d6739af80>, 'logout': <function logout at 0x7f3d6739ad40>, 'settings': <function settings at 0x7f3d673a05f0>, 'hwi_settings': <function hwi_settings at 0x7f3d673a04d0>, 'general_settings': <function general_settings at 0x7f3d673a09e0>, 'bitcoin_core_settings': <function bitcoin_core_settings at 0x7f3d673a0d40>, 'auth_settings': <function auth_settings at 0x7f3d673a4320>, 'new_wallet_type': <function new_wallet_type at 0x7f3d673a4440>, 'new_wallet': <function new_wallet at 0x7f3d673a47a0>, 'wallet': <function wallet at 0x7f3d673a4b00>, 'wallets_overview': <function wallets_overview at 0x7f3d673a4f80>, 'singlesig_setup_wizard': <function singlesig_setup_wizard at 0x7f3d673af200>, 'wallet_tx': <function wallet_tx at 0x7f3d673af560>, 'wallet_tx_history': <function wallet_tx_history at 0x7f3d673af8c0>, 'wallet_tx_utxo': <function wallet_tx_utxo at 0x7f3d673afc20>, 'wallet_receive': <function wallet_receive at 0x7f3d673aff80>, 'fees': <function fees at 0x7f3d67339320>, 'txout_set_info': <function txout_set_info at 0x7f3d67339680>, 'get_scantxoutset_status': <function get_scantxoutset_status at 0x7f3d673399e0>, 'get_wallet_rescan_progress': <function get_wallet_rescan_progress at 0x7f3d67339d40>, 'wallet_send': <function wallet_send at 0x7f3d67340320>, 'wallet_sendnew': <function wallet_sendnew at 0x7f3d67340440>, 'wallet_importpsbt': <function wallet_importpsbt at 0x7f3d673407a0>, 'wallet_sendpending': <function wallet_sendpending at 0x7f3d67340b00>, 'wallet_settings': <function wallet_settings at 0x7f3d67340f80>, 'new_device': <function new_device at 0x7f3d67347200>, 'device': <function device at 0x7f3d67347560>}
```

An unhelathy like this:
```
{'static': <bound method _PackageBoundObject.send_static_file of <Flask 'cryptoadvance.specter.server'>>, 'hwi_server.index': <function index at 0x7f12b3475d40>, 'hwi_server.api': <function api at 0x7f12b3475c20>, 'hwi_server.hwi_bridge_settings': <function hwi_bridge_settings at 0x7f12b3475b00>}
```

Feel free to beat me for the brittle if-clause in server.py but please solve the issue in the first place for this as well :-).

## 19nd Feb 2020 - k9ert
The ApplicationFactory-pattern is not that straightforward. There are loads of pifalls and different ways to go. While finding a proper way to do it, one thing became clear: You need to separate the instantiation and the initialisation of the Application.

(from singleton.py)
```python __main__.py
app = logic.create_app()
app.app_context().push()
# (...)
logic.init_app(app)
```
If you would put everything in the create-call, you can't import code which is dependent on an initialized ApplicationContext, you can't do "from flask import current_app". So you have to push the app_context but on the other side, you don't want to do that from within the create_app-function because this would be a quite shitty side-effect which srews up your whole dependency injection.