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

### Configure Tor authentication
```
$ tor --hash-password "your-tor-passphrase"
```
That returns a password hash such as:
```
16:CE9058DA89498A4160373C70FF7FFF70CC2E20B6788FC48F5C35B2E85B
```
Update your `torrc` config file (usually `/etc/tor/torrc` or `/usr/local/etc/tor/torrc` on macOS Homebrew installs). Uncomment the `ControlPort` line as well as the `HashedControlPassword` line. Remember to paste in your own hashed password result from above.
```
## The port on which Tor will listen for local connections from Tor
## controller applications, as documented in control-spec.txt.
ControlPort 9051
## If you enable the controlport, be sure to enable one of these
## authentication methods, to prevent attackers from accessing it.
HashedControlPassword 16:CE9058DA89498A4160373C70FF7FFF70CC2E20B6788FC48F5C35B2E85B
#CookieAuthentication 1
```

Restart the Tor service:
* `sudo /etc/init.d/tor restart` on linux
* `brew services restart tor` on macOS Homebrew installs


### Configure Specter Desktop to connect to Tor
Update the `.flaskenv` file in the project root. Set `CONNECT_TOR` to 'True' and set `FLASK_ENV` to 'production':
```
PORT=25441

# If you want to serve over a Tor hidden service, also set FLASK_ENV=production.
#   (The autoreloading in 'development' mode causes problems with the Tor connector)
CONNECT_TOR=True

FLASK_ENV=production
#FLASK_ENV=development
```

### Specify Tor secrets
The Tor password that we hashed above will need to be shared with Specter Desktop.

Copy the example `.env_example` file:
```
$ cp .env_example .env
```

And then edit `.env` and specify `TOR_PASSWORD`:
```
# The cleartext password that was entered into:
#   $ tor --hash-password "your-tor-passphrase"
TOR_PASSWORD=your-tor-passphrase
```

### Launch with Tor
Now just start Specter Desktop as usual:
```
$ python server.py
```

Amongst the startup output you'll see:
```
 * Connecting to tor
Started a new hidden service with the address of abcd1234efgh5678.onion
```

Point a Tor browser at that onion address and you will have (reasonably?) secure access to your Specter Desktop from anywhere in the world!

Each time Specter Desktop restarts the same onion address will be re-enabled.

If you'd like to discard the existing onion address and force the creation of a new one, simply delete the `.tor_service_key` in the project root and restart Specter Desktop.
