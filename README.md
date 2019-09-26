# Specter Desktop

## DISCLAIMER

This software is **WORK IN PROGRESS and NOT READY TO USE YET**. Currently tested only in Chrome, so in other browsers it may look weird.

If something doesn't work open an issue here or ask a question in our [Telegram group](https://t.me/spectersupport).

## Why?

Bitcoin Core has a very powerful command line interface and a wonderful daemon. Using PSBT and HWI it can also work with hardware wallets, but at the moment it is too linux-way. The same applies to multisignature setups. 

The goal of this project is to make a convenient and user-friendly GUI around Bitcoin Core with a focus on multisignature setup with airgapped hardware wallets.

At the moment we are working on integration of our [Specter-DIY hardware wallet](https://github.com/cryptoadvance/specter-diy) that uses QR codes as a main communication channel, and ColdCard that uses SD cards. Later on we plan to integrate "hot" hardware wallets using [HWI tool](https://github.com/bitcoin-core/HWI) and [Junction](https://github.com/justinmoon/junction).

## How to run

Clone the repo, install dependencies:

```
git clone https://github.com/cryptoadvance/specter-desktop.git
pip3 install flask flask_qrcode flask_socketio requests
```

Run the server:

```
cd specter-desktop
python3 server.py
```

Your bitcoin node should have `rpcuser` and `rpcpassword` set in the `bitcoin.conf` file.

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