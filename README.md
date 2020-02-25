# Specter Desktop

[![Build Status](https://travis-ci.org/cryptoadvance/specter-desktop.svg?branch=master)](https://travis-ci.org/cryptoadvance/specter-desktop)

## DISCLAIMER

This software is **WORK IN PROGRESS and NOT READY TO USE YET**. Currently tested only in Chrome, so in other browsers it may look weird.

If something doesn't work open an issue here or ask a question in our [Telegram group](https://t.me/spectersupport) or [Slack](https://join.slack.com/t/spectersupport/shared_invite/enQtNzY4MTQ2MTg0NDY1LWQzMGMzMTk2MWE2YmVmNzE3ODgxODIxNWRlMzJjZTZlMDBlMjA5YzVhZjQ0NzJlNmE0N2Q4MzE0ZGJiNjM4NTY).

## Why?

Bitcoin Core has a very powerful command line interface and a wonderful daemon. Using PSBT and HWI it can also work with hardware wallets, but at the moment it is too linux-way. The same applies to multisignature setups. 

The goal of this project is to make a convenient and user-friendly GUI around Bitcoin Core with a focus on multisignature setup with airgapped hardware wallets.

At the moment we are working on integration of our [Specter-DIY hardware wallet](https://github.com/cryptoadvance/specter-diy) that uses QR codes as a main communication channel, and ColdCard that uses SD cards. Later on we plan to integrate "hot" hardware wallets using [HWI tool](https://github.com/bitcoin-core/HWI) and [Junction](https://github.com/justinmoon/junction).

## How to run

Clone the repo, install dependencies:

HWI support requires `libusb` (necessary? Or is `pip install libusb1` sufficient?):
* Ubuntu/Debian: `sudo apt install libusb-1.0-0-dev libudev-dev`
* macOS: `brew install libusb`

```sh
git clone https://github.com/cryptoadvance/specter-desktop.git
cd specter-desktop
virtualenv --python=python3 .env
source .env/bin/activate
pip3 install -r requirements.txt
pip3 install -e .
```

Run the server:

```sh
cd specter-desktop
python3 -m cryptoadvance.specter server
```

You can also run it as a daemon, using tor, provide ssl certificates to run over https. Https is especially important because browsers don't allow the website to access camera without secure connection, and we need camera access to scan QR codes.

An example how to run specter server in the background (`--daemon`) with ssl certificates (`--key`, `--cert`) over tor:

```sh
python -m cryptoadvance.specter server --tor=mytorpassword --cert=./cert.pem --key=./key.pem --daemon
```

If your Bitcoin Core is using a default data folder the app should detect it automatically. If not, consider setting `rpcuser` and `rpcpassword` in the `bitcoin.conf` file and in the app settings.

Have a look at [DEVELOPMENT.md](https://github.com/cryptoadvance/specter-desktop/blob/master/DEVELOPMENT.md) for further information about hacking on specter-desktop.

## Detailed instructions

- Beyond local network - how to forward your node through a cheap VPS: [docs/reverse-proxy.md](docs/reverse-proxy.md)
- Setting up Specter over Tor: [docs/tor.md](docs/tor.md)
- Using self-signed certificates in local network or Tor: [docs/self-signed-certificates.md](docs/self-signed-certificates.md)

## A few screenshots

### Adding a new device

![](screenshots/devices.jpg)

![](screenshots/device_keys.jpg)

### Creating a new wallet

![](screenshots/wallets.jpg)

![](screenshots/new_multisig.jpg)

### Wallet interface

![](screenshots/transactions.jpg)

![](screenshots/receive.jpg)

![](screenshots/send.jpg)

### Configuration

![](screenshots/bitcoin-rpc.jpg)
