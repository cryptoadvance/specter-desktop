## Running Specter Desktop over a Tor hidden service

Specter Desktop protects your security and privacy by running on a local server that only talks to your own bitcoin node. But what if you need to check a wallet balance or generate and sign transactions when you're away from your home network?

Configuring your router to let you VPN into your home network is probably the easiest solution.

But you can also make Specter Desktop available outside of your network via a Tor hidden service. A hidden service generates a secret .onion address that only you know and which can be accessed from a Tor browser from anywhere in the world. This does not require any port forwarding on your router.

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

On Linux you also need to add yourself to the tor group (depends on the system `debian-tor` on Ubuntu):
```sh
usermod -a -G debian-tor `whoami`
```

### Running with Tor using command line

You can start the server using `--tor` flag:

```sh
$ python3 -m cryptoadvance.specter server --tor
```

### Configure environment variables

Update the `.flaskenv` file in the project root. Set `CONNECT_TOR` to 'True' and set `FLASK_ENV` to 'production':
```sh
PORT=25441

# If you want to serve over a Tor hidden service, also set FLASK_ENV=production.
#   (The autoreloading in 'development' mode causes problems with the Tor connector)
CONNECT_TOR=True

FLASK_ENV=production
#FLASK_ENV=development
```

### Launch with Tor

Now just start Specter Desktop as usual:

```sh
$ python3 -m cryptoadvance.specter server
```

Amongst the startup output you'll see:
```
 * Connecting to tor
Started a new hidden service with the address of abcd1234efgh5678.onion
```

Point a Tor browser at that onion address and you will have (reasonably?) secure access to your Specter Desktop from anywhere in the world!

Each time Specter Desktop restarts the same onion address will be re-enabled.

If you'd like to discard the existing onion address and force the creation of a new one, simply delete the `.tor_service_key` in the project root and restart Specter Desktop.
