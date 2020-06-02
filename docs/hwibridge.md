# Specter HWIBridge
If you are running your Bitcoin Core on a remote machine,
such as an AWS or Heroku machine, or if you are using a separate hardware like [RaspiBlitz](https://github.com/rootzoll/raspiblitz), [myNode](https://mynodebtc.com), or [Nodl](https://www.nodl.it),
you may also prefer to run Specter on that same remote machine.

In such case, Specter will not be able to connect to USB devices connected to the local machine you use to access Specter.
This is because Specter uses HWI for hardware wallets integration, which can only access devices connected directly to the machine it is running on.

The following steps will help you set up a local `Specter HWIBridge`, which you could connect to the remote server and will make it detect devices connected to your local machine:

1. Run Specter normally on the remote server machine.
2. On the local machine you are accessing Specter from, [install Specter](../README.md#how-to-run) as well and run it with the `--hwibridge` flag.
(Note, if you are running Specter as a Tor hidden service, you will have to set up the local HWIBridge Specter as a [Tor hidden service](tor.md) as well)
3. Then open `YOUR_LOCAL_SPECTER_URL:PORT/hwi/settings` (i.e. `http://127.0.0.1:25441/hwi/settings`).
4. In the `Whitelisted domains` form field, enter the domain of your remote Specter server you are connecting to and click update.
5. Now open the remote Specter server URL and go to settings.
6. In the bottom, find `HWI Bridge URL`, and enter there the URL of your local Specter HWIBridge along with `/hwi/api/` (i.e. `http://127.0.0.1:25441/hwi/api/`), then click save.
7. You should now be able to use hardware wallets connected via USB to your local node with the Specter running on the remote server.

We are currently working to make this process much easier and simpler.
In the meantime, if you have any further questions or need help, please either open a GitHub issue, or ask in the [Specter Telegram group](https://t.me/spectersupport).