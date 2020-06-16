# Frequently Asked Questions

## ABOUT THE PROJECT

The goal of this project is to make a convenient and user-friendly GUI around Bitcoin Core with a focus on multisignature setup with airgapped (offline) hardware wallets. 

We first wanted to make a new hardware wallet (HWW), but after we understood that everything can be hacked, we decided to build a user-friendly Multisig Desktop App and nice DIY Hardware Wallet.

**Why is that good for Bitcoin?**

 - User: Better Security with multisig setup 
 - User: Better Privacy with own node 
 - HWW Makers: More HW wallets sold 
 - Node Makers: More Nodes sold 
 - Network: More nodes running 

We can actually incentivize the Bitcoin community to run their own node with this user-friendly multisig & node setup! 

## *Why the name Specter?*

    "A specter is haunting the modern world, the specter of crypto anarchy."
    The Crypto Anarchist Manifesto - Timothy C. May - Sun, 22 Nov 92 12:11:24 PST
    
Specter is that little ghost helping the sovereign cypherpunk to protect his property rights.
We are aware of the vulnerability (Spectre) and know there is an infinite game against vulnerabilities.
https://en.wikipedia.org/wiki/Spectre_(security_vulnerability)
In Bitcoin Cold storage we can use multisig setups and different hardware wallets to mitigate these risks, while protecting our privacy by verifying transactions on our own node.

## GENERAL QUESTIONS

## *How safe is the app to use? Is it still considered alpha/beta or safe enough to use it with real sats in a HWW or Specter-DIY multisig setup?*

It is watch-only (private keys are protected by HWW) and compatible with multisig in Electrum, so even if something breaks you always have a fallback option while we fix the bug. So go for it :)

We try to use default descriptors and derivation paths exactly for this reason - to be compatible with other wallets. Would be nice to keep it this way, but at a certain point we will need to diverge - for example when we add miniscript support.

## *What does WIP mean?*

WIP means that we don't try to be very backward-compatible at the moment. At some point we may change wallet storage format for example, and you would need to migrate using some script or create wallets from scratch. In this case, we would provide migration scripts.

## *What's the difference between specter-desktop and specter-DIY?*

Specter-desktop is a watch-only GUI software wallet running on Bitcoin Core using its wallet and full node functionality.
Bitcoin Core tracks addresses, UTXO (unspent transaction outputs) and composes PSBT (partially-signed bitcoin transactions).

Whereas, [Specter-DIY](https://github.com/cryptoadvance/specter-diy) is a do-it-yourself hardware wallet from off the shelf components, that signs and broadcasts transactions using QR codes that forgets your private keys when powered off.

## *I'm not sure I want the Bitcoin-Core wallet functionality to be used, is that mandatory? If so, is it considered secure?*

You don't need private keys in Bitcoin Core, but you need wallets to be enabled `disablewallet=0` in your `bitcoin.conf` file.

## *I make unsigned transactions from my cold storage using a watching-only Electrum wallet. I use public servers instead of my own node because doing it "right" is too complicated for me. Specter may be an ideal alternative if it will connect to my **headless bitcoind node**. Will this be possible?*

Yes, this is the plan - to use a HWW like Coldcard/Trezor with Specter DIY, with a user-friendly multisig Specter desktop app, which is connected to your own node for better privacy.

## *What is the practical difference of using PSBT (partially signed bitcoin transaction) with multisig vs. just signing the raw multisig transaction normally?*

It gives you the ability to store the transaction temporarily before it is signed.

## USAGE

## *How do I run the app?*

After following [these steps](https://github.com/cryptoadvance/specter-desktop#how-to-run) 
You should be able to view it in a browser at: 127.0.0.1:25441/
If not, see [Troubleshoot](https://github.com/cryptoadvance/specter-desktop/new/master/docs#troubleshoot)


## *What do I need to do in order to create a multisig wallet?*

First you need to “add devices” that store keys for the wallet. After creating the devices, you have to create the type of wallet you want (2-of-2, 3-of-5, etc.) and select the corresponding devices/keys - you need at least two devices setup in order to create a multisig wallet.

## *Can I use Bluewallet with Specter DIY?*

Yes you can use BlueWallet in watch-only mode and sign with Specter DIY. See it in action [here](https://twitter.com/StepanSnigirev/status/1209426608949465088)

## *Which HWW's are supported?*

Any HWW with HWI, including USB HWW's (Coldcard, Trezor, Ledger, KeepKey, BitBox, etc.)

## *Can this also work with external nodes like Casa, MyNode, and Raspilitz?* 

Absolutely, as well as any other DIY bitcoin full, or pruned, node!

Currently Raspiblitz (https://github.com/rootzoll/raspiblitz) has explicit support and you can automatically install it as bonus-software. Unfortunately the documentation is not that good yet but the menu when setting it up is quite self-explanatory. 

## *Can I use Tor?*

Yes there is a way to access specter-desktop over Tor from outside, here is the [doc](https://github.com/cryptoadvance/specter-desktop/blob/master/docs/tor.md)

With that being said, beware that it's not practical yet to sign transactions via Tor:

 - Specter-DIY needs the camera which is not available in the Tor-browser (yet)
 - You could use HWI-wallets, but you would need to plug the wallet into the machine where specter-desktop is running on, but this is usually not the use-case you're looking for when using Tor.

## *How to set the URL for the block explorer?*

This feature is optional and not needed for the wallet to function. It's only used for convenience in order to generate URLs for addresses.
Technically, you can use any block explorer but that's not what you want to do, unless you want to try out the feature.
Simply fill in https://blockstream.info/ to use that block explorer, but you will leak privacy doing that.

## BACKING UP FUNDS 

## *If something happens to the `~/.specter` folder, is it still possible to **restore** acccess to multisigs created there (assuming there is no backup of the `~/.specter` folder)?* 

Yes, it's a standard multisig. So you can recreate it as soon as you have **master public keys of ALL the devices** - either with Specter, or Electrum.

If your `~/.specter` folder is gone and only one of your devices is lost without a backup, then all your funds are **LOST**, even if you have a 1/4-multisig-wallet.

When using Specter and importing an old wallet you would need to rescan blockchain in the wallet settings page.

## SPECTER-DIY

## *What does the Specter-DIY consist of?*

It consists of:

 - STM32F469 discovery board
 - QR Code scanner from Waveshare
 - Power Bank (small)
 - miniUSB and microUSB cable
 - Prototype Shield
 - A few pin connectors 

[Shopping list link](https://github.com/cryptoadvance/specter-diy/blob/master/docs/shopping.md) + [assembly link](https://github.com/cryptoadvance/specter-diy/blob/master/docs/assembly.md)
Waveshare QR scanner is recommended as it has a good quality/price ratio.

## *Is specter-DIY safe to use?*

Do not use it on mainnet yet unless it's only being used as one of the signers in multisig setup! But feel free to experiment with it on testnet, regtest or signet.

## *I'm wondering what if someone takes the device? How does Specter-DIY approach this scenario?*

It supports passphrases as an additional security layer, but currently it has two modes of operation - agnostic when your secrets are not stored on the device and you need to enter recovery phrase every time you use the device, and reckless when it is stored on flash and can be extracted. 

We are working on smartcard support so you could store your keys on removable secure element in a credit card form factor, as well as an option to encrypt secrets with a key stored on the SD card. See this recently opened [issue](https://github.com/cryptoadvance/specter-diy/issues/64) thanks to @Thomas1378 in the Telegram chat!

## *Currently there is a `specter_hwi.py` file, which implements the HWIClient for Specter-DIY. Is there any reason you didn't add that directly to HWI?*

Putting it into HWI means: "this is a hardware wallet people should consider using for real". Currently, we would strongly advice NOT to use USB with specter-DIY, but to use QR codes instead.

We will make a PR to HWI when we think it's safe enough. In particular when we will have a secure bootloader that verifies signatures of the firmware, and USB communication is more reliable. 

## *Do you have a physical security design?*

No security at the moment, but it also doesn't store the private key. Working on integration of secure element similar to the ColdCard's (mikroe secure click). At the moment it's more like a toy.

## *Is there a simulator I can try the Specter-DIY with?*

Yes. Specter-DIY in simulator-mode simulates QR code scanner over TCP, see [here](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/4_miniwallet/main.py)

## *Is there a goal to get Specter-DIY loading firmware updates from the SD card?*

At the moment we don't have a proper bootloader and secure element integration yet, but we're moving in that direction! 
I think SD card is a good choice, also QR codes might be possible, but we need to experiment with them a bit.

## *Can specter-DIY register cosigner xpubs like coldcard? I know you wipe private keys on shutdown, but do you save stuff like that?*

Yes, we keep wallet descriptors and other public info.

## *Once you add the javacard (secure element) you'll save the private keys, too?*

With the secure element you will have three options:

 - agnostic mode, forgets key after shutdown
 - store key on the smartcard but do all crypto on application MCU
 - store key and do crypto on the secure element

Last seems to be the most secure, but then you trust proprietary crypto imementation. Second option saves private key on the secure element under pin protection, but also encrypted, so secure element never knows the private key.

## SPECTER-DEVKIT

## *Can I buy the Specter-devkit pre-built?*

Not yet. There are still a few things to implement before we can say it's secure - bootloader and integration with a secure element. We also need to fix a few things with the housing. So for now, it's DIY only. 
With that being said, we are working on a kit (extension board) that includes a QR scanner, battery, charging circuit and a smartcard (secure element) slot. Together with a 3D printed case it is really just plug and play! 
No supply-chain risks as you buy the board and a smartcard from normal electronics stores. We will start selling ready to use wallets when we consider it secure enough and when we remove (WIP) from the repo description. Devkits will be available earlier than that.

## TROUBLESHOOT

## *How to upgrade?*

Use this command: `pip3 install cryptoadvance.specter --upgrade`

To check (before and/or afterwards) your installed version, you can use: `pip3 show cryptoadvance.specter`

## *How can I access the web interface if it's hosted on a headless computer?* 

You can either set --host 0.0.0.0 `python -m cryptoadvance.specter server --host 0.0.0.0` or configure nginx to forward connections from specific port to specter.
 
Alternatively, you can also define --port 80 if you want to have it on default http port of the computer.

One drawback though is that with http and **external access** you will not get camera scanning functionality. It is an issue if you are using specter-DIY as it's necessary to scan QR codes with signed transactions. To fix that you will need a self-signed certificate, we have a document on that [here](https://github.com/cryptoadvance/specter-desktop/blob/master/docs/self-signed-certificates.md)

## *Keep getting: No matching distribution found for cryptoadvance.specter

Try `pip3 install cryptoadvance.specter`

Specter only works with python3, so use pip3 to install it
`brew install python3`

## *Even after upgrading to python3 it's still looking at 2.7 version. I uninstalled 2.7, so not sure where to go next?*

Run it with the command `python3 -m cryptoadvance.specter server` - then it will use python3

## *How to delete a wallet using a remote full node?*

You can't delete the wallet if you are using remote Bitcoin Core node - there is no RPC call to do it remotely. So, deleting wallet works only on the same computer. 
You can also just delete the wallet manually. It's a folder in `~/.bitcoin` directory and in `~/.specter` as well.

## DIY TROUBLESHOOT

## *Does anyone have any tips on mounting the power bank and QR code scanner to the STM32 board in a somewhat ergonomic manner?*

Use the smallest powerbank possible.

## HWW TROUBLESHOOT

Got stuck for a second because I wasn't safely removing my SD card reader, so the files were 0 bytes.

## *With achow's HWI tool, input and output PSBT are the same. And with Electrum 4, I get a rawtransaction, not a base64 PSBT.*

I solved my issue, it turns out my PSBT needed bip32 hints (whatever that means) included. I can now open lightning channels straight from hardware wallet!

## TECHNICAL QUESTIONS (not dev related)

## *Does specter-desktop require `txindex=1` to be set in your `bitcoin.conf`?*

No, but you need to enable wallets! `disablewallet=0`

## FUTURE FEATURES

## *Will Specter-Desktop ever be a full Hot-Wallet?*

Right now it’s only with external wallets, but there is an open issue for hot wallet.

We have plans to add new device type "this computer", see this [issue](https://github.com/cryptoadvance/specter-desktop/issues/58)

At the moment it is more like a coordinator app. For signing we have [specter-diy](https://github.com/cryptoadvance/specter-diy)

*Comment: Still open for discussion - details are being discussed!*

## *How are you guys planning to do airgapped firmware updates via QR codes?*

We haven't tested it yet. We will work on the bootloader soon and try different update mechanisms. QR codes is one of them. Also considering SD card - might be easier as firmware is 1Mb, so it would require 1000 QR codes.

## *Will this device be Shamir Secret Shares compatible?*

Yes it will be, and especially effective in "forget after turn off" mode. Then one could use it to split a secret for wallets that don't support it.

## *Will there be coinjoin support in the future?*

When coinjoin servers and hardware wallets support proof of ownership: https://github.com/satoshilabs/slips/blob/slips-19-20-coinjoin-proofs/slip-0019.md

## VIDEOS

## **1** [Getting started with Specter-DIY and Specter-Desktop](https://twitter.com/CryptoAdvance/status/1235151027348926464)

How to flash and set up an airgapped hardware wallet that uses QR codes to communicate with the host.

In the video: 

 - Flashing the firmware
 - Generating a new key 
 - Importing keys to Specter-Desktop software 
 - Using single-key wallets 
 - Creating a multisignature wallet and importing it to the device 
 - Signing multisig transactions 

## **2** [Assembling Specter-DIY](https://www.youtube.com/watch?v=1H7FqG_FmCw)

Specter-DIY hardware wallet: 

 - off-the-shelf components
 - costs 100$ - assemble in 5 minutes 
 - no soldering 
 - forgets your private key when powered off 

## **3** [Specter-DIY air-gapped open source bitcoin hardware wallet overview](https://twitter.com/KeithMukai/status/1189565099259944961)

## **4** [Build your own bitcoin hardware-wallet YT series](https://www.youtube.com/playlist?list=PLn2qRQUAAg0z_-R0swVuSsNS9bzRu6oP5&app=desktop)

## *What is the difference between that project (DIYbitcoinhardware) & Specter? Is DIYbitcoinhardware sort of a prerequisite for Specter?*

Specter is built on top of that micropython build. DIYbitcoinhardware is focusing more on the toolbox without actual application logic, Specter implements logic and GUI on top of it. 

Yes, that's why the video was recorded - to give some introduction about the tools we use, and hardware wallets logic in general.
