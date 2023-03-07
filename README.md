![](https://img.shields.io/badge/Bitcoin-000000?style=flat&logo=bitcoin&logoColor=white)
[![docs -  netlify](https://img.shields.io/badge/docs-_netlify-2ea44f)](https://docs.specter.solutions/desktop/)
![Cirrus CI - Specific Task Build Status](https://img.shields.io/cirrus/github/cryptoadvance/specter-desktop?label=pytest&task=test)
![Cirrus CI - Specific Task Build Status](https://img.shields.io/cirrus/github/cryptoadvance/specter-desktop?label=cypress&task=cypress_test)
![GitHub Release Date](https://img.shields.io/github/release-date/cryptoadvance/specter-desktop)
[![PyPI version](https://img.shields.io/pypi/v/cryptoadvance.specter)](https://pypi.org/project/cryptoadvance.specter/)
![Docker Image Version (latest by date)](https://img.shields.io/docker/v/lncm/specter-desktop?label=docker)
![GitHub all releases](https://img.shields.io/github/downloads/cryptoadvance/specter-desktop/total)

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Specter Desktop](#specter-desktop)
  - [DISCLAIMER](#disclaimer)
  - [Documentation and Video Walkthrough](#documentation-and-video-walkthrough)
  - [Why?](#why)
  - [Help wanted: Do you like Specter?](#help-wanted-do-you-like-specter)
  - [How to run](#how-to-run)
    - [Using the Specter Desktop app](#using-the-specter-desktop-app)
    - [Installing Specter from Pip](#installing-specter-from-pip)
    - [Connect Specter to Bitcoin Core](#connect-specter-to-bitcoin-core)
  - [Tips and tricks (detailed instructions)](#tips-and-tricks-detailed-instructions)
  - [Errors, doubts.. Read our FAQ!](#errors-doubts-read-our-faq)
  - [Setting up Specter Desktop](#setting-up-specter-desktop)
    - [Select how to connect to Bitcoin network](#select-how-to-connect-to-bitcoin-network)
    - [Add a new device](#add-a-new-device)
    - [Create a new wallet](#create-a-new-wallet)
    - [Wallet interface](#wallet-interface)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Specter Desktop

    "A specter is haunting the modern world, the specter of crypto anarchy."
    The Crypto Anarchist Manifesto - Timothy C. May - Sun, 22 Nov 92 12:11:24 PST

## DISCLAIMER

This software might be ready to be used but at your own risk.

If something doesn't work open an issue here or ask a question in our [Telegram group](https://t.me/spectersupport).

## Documentation and Video Walkthrough

* ![video](https://www.youtube.com/embed/v3SEp0SkOWs) [Watch here](https://www.youtube.com/watch?v=v3SEp0SkOWs)
* [documentation](https://docs.specter.solutions/desktop/)

## Why?

Bitcoin Core has a very powerful command line interface and a wonderful daemon. Using PSBT and [HWI](https://github.com/bitcoin-core/HWI) it can also work with hardware wallets, but at the moment it is too linux-way. The same applies to multisignature setups. 

The goal of this project is to make a convenient and user-friendly User Interface around Bitcoin Core with a focus on multisignature setup with airgapped signing devices (aka hardware wallets).

At the moment Specter-Desktop is working with all major hardware wallets including:
- SeedSigner
- Specter DIY (optionally airgapped, using QR codes)
- Blockstream Jade
- ColdCard (optionally airgapped, using an SD card)
- BitBox02
- Passport
- Electrum (optionally airgapped, if running Electrum on an airgapped computer/phone)
- Keystone (airgapped, using QR codes)
- Trezor
- Ledger
- KeepKey


We also support using the Bitcoin Core as a hot wallet, by importing or generating a random BIP39 mnemonic, but this feature is experimental and we do not recommend using it at this stage.
We plan to add support for other hardware wallets as they come up. If you are interested in using Specter with a hardware wallet currently unsupported, let us know by opening an issue here or asking in our [Telegram group](https://t.me/spectersupport).

## Help wanted: Do you like Specter?
Please help us to push forward, fix bugs, refine FAQs and please help each other in the support channel.
As a small team on a tiny budget we are working hard to make Specter better every day – for Bitcoin, for you and for us.

## How to run

### Using the Specter Desktop app
The easiest way to run Specter Desktop is by installing the Specter Desktop app, which you can find on the [GitHub release page](https://github.com/cryptoadvance/specter-desktop/releases).
With this method, all you need to do is just download the right file for your operating system and install it like a normal desktop app (Debian buster is only [partially supported](https://github.com/cryptoadvance/specter-desktop/issues/769))

### Installing Specter from Pip
* Specter requires Python version 3.9 to 3.10.
* Bitcoin Core node should be at least v0.19+, better if it's the latest one from [bitcoincore.org](https://bitcoincore.org/en/download/).
* HWI support requires `libusb` 
  * Ubuntu/Debian: `sudo apt install libusb-1.0-0-dev libudev-dev python3-dev`
  * macOS: `brew install libusb`
  * Windows: follow instructions in [`windows.md`](docs/windows.md)
  * Arch: `sudo pacman -Syu && sudo pacman -S libusb`
  * Fedora/CentOS: `sudo yum -y install libusb libudev-devel python3-devel`
 * Install Specter
```sh
pip3 install cryptoadvance.specter
```
* Run Specter
```sh
python3 -m cryptoadvance.specter server 
```
* Upgrade Specter
```sh
pip3 install cryptoadvance.specter --upgrade
```

After that, Specter will be available at [http://127.0.0.1:25441/](http://127.0.0.1:25441/).

The above installation-method is quite easy but you have to trust pypi. If you want to verify the software completely yourself while still installing via pip3, you can do something like this (adjust yourself for other versions):
```
wget https://github.com/cryptoadvance/specter-desktop/releases/download/v1.7.0/cryptoadvance.specter-1.7.0.tar.gz
wget https://github.com/cryptoadvance/specter-desktop/releases/download/v1.7.0/SHA256SUMS
sha256sum --ignore-missing --check SHA256SUMS
wget https://github.com/cryptoadvance/specter-desktop/releases/download/v1.7.0/SHA256SUMS.asc
gpg --verify SHA256SUMS.asc
# Now, let's extract the requirements-file and install all requirements with require-hashes
tar -xvzf cryptoadvance.specter-1.7.0.tar.gz cryptoadvance.specter-1.7.0/requirements.txt
# create your ususal virtualenv
virtualenv --python=python3 .env
# activate
pip3 install -r cryptoadvance.specter-1.7.0/requirements.txt --require-hashes --upgrade
# The package cryptoadvance.specter itself cannot be included into requirements.txt
# But we have checked the checksum before so it's safe to install without checking it's hash
pip3 install cryptoadvance.specter-1.7.0.tar.gz
```


You can also run it using Tor, provide SSL certificates to run over https. Https is especially important because browsers don't allow the website to access the camera without secure connection, and we need camera access to scan QR codes.

An example how to run Specter server with SSL certificates (`--key`, `--cert`) over Tor (make sure to walk through the [Tor-document](docs/tor.md) ):

```sh
python3 -m cryptoadvance.specter server --tor --cert=./cert.pem --key=./key.pem
```

### Connect Specter to Bitcoin Core

If your Bitcoin Core is using a default data folder the app should detect it automatically. If not, consider setting `rpcuser` and `rpcpassword` in the `bitcoin.conf` file or set in directly in the specter-app settings. 

If you are using Bitcoin Core with GUI, set `server=1` in `bitcoin.conf`. This setting allows other programs to talk to the rpc server of Bitcoin Core. It's automatically enabled when you are using bitcoind, but disabled in bitcoin-qt.

If you use Specter from a remote machine and want to use it with hardware wallets connected via USB, please read [this guide on setting up HWIBridge](docs/hwibridge.md) to facilitate such connection to hardware wallets. 

Have a look at [development.md](docs/development.md) for further information about hacking on Specter-desktop.

## Tips and tricks (detailed instructions)

- Setting up Specter over Tor: [docs/tor.md](docs/tor.md)
- Using self-signed certificates in local network or Tor: [docs/self-signed-certificates.md](docs/self-signed-certificates.md)
- Running Specter as a service on a linux machine: [docs/daemon.md](docs/daemon.md)
- Beyond local network - how to forward your node through a cheap VPS: [docs/reverse-proxy.md](docs/reverse-proxy.md)

## Errors, doubts.. Read our FAQ!

If you're stuck while installing/configuring Specter or you're looking for more informations about the project, read our [FAQ](docs/faq.md)!

## Setting up Specter Desktop

### Select how to connect to Bitcoin network

![image](https://user-images.githubusercontent.com/47259243/223425374-a3e68ac7-2bdb-48fe-a53b-59f235c59bd1.png)

Electrum server or...
![image](https://user-images.githubusercontent.com/47259243/223426046-dd225f00-ba18-45cb-871a-40efd7eefc1e.png)

...via Bitcoin Core node.
![image](https://user-images.githubusercontent.com/47259243/223426366-c3ba758a-34c4-4ce1-8aae-cf0cc335a892.png)


### Add a new device

Select signing device
![image](https://user-images.githubusercontent.com/47259243/223428531-2f3a04d4-177d-4626-8108-b66234892541.png)

Upload public keys
![image](https://user-images.githubusercontent.com/47259243/223427859-c06faec5-78ab-4592-9ba6-4018978280cc.png)


### Create a new wallet

Select the type of wallet
![image](https://user-images.githubusercontent.com/47259243/223429703-7bf1bb38-f8c2-4103-a681-8cfd02301a23.png)

Pick the device you want to use
![image](https://user-images.githubusercontent.com/47259243/223429929-4a0acd0a-7d9d-4b29-a7b0-5f52cf262f21.png)

Configure the wallet
![image](https://user-images.githubusercontent.com/47259243/223433687-199fd383-6948-4799-bac3-e1f3c0d766de.png)


### Wallet interface

Transactions & UTXOs
![image](https://user-images.githubusercontent.com/47259243/223434020-cc88c8f5-200d-4acb-967c-3fdf3e8a8776.png)

Receive & Change Addresses
![image](https://user-images.githubusercontent.com/47259243/223434274-5480dd02-4104-43b2-8f0e-28623f3464a9.png)

Send 
![image](https://user-images.githubusercontent.com/47259243/223434554-562802dc-467d-4d7e-bc83-1cd56c3239d2.png)

Settings -> Important for multi-signature wallets. Export printable PDF backup.
![image](https://user-images.githubusercontent.com/47259243/223435735-73a440c2-e2e0-4fb7-b755-54e265a4e34c.png)
