# Connect your node
Specter is a very flexible tool and can be used in a lot of different setups. There are some more popular setups which are we want to address here, first. If you want to use Specter with MyNode or Raspiblitz, that might be easy but you might still want to have some guidance. So for some obcious setups, here are some awesome material to watch and study:
* BTC Sessions [showing](https://www.youtube.com/watch?v=ZQvCncdFMPo) how to start with Specter on Mynode
* Bitcoin-Magazine showing also [some things](https://www.youtube.com/watch?v=ZQvCncdFMPo) MyNode and Specter
* Ministry of Nodes [explains](https://www.youtube.com/watch?v=4koKF2MDXtk) how to run Bitcoin Core and Specter on the same windows-machine

The installation on the raspiblitz is quite simple as there is a installation-option in the ssh-menu. Pretty straightforward however we're not aware of any video-walthrough for that. Ping us or make a PR if you're aware of anything for that.

# General thoughts
But let's approach the connection-issue from a generic view. We assume here, that you want to setup everything in your local network. Every Computer needs a IP-address in your network. So either, Bitcoin-Core is running on the same computer with specter or on two different one. But the both should have private IP-addresses like e.g. (most popular) 192.198.X.Y.
For this setup, you don't need to modify your router. Also your Bitcoi-Core-Node doesn't need to be exposed on the internet.

If both are running on the same machine, there are usually a lot less potential network-issues. If both are running as the same user, autodetect can be used.

Let's look at all the issues which can potentially occur one by one.

# Potential connection issues

The first thing you should do if it doesn't work out of the box is explicitely configuring the connection to Bitcoin Core. For that, there are the following values to be set:
* Your Bitcoin RPC username is specified in your bitcoin.conf file on the computer where Bitcoin Core is running. If you open the file, you should find that value in a like like this: `rpcuser=bitcoin`
* Your Bitcoin RPC password can also be found in that file. Search for a line like `rpcpassword=aVerySecretPassword`
* Your nodes IP address could simply be `http://localhost` if you're running Bitcoin-Core on the same machine than specter. Otherwise, it's, as discussed above, a local network-address starting often enough with 192.168.X.Y.
* Your nodes RPC port (usually 8332)

## Connection Failure

`Process finished with code -1Error message: Failed to connect`

This error-message can be one of two causes:
1. The IP-Address is wrong: Double check it
2. The port is wrong (closed) or the service can't be accessed because of other reasons

Checking the ip-address is usually easy: Open a command-line and [ping the address](https://www.howtogeek.com/355664/how-to-use-ping-to-test-your-network/). If the computer responds, it might still be the wrong IP but at least you proved that there is an computer existing with that address.

Checking whether the port is open, is a bit more difficult and you might want to do that only if you've went through the hints below.. On mainnet, it's usually 8332. If you're on windows, you can use [one of these tools](https://techtalk.gfi.com/scan-open-ports-in-windows-a-quick-guide/) to check whether the port is open.

Also you should check your bitcoin.conf. There are several reasons why your service is not available on the port:

### localhost bind only

The rpc-service needs to bind to the right IP and port. If you're running specter on the same machine than Core, something like this would be ok:
```
rpcbind=127.0.0.1:8332
```

However if you're running it on a different machine, you need to make your service available to the outside. That's done by:
* binding it to all network-interfaces like `rpcbind=0.0.0.0:8332`
* and also allowing everyone (pr specifically your machine) to connect to it: `rpcallowip=0.0.0.0/0`

### firewall issues

Often enough there are firewalls installed on the machines running services. Usually this is the case if it takes very long until you get a result after clicking the test-button. The solution here is very specific to the firewall used on the server.

"ufw" is a popular and easy to use firewall. This is how you open the port:
```
sudo ufw allow 8332
sudo ufw enable
```

### Server responded with error code 401:
This issue is due to a wrong password or username configured. Double-check that the values configured match those on the bitcoin.conf

