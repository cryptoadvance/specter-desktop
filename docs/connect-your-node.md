[TOC]
# Connect to your node
Specter is a very flexible tool and can be used in a lot of different setups. There are some popular setups which we want to address first. If you want to use Specter with MyNode or Raspiblitz, that might be easy but you might still want to have some guidance. Here is some awesome material to watch and study for MyNode users:

* BTC Sessions [showing](https://www.youtube.com/watch?v=ZQvCncdFMPo) how to start with Specter on Mynode
* Bitcoin-Magazine showing also [some things](https://www.youtube.com/watch?v=ZQvCncdFMPo) MyNode and Specter

If you want to use Specter with a node on your Windows machine: Ministry of Nodes [explains](https://www.youtube.com/watch?v=4koKF2MDXtk) that setup.

The installation on the Raspiblitz is quite simple as there is an installation option in the ssh-menu. 
There is also a walk-through on [how to connect the Specter Desktop App with the RaspiBlitz](https://d11n.net/connect-specter-desktor-with-raspiblitz.html).

Jameson Lopp has created a [tool](https://jlopp.github.io/bitcoin-core-config-generator/) to assist with bitcoin.conf creation for Linux/Windows/MacOS. It also explains some of the configuration options in detail.

## General thoughts
But let's approach the connection issue more generically. We assume here, that you want to setup everything in your local network. Every computer needs an IP address in your network. So either, Bitcoin Core is running on the same computer as Specter or on two different ones. But both should have private IP addresses - e.g. (most popular) 192.198.X.Y.
For this setup, you don't need to modify your router. Also your Bitcoin Core node doesn't need to be exposed to the internet.

If both are running on the same machine, there are usually a lot less potential network issues. If both are running as the same user, auto-detect can be used.

Let's look at all the issues which can potentially occur.

## Potential connection issues

The first thing you should do if it doesn't work out of the box is explicitly configure the connection to Bitcoin Core. For that, there are the following values to be set:
* Your Bitcoin RPC username is specified in your bitcoin.conf file on the computer where Bitcoin Core is running. If you open the file, it should like this: `rpcuser=bitcoin`
* Your Bitcoin RPC password can also be found in that file. Search for `rpcpassword=aVerySecretPassword`
* Your node's IP address could simply be `http://localhost` if you're running Bitcoin Core on the same machine as Specter. Otherwise, it's, as discussed above, a local network-address starting often enough with 192.168.X.Y.
* Your nodes RPC port (usually 8332)

### Connection failure

`Process finished with code -1Error message: Failed to connect`

This error message can have one of two causes:
1. The IP address is wrong: Double check it
2. The port is wrong (closed) or the service can't be accessed because of other reasons

Checking the IP address is usually easy: Open a command-line and [ping the address](https://www.howtogeek.com/355664/how-to-use-ping-to-test-your-network/). If the computer responds, it might still be the wrong IP but at least you proved that there is an computer existing with that address.

Checking whether the port is open, is a bit more difficult and you might want to do that only if you've went through the hints below. On mainnet, it's usually 8332. If you're on Windows, you can use [one of these tools](https://techtalk.gfi.com/scan-open-ports-in-windows-a-quick-guide/) to check whether the port is open.

Also you should check your bitcoin.conf. There could be several reasons why your service is not available on the port:

### localhost bind-only

The rpc service needs to bind to the right IP address and port. If you're running Specter on the same machine than Core, something like this would be ok:
```
rpcbind=127.0.0.1:8332
```
(You can also specify the rpc port once with rpcport=8332 so you can skip it
with rpcbind etc.)

However, if you're running it on a different machine, you need to make your service available to the outside. That's done by:
* binding it to all network interfaces like `rpcbind=0.0.0.0:8332`
* and also allowing everyone (specifically your machine) to connect to it: `rpcallowip=0.0.0.0/0`

Note: This allow option is only for troubleshooting; ideally you would limit
it to your local subnet or the machine running Specter that wants to talk to the
node via RPC.

### Example - Specter connecting to a remote node: 

Specter is running on your PC with the local network IP-address 192.168.178.55. You want to allow this machine to be able to send RPC requests and connect Specter to the external node, which has the IP-address 192.168.178.45 in your local network. You also want to be able to do RPC requests on the external node itself, i.e. directly or logged in with a ssh-session. You have to specify the two options in bitcoin.conf as follows:
```
rpcallowip=192.168.178.55/24
rpcbind=192.168.178.45
rpcbind=127.0.0.1
```
Note: both options can be specified multiple times.

### firewall issues

Often enough there are firewalls installed on the machines running services. Usually this is the case if it takes very long until you get a result after clicking the test button in Specter. The solution here is very specific to the firewall used on the server.

"ufw" is a popular and easy to use firewall (Raspiblitz is using it for example). 
This is how you open the port:
```
sudo ufw allow 8332
sudo ufw enable
```
Note: Again, ideally, you would restrict the access further after trouble shooting:

```
sudo ufw allow from SPECIFIC IP to any port 8332
```

### Server responded with error code 401:
This issue is due to a wrong username or password configuration. Double-check that the values configured match those on the bitcoin.conf

