## Running Specter Desktop over a Tor hidden service

Specter Desktop protects your security and privacy by running on a local server that only talks to your own bitcoin node. But what if you need to check a wallet balance or generate and sign transactions when you're away from your home network?

Configuring your router to let you VPN into your home network is probably the easiest solution.

But you can also make Specter Desktop available outside of your network via a Tor hidden service. A hidden service generates an .onion address so Specter can be accessed from a Tor browser from anywhere in the world. This does not require any port forwarding on your router.

Make sure authentication is enabled to avoid access to your Specter by random strangers in the internet. It can be configured in the `Settings -> Authentication` tab.
"Multiuser" mode is something you want for simple authentication, "RPC password as PIN" makes your Specter available only if Bitcoin Core is running and configured with a static rpcpassword but can cause problems if Bitcoin Core shuts down.

### Security note
Tor support, like Specter Desktop as a whole, should be treated as a work-in-progress that is not yet vetted as being fully secure.

### Install Tor service
Install Tor on the same server that you'll be running Specter Desktop:
* [Debian / Ubuntu](https://2019.www.torproject.org/docs/debian.html.en)
* [macOS](https://2019.www.torproject.org/docs/tor-doc-osx.html.en)

### Configure Tor port
Update your `torrc` config file (usually `/etc/tor/torrc` or `/usr/local/etc/tor/torrc` on macOS Homebrew installs) and uncomment the `ControlPort` line.
```sh
## The port on which Tor will listen for local connections from Tor
## controller applications, as documented in control-spec.txt.
ControlPort 9051
```

You may also need to add the following lines in the `torrc` file:

```sh
CookieAuthentication 1
CookieAuthFileGroupReadable 1
```

Restart the Tor service:
* `sudo /etc/init.d/tor restart` on linux
* `brew services restart tor` on macOS Homebrew installs

On Linux you also need to add yourself to the Tor group (depends on the system `debian-tor` on Ubuntu):
```sh
usermod -a -G debian-tor `whoami`
```

### Running with Tor using command line

You can start the server using `--tor` flag or enable it in the web interface:

```sh
$ python3 -m cryptoadvance.specter server --tor
```

Amongst the startup output you'll see:
```
...
* Started a new hidden service with the address of blahblahbla123asbfdgfd.onion
```

Point a Tor browser at that onion address and you will have (reasonably?) secure access to your Specter Desktop from anywhere in the world!

Each time Specter Desktop restarts the same onion address will be re-enabled.

If you'd like to discard the existing onion address and force the creation of a new one, simply delete the `.tor_service_key` in the `~/.specter` folder and restart Specter Desktop.
