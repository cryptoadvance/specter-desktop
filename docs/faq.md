# Frequently Asked Questions

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [ABOUT THE PROJECT](#about-the-project)
  - [*Why the name Specter?*](#why-the-name-specter)
- [GENERAL QUESTIONS](#general-questions)
  - [*How safe is the app to use? Is it still considered alpha/beta or safe enough to use it with real sats in a HWW or Specter-DIY multisig setup?*](#how-safe-is-the-app-to-use-is-it-still-considered-alphabeta-or-safe-enough-to-use-it-with-real-sats-in-a-hww-or-specter-diy-multisig-setup)
  - [*What does WIP mean?*](#what-does-wip-mean)
  - [*What's the difference between Specter-desktop and Specter-DIY?*](#whats-the-difference-between-specter-desktop-and-specter-diy)
  - [*Is a full node necessary for using Specter-desktop?*](#is-a-full-node-necessary-for-using-specter-desktop)
  - [*Can I use pruned mode?*](#can-i-use-pruned-mode)
  - [*I get this message: "This is a development server. Do not use it in a production deployment.". Should i worry?](#i-get-this-message-this-is-a-development-server-do-not-use-it-in-a-production-deployment-should-i-worry)
  - [*I'm not sure I want the Bitcoin-Core wallet functionality to be used, is that mandatory? If so, is it considered secure?*](#im-not-sure-i-want-the-bitcoin-core-wallet-functionality-to-be-used-is-that-mandatory-if-so-is-it-considered-secure)
  - [How many addresses does an HD wallet have, and are they all the same?](#how-many-addresses-does-an-hd-wallet-have-and-are-they-all-the-same)
  - [*I make unsigned transactions from my cold storage using a watching-only Electrum wallet. I use public servers instead of my own node because doing it "right" is too complicated for me. Specter may be an ideal alternative if it will connect to my **headless bitcoind node**. Will this be possible?*](#i-make-unsigned-transactions-from-my-cold-storage-using-a-watching-only-electrum-wallet-i-use-public-servers-instead-of-my-own-node-because-doing-it-right-is-too-complicated-for-me-specter-may-be-an-ideal-alternative-if-it-will-connect-to-my-headless-bitcoind-node-will-this-be-possible)
  - [*What is the practical difference of using PSBT (partially signed bitcoin transaction) with multisig vs. just signing the raw multisig transaction normally?*](#what-is-the-practical-difference-of-using-psbt-partially-signed-bitcoin-transaction-with-multisig-vs-just-signing-the-raw-multisig-transaction-normally)
  - [*If the Bitcoin Core instance we are connecting to already has a wallet, is it possible to load it via the UI if we know the name, and could we import a .dat file?*](#if-the-bitcoin-core-instance-we-are-connecting-to-already-has-a-wallet-is-it-possible-to-load-it-via-the-ui-if-we-know-the-name-and-could-we-import-a-dat-file)
  - [*How are Bitcoin Core mnemonic seeds created? With Core there's only the option to backup the wallet.dat file, so how does specter-desktop transform the wallet.dat file into a mnemonic seed?*](#how-are-bitcoin-core-mnemonic-seeds-created-with-core-theres-only-the-option-to-backup-the-walletdat-file-so-how-does-specter-desktop-transform-the-walletdat-file-into-a-mnemonic-seed)
  - [*Why when I export a multisig wallet from specter-desktop (settings > export > copy wallet data) created from devices with only segwit ZPUBs, do I get a data structure with expected segwit derivation paths but XPUBs instead?*](#why-when-i-export-a-multisig-wallet-from-specter-desktop-settings--export--copy-wallet-data-created-from-devices-with-only-segwit-zpubs-do-i-get-a-data-structure-with-expected-segwit-derivation-paths-but-xpubs-instead)
  - [*Does Specter have coin control?*](#does-specter-have-coin-control)
- [USAGE](#usage)
  - [*How do I run the app?*](#how-do-i-run-the-app)
  - [*How do i verify the signatures of the binaries?*](#how-do-i-verify-the-signatures-of-the-binaries)
  - [*Where do i find the logs?*](#where-do-i-find-the-logs)
  - [*What types of ways can I run specter-desktop?*](#what-types-of-ways-can-i-run-specter-desktop)
  - [Devices? Wallets? What is the difference?](#devices-wallets-what-is-the-difference)
  - [*What do I need to do in order to create a multisig wallet?*](#what-do-i-need-to-do-in-order-to-create-a-multisig-wallet)
  - [*Is my understanding correct that specter-desktop does not hold any keys and you need to create a multisig wallet in order to sign transactions and send funds?*](#is-my-understanding-correct-that-specter-desktop-does-not-hold-any-keys-and-you-need-to-create-a-multisig-wallet-in-order-to-sign-transactions-and-send-funds)
  - [*How would one sign with Electrum? Do I need to create multisig wallet in Electrum first or can I create it with specter-desktop?*](#how-would-one-sign-with-electrum-do-i-need-to-create-multisig-wallet-in-electrum-first-or-can-i-create-it-with-specter-desktop)
  - [*Can I use Ledger and ColdCard multisig while CC remains air-gapped?*](#can-i-use-ledger-and-coldcard-multisig-while-cc-remains-air-gapped)
  - [*Can I use Bluewallet with Specter DIY?*](#can-i-use-bluewallet-with-specter-diy)
  - [*Which hardware wallets are supported?*](#which-hardware-wallets-are-supported)
  - [*Can this also work with external nodes like Casa, MyNode, and Raspilitz?*](#can-this-also-work-with-external-nodes-like-casa-mynode-and-raspilitz)
  - [*Can I use Tor?*](#can-i-use-tor)
  - [I forgot my password, how can I reset it?](#i-forgot-my-password-how-can-i-reset-it)
- [BACKING UP FUNDS](#backing-up-funds)
  - [*If something happens to the `~/.specter` folder, is it still possible to **restore** access to multisigs created there (assuming there is no backup of the `~/.specter` folder)?*](#if-something-happens-to-the-specter-folder-is-it-still-possible-to-restore-access-to-multisigs-created-there-assuming-there-is-no-backup-of-the-specter-folder)
  - [*To recover a multisig that was built on specter (eg: 2 of 3 with ColdCard), is having the seeds of all 3 signing wallets sufficient or do we need to backup more info?*](#to-recover-a-multisig-that-was-built-on-specter-eg-2-of-3-with-coldcard-is-having-the-seeds-of-all-3-signing-wallets-sufficient-or-do-we-need-to-backup-more-info)
- [SPECTER-DIY](#specter-diy)
  - [*What does the Specter-DIY consist of?*](#what-does-the-specter-diy-consist-of)
  - [*Is specter-DIY safe to use?*](#is-specter-diy-safe-to-use)
  - [*I'm wondering what if someone takes the device? How does Specter-DIY approach this scenario?*](#im-wondering-what-if-someone-takes-the-device-how-does-specter-diy-approach-this-scenario)
  - [*Currently there is a `specter_hwi.py` file, which implements the HWIClient for Specter-DIY. Is there any reason you didn't add that directly to HWI?*](#currently-there-is-a-specter_hwipy-file-which-implements-the-hwiclient-for-specter-diy-is-there-any-reason-you-didnt-add-that-directly-to-hwi)
  - [*Do you have a physical security design?*](#do-you-have-a-physical-security-design)
  - [*Is there a simulator I can try the Specter-DIY with?*](#is-there-a-simulator-i-can-try-the-specter-diy-with)
  - [*Is there a goal to get Specter-DIY loading firmware updates from the SD card?*](#is-there-a-goal-to-get-specter-diy-loading-firmware-updates-from-the-sd-card)
  - [*Can Specter-DIY register cosigner xpubs like ColdCard? I know you wipe private keys on shutdown, but do you save stuff like that?*](#can-specter-diy-register-cosigner-xpubs-like-coldcard-i-know-you-wipe-private-keys-on-shutdown-but-do-you-save-stuff-like-that)
  - [*Once you add the javacard (secure element) you'll save the private keys, too?*](#once-you-add-the-javacard-secure-element-youll-save-the-private-keys-too)
- [TROUBLESHOOT](#troubleshoot)
  - [The AppImage is not starting on Debian 10](#the-appimage-is-not-starting-on-debian-10)
  - [I have issues connecting my Hardware-Wallet via USB?!](#i-have-issues-connecting-my-hardware-wallet-via-usb)
  - [*How to upgrade Specter-desktop?*](#how-to-upgrade-specter-desktop)
  - [Laptop/Desktop](#laptopdesktop)
  - [Raspiblitz](#raspiblitz)
  - [umbrel](#umbrel)
  - [*How can I access the web interface if it's hosted on a headless computer?*](#how-can-i-access-the-web-interface-if-its-hosted-on-a-headless-computer)
  - [*How can I access the Specter Desktop web interface with my phone?*](#how-can-i-access-the-specter-desktop-web-interface-with-my-phone)
  - [*Keep getting: No matching distribution found for cryptoadvance.specter*](#keep-getting-no-matching-distribution-found-for-cryptoadvancespecter)
  - [*Even after upgrading to python3 it's still looking at 2.7 version. I uninstalled 2.7, so not sure where to go next?*](#even-after-upgrading-to-python3-its-still-looking-at-27-version-i-uninstalled-27-so-not-sure-where-to-go-next)
  - [*I created an existing wallets but even after rescanning, specter couldn't find any (or not enough) funds?*](#i-created-an-existing-wallets-but-even-after-rescanning-specter-couldnt-find-any-or-not-enough-funds)
  - [*How to delete a wallet using a remote full node?*](#how-to-delete-a-wallet-using-a-remote-full-node)
  - [*Trying to connect specter-desktop to my remote node on my LAN few times but no success. `bitcoin.conf` has the `server=1` option, should there be something else since I get this error `Process finished with code -1Error message: Failed to connect` message?*](#trying-to-connect-specter-desktop-to-my-remote-node-on-my-lan-few-times-but-no-success-bitcoinconf-has-the-server1-option-should-there-be-something-else-since-i-get-this-error-process-finished-with-code--1error-message-failed-to-connect-message)
  - [Backup files not showing when trying to load backups](#backup-files-not-showing-when-trying-to-load-backups)
- [DIY TROUBLESHOOT](#diy-troubleshoot)
  - [*Does anyone have any tips on mounting the power bank and QR code scanner to the STM32 board in a somewhat ergonomic manner?*](#does-anyone-have-any-tips-on-mounting-the-power-bank-and-qr-code-scanner-to-the-stm32-board-in-a-somewhat-ergonomic-manner)
- [HWW TROUBLESHOOT](#hww-troubleshoot)
  - [*With achow's HWI tool, input and output PSBT are the same. And with Electrum 4, I get a rawtransaction, not a base64 PSBT.*](#with-achows-hwi-tool-input-and-output-psbt-are-the-same-and-with-electrum-4-i-get-a-rawtransaction-not-a-base64-psbt)
- [TECHNICAL QUESTIONS (not dev related)](#technical-questions-not-dev-related)
  - [*Does specter-desktop require `txindex=1` to be set in your `bitcoin.conf`?*](#does-specter-desktop-require-txindex1-to-be-set-in-your-bitcoinconf)
  - [*Does specter-desktop specify an RPC wallet in the `bitcoin.conf` or append wallet name to node url?*](#does-specter-desktop-specify-an-rpc-wallet-in-the-bitcoinconf-or-append-wallet-name-to-node-url)
- [FUTURE FEATURES](#future-features)
  - [*How are you guys planning to do air-gapped firmware updates via QR codes?*](#how-are-you-guys-planning-to-do-air-gapped-firmware-updates-via-qr-codes)
  - [*Will this device be Shamir Secret Shares compatible?*](#will-this-device-be-shamir-secret-shares-compatible)
  - [*Will there be CoinJoin support in the future?*](#will-there-be-coinjoin-support-in-the-future)
- [VIDEOS](#videos)
  - [**1** Getting started with Specter-DIY and Specter-Desktop](#1-getting-started-with-specter-diy-and-specter-desktop)
  - [**2** Assembling Specter-DIY](#2-assembling-specter-diy)
  - [**3** Specter-DIY air-gapped open source bitcoin hardware wallet overview](#3-specter-diy-air-gapped-open-source-bitcoin-hardware-wallet-overview)
  - [**4** Build your own bitcoin hardware-wallet YT series](#4-build-your-own-bitcoin-hardware-wallet-yt-series)
  - [*What is the difference between that project (DIYbitcoinhardware) & Specter? Is DIYbitcoinhardware sort of a prerequisite for Specter?*](#what-is-the-difference-between-that-project-diybitcoinhardware--specter-is-diybitcoinhardware-sort-of-a-prerequisite-for-specter)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## ABOUT THE PROJECT

The goal of this project is to make a convenient and user-friendly GUI around Bitcoin Core with a focus on multisignature setup with air-gapped (offline) hardware wallets. 

We first wanted to make a new hardware wallet (HWW), but after we understood that everything can be hacked, we decided to build a user-friendly multisig Desktop App and nice DIY Hardware Wallet.

**Why is that good for Bitcoin?**

 - User: Better Security with multisig setup 
 - User: Better Privacy with own node 
 - HWW Makers: More HW wallets sold 
 - Node Makers: More Nodes sold 
 - Network: More nodes running 

We can actually incentivize the Bitcoin community to run their own node with this user-friendly multisig & node setup! 

### *Why the name Specter?*

    "A specter is haunting the modern world, the specter of crypto anarchy."
    The Crypto Anarchist Manifesto - Timothy C. May - Sun, 22 Nov 92 12:11:24 PST
    
Specter is that little ghost helping the sovereign cypherpunk to protect his property rights.
We are aware of the vulnerability (Spectre) and know there is an infinite game against vulnerabilities.
https://en.wikipedia.org/wiki/Spectre_(security_vulnerability)
In Bitcoin Cold storage we can use multisig setups and different hardware wallets to mitigate these risks, while protecting our privacy by verifying transactions on our own node.

## GENERAL QUESTIONS

### *How safe is the app to use? Is it still considered alpha/beta or safe enough to use it with real sats in a HWW or Specter-DIY multisig setup?*

It is watch-only (private keys are protected by HWW) and compatible with multisig in Electrum, so even if something breaks you always have a fallback option while we fix the bug. So go for it :)

We try to use default descriptors and derivation paths exactly for this reason - to be compatible with other wallets. Would be nice to keep it this way, but at a certain point we will need to diverge - for example when we add miniscript support.

### *What does WIP mean?*

WIP means that we don't try to be very backward-compatible at the moment. At some point we may change wallet storage format for example, and you would need to migrate using some script or create wallets from scratch. In this case, we would provide migration scripts.

### *What's the difference between Specter-desktop and Specter-DIY?* 

Specter-desktop is a watch-only GUI software wallet running on Bitcoin Core using its wallet and full node functionality.
Bitcoin Core tracks addresses, UTXO (unspent transaction outputs) and composes PSBT (partially-signed bitcoin transactions).

Whereas, [Specter-DIY](https://github.com/cryptoadvance/specter-diy) is a do-it-yourself hardware wallet from off the shelf components, that signs and broadcasts transactions using QR codes that forgets your private keys when powered off.

### *Is a full node necessary for using Specter-desktop?*

Yes, a Bitcoin node is needed to provide all relevant data without relying on 3rd parties, and also for its watch-only wallet capabilities. However, Specter allows you to easily setup a (pruned-) node easily within Specter. If you can, a full-node is recommended but will take a lot longer to synchronize.

### *Can I use pruned mode?*

Yes, but if you have many older addresses you will need to re-download the blockchain in order to see your balance and transaction history, which will take some time.
Since v0.8.0 there is a workaround as you can download history from an external blockexplorer which has privacy implications. Make sure to read the tooltip-hints when using that feature and also consider this question in the  [troubleshooting-section](#i-created-an-existing-wallets-but-even-after-rescanning-specter-couldnt-find-any-funds)..

### *I get this message: "This is a development server. Do not use it in a production deployment.". Should i worry?

No you don't have to worry unless you plan to run specter as a public service on the internet with a growing number of people using it. That was traditionally the use-case for web-apps: Run in the open public internet getting accessed by MANY people. However, that's not how specter is meant to be used. If people get performance issues, it's most likely not because the user-base is growing on their specter but because their Raspberry Pi is too weak for that one user who is doing all sorts of other stuff on that Pi on top.

### *I'm not sure I want the Bitcoin-Core wallet functionality to be used, is that mandatory? If so, is it considered secure?*

You don't need private keys in Bitcoin Core, but you need wallets to be enabled `disablewallet=0` in your `bitcoin.conf` file. And if you don't want that, make also sure you're not using the Hotwallet-Feature.

### How many addresses does an HD wallet have, and are they all the same?

By default the gap limit is 20, but you can go to the wallet settings and import as many addresses as you want. If you know the wallet is old you may want to try importing many addresses (~1000), and then rescanning.

The order is the same, and the addresses are also the same as the address derivation process is deterministic for a wallet. Address index is a derivation index of the wallet, so the index and the address itself are connected.

### *I make unsigned transactions from my cold storage using a watching-only Electrum wallet. I use public servers instead of my own node because doing it "right" is too complicated for me. Specter may be an ideal alternative if it will connect to my **headless bitcoind node**. Will this be possible?*

Yes, this is the plan - to use a HWW like ColdCard/Trezor with Specter DIY, with a user-friendly multisig Specter desktop app, which is connected to your own node for better privacy.

### *What is the practical difference of using PSBT (partially signed bitcoin transaction) with multisig vs. just signing the raw multisig transaction normally?*

It gives you the ability to store the transaction temporarily before it is signed.

### *If the Bitcoin Core instance we are connecting to already has a wallet, is it possible to load it via the UI if we know the name, and could we import a .dat file?*

Currently, you can create a hot wallet from within the specter-desktop UI, but at the moment it's not possible to extract XPUBs from the existing Core wallet, and without XPUBs change verification will break in all hardware wallets. Change address verification in multisig on a hardware wallet requires ability to check that change and inputs were derived from the same XPUBs. Without XPUBs all hardware wallets will show two outputs so you never know if the change output is actually change or not.

With that being said, wallets created by Bitcoin Core always use hardened derivations, so they don't have useful XPUBs - this breaks multisig address verification on hardware wallets and thus can't verify change addresses. Therefore specter-desktop is creating a Bitcoin Core hot wallet differently - it generates a BIP39 recovery phrase, loads XPRVs to Core and XPUBs to specter-desktop. Then it can be used as a part of multisig setup as usual.

The seed is generated by specter-desktop and then it's imported in a Bitcoin Core wallet, but instead of watch-only it's an XPRV imported using descriptors. More info on descriptors can be found [here](https://github.com/bitcoin/bitcoin/blob/master/doc/descriptors.md).

### *How are Bitcoin Core mnemonic seeds created? With Core there's only the option to backup the wallet.dat file, so how does specter-desktop transform the wallet.dat file into a mnemonic seed?*

Specter-desktop generates a random mnemonic using Trezor's mnemonic package, then converts it to XPRVs and imports these keys to Bitcoin Core. This feature is very experimental at the moment and shouldn't be used for large amounts.

### *Why when I export a multisig wallet from specter-desktop (settings > export > copy wallet data) created from devices with only segwit ZPUBs, do I get a data structure with expected segwit derivation paths but XPUBs instead?*

XPUB is a canonical representation that is supported by Bitcoin Core, whereas ZPUB is an invention of SatoshiLabs that got adopted by the industry, but not by Bitcoin Core. In wallet export file we export Bitcoin Core's descriptor, so it contains master keys in the format that Bitcoin Core understands. More info on descriptors can be found [here](https://github.com/bitcoin/bitcoin/blob/master/doc/descriptors.md).

### *Does Specter have coin control?*

Yes, Specter supports coin control. Go to "Send". Open the "Advanced" features - and down at the right you have "Select coins manually" bottom.


## USAGE

### *How do I run the app?*

After following [these steps](https://github.com/cryptoadvance/specter-desktop#how-to-run) 
You should be able to view it in a browser at: 127.0.0.1:25441/
If not, see [Troubleshoot](https://github.com/cryptoadvance/specter-desktop/new/master/docs#troubleshoot)

### *How do i verify the signatures of the binaries?*

There is a great tutorial [here](https://bitcoiner.guide/verifysoftware/) explaining it for specter-desktop. A more generic video from kryptokids is [here](https://www.youtube.com/watch?v=S257nUqs13A).

### *Where do i find the logs?*

If you use a binary-installation (a platform specific download-package) there is a log-file called `specterApp.log` in the SPECTER_DATA_FOLDER in your user-directory. So for different platforms, default places are: 
* Windows: `C:\Users\YourUser\.specter\specterApp.log`
* Linux: `/home/yourUser/.specter/specterApp.log`
For pip installations, you need to look into the file `specter.log` in the same directory.
If you still have trouble finding that file on your harddrive, have a look at the tooltip in the settings/general/Loglevel item.

### *What types of ways can I run specter-desktop?*

There are many ways how to run Specter:
- Specter on local computer, node on remote
- Specter on a remote node, web interface in local network or over Tor (but hardware wallets need to be connected to the node where Specter is running)
- Specter on a remote node, another Specter on your computer in "hwibridge" mode that gives access to your hardware wallets from the remote node (configurable whitelist)

Also you can run it via a platform-specific binary, pip-installation or via a Docker-container. It depends on your needs, and can be customized accordingly.

Specter-desktop makes many requests to Bitcoin Core RPC, so it works better from the same machine where Core is running, but remote is also possible. With that being said, by default Bitcoin Core RPC is connecting over HTTP, so everything including your RPC login and password are flying around as plaintext. You can use HTTPS and a [self-signed certificate](https://github.com/cryptoadvance/specter-desktop/blob/master/docs/self-signed-certificates.md) to fix that.

If you use hardware wallets and they are usb-connected to specter-desktop then you need to use the hwibridge in the remote cases. However if your HWW is air-gapped (ColdCard, specter-diy, cobo) - then you can use remote web interface.

### Devices? Wallets? What is the difference?

The logic is that devices store keys, and you can combine these keys in different wallets like multisig or singlesig. So the same device can be used for a nested segwit wallet, native segwit, and many multisig wallets.
The only requirement is that all cosigners in multisig wallets should be different devices.
For some devices it makes sense to import keys, for example for another passphrase. However it's also possible (and recommended) to create a new device if you want to use a different passphrase for the same device.

### *What do I need to do in order to create a multisig wallet?*

XPUBs are needed (from HWW's, laptop with Electrum desktop wallet, Specter-DIY, etc.) in order to create a multisig setup, but don't worry it's in watch-only mode and it's your own full node! First you need to “add devices” that store keys for the wallet. After creating the devices, you have to create the type of wallet you want (2-of-2, 3-of-5, etc.) and select the corresponding devices/keys - you need at least two devices setup in order to create a multisig wallet.

### *Is my understanding correct that specter-desktop does not hold any keys and you need to create a multisig wallet in order to sign transactions and send funds?*

As of late, you can also use a hot wallet as a signer with specter-desktop, but this is not recommended as a default setup. You can however use devices like Electrum wallet or FullyNoded for example (Electrum or Bitcoin Core can be air-gapped). This [video](https://youtu.be/4YXklLh2srA) is quite useful for using Electrum, and this [guide](https://github.com/Fonta1n3/FullyNoded/blob/master/Docs/Connect-node.md#importing-a-wallet-from-specter) is useful for connecting with FullyNoded.

### *How would one sign with Electrum? Do I need to create multisig wallet in Electrum first or can I create it with specter-desktop?*

You need to create it in both wallets. When you start creating multisig wallet in Electrum it will give you the bech32 extended public key (ZPUB) where you can then add it to specter-desktop as well as other ZPUBS from other devices, and then add them to Electrum. After that you can start using Electrum as a signer.
Electrum support got much better lately. We now have a dedicated electrum device with a specific explanation. If you're running into trouble, this [video](https://www.youtube.com/watch?v=4YXklLh2srA) might still help a lot and gives more details.

### *Can I use Ledger and ColdCard multisig while CC remains air-gapped?*

Yes you can use the ColdCard with its SD card without connecting it to the computer via USB. You just need to import the ColdCard public keys with SD card. Just after creating the multisig wallet, you should go to the wallet page, click on the Settings tab, then scroll down to the Export and click on the export to ColdCard option. It will download a file you can import with the SD card to ColdCard and show you a notification with the instructions on how to do this. This will allow the ColdCard to be “aware” of the multisig and sign transactions for it.

### *Can I use Bluewallet with Specter DIY?*

Yes you can use BlueWallet in watch-only mode and sign with Specter DIY. See it in action [here](https://twitter.com/StepanSnigirev/status/1209426608949465088)

### *Which hardware wallets are supported?*

All major once! Checkout the list when you add a new device.

### *Can this also work with external nodes like Casa, MyNode, and Raspilitz?*

Absolutely, as well as any other DIY bitcoin full, or pruned, node!

Currently Raspiblitz (https://github.com/rootzoll/raspiblitz), has explicit support and you can automatically install it as bonus-software. Also [umbrel](https://getumbrel.com/) has it in the app-store. Mynode has it on Mynode [premium](https://mynodebtc.com/products/premium). Start9 is currently preparing support. There are differences mainly on update-policy and update-freuency.

### *Can I use Tor?*

Yes there is a way to access specter-desktop over Tor from outside, here is the [doc](https://github.com/cryptoadvance/specter-desktop/blob/master/docs/tor.md).

Since version v1.3.0, there will also be the possibility to activate a tor-installation from within Specter-Desktop.

With that being said, beware that it's not practical yet to sign transactions via Tor:

 - Specter-DIY needs the camera which is not available in the Tor-browser (yet)
 - You could use HWI-wallets, but you would need to plug the wallet into the machine where specter-desktop is running on, but this is usually not the use-case you're looking for when using Tor.

 Progress on Tor Support for QR-code scanning is tracked in this [issue](https://github.com/cryptoadvance/specter-desktop/issues/536)


### I forgot my password, how can I reset it?

Check the .specter-folder in your home folder (or on your mynode/raspiblitz/...). There is a file called `config.json` in there which has a line like this:
```
"auth": {
    "method": "somethingInHere",
    ...
},
```
Depending on "what's written in `somethingInHere`:
* If it's `rpcpasswordaspin`, you can lookup the password in your `bitcoin.conf`-file in a line like `rpcpassword=YourPasswordHere`
* If it's `usernamepassword`, you won't be able to recover the password but you can deactivate it by setting it to `none`
* If it's `none` (or you just set it to `none`) you can login without any password. So hurry up with setting it again within specter.

## BACKING UP FUNDS 

### *If something happens to the `~/.specter` folder, is it still possible to **restore** access to multisigs created there (assuming there is no backup of the `~/.specter` folder)?* 

Yes, it's a standard multisig. So you can recreate it as soon as you have **master public keys of ALL the devices** - either with Specter, or Electrum.

If your `~/.specter` folder is gone and only one of your devices is lost
 without a backup, then all your funds are **LOST**, even if you have a 1/4-multisig-wallet.

When using Specter and importing an old wallet you would need to re-scan the blockchain in the wallet settings page.

### *To recover a multisig that was built on specter (eg: 2 of 3 with ColdCard), is having the seeds of all 3 signing wallets sufficient or do we need to backup more info?*

Having seeds is enough, but in case you lose one of the seeds it is also **highly recommended** that you also backup your XPUBs. You can go to the wallet settings and export it as json file, this file has all the information needed to find your funds. "Export to wallet" software should give you one json file with all information needed for the recovery of your watch only wallet later on. 

## SPECTER-DIY

### *What does the Specter-DIY consist of?*

It consists of:

 - STM32F469 discovery board
 - QR Code scanner from Waveshare
 - Power Bank (small)
 - miniUSB and microUSB cable
 - Prototype Shield
 - A few pin connectors 

[Shopping list link](https://github.com/cryptoadvance/specter-diy/blob/master/docs/shopping.md) + [assembly link](https://github.com/cryptoadvance/specter-diy/blob/master/docs/assembly.md)
Waveshare QR scanner is recommended as it has a good quality/price ratio.

### *Is specter-DIY safe to use?*

Do not use it on mainnet yet unless it's only being used as one of the signers in multisig setup! But feel free to experiment with it on testnet, regtest or signet.

### *I'm wondering what if someone takes the device? How does Specter-DIY approach this scenario?*

It supports passphrases as an additional security layer, but currently it has two modes of operation - agnostic when your secrets are not stored on the device and you need to enter recovery phrase every time you use the device, and reckless when it is stored on flash and can be extracted. 

We are working on smart card support so you could store your keys on removable secure element in a credit card form factor, as well as an option to encrypt secrets with a key stored on the SD card. See this recently opened [issue](https://github.com/cryptoadvance/specter-diy/issues/64) thanks to @Thomas1378 in the Telegram chat!

### *Currently there is a `specter_hwi.py` file, which implements the HWIClient for Specter-DIY. Is there any reason you didn't add that directly to HWI?*

Putting it into HWI means: "this is a hardware wallet people should consider using for real". Currently, we would strongly advice NOT to use USB with Specter-DIY, but to use QR codes instead.

We will make a pull request to HWI when we think it's safe enough. In particular when we will have a secure bootloader that verifies signatures of the firmware, and USB communication is more reliable. 

### *Do you have a physical security design?*

No security at the moment, but it also doesn't store the private key. Working on integration of secure element similar to the ColdCard's (mikroe secure chip). At the moment it's more like a toy.

### *Is there a simulator I can try the Specter-DIY with?*

Yes. Specter-DIY in simulator-mode simulates QR code scanner over TCP, see [here](https://diybitcoinhardware.com/f469-disco/simulator/?script=https://raw.githubusercontent.com/diybitcoinhardware/f469-disco/master/docs/tutorial/4_miniwallet/main.py)

### *Is there a goal to get Specter-DIY loading firmware updates from the SD card?*

At the moment we don't have a proper bootloader and secure element integration yet, but we're moving in that direction! 
I think SD card is a good choice, also QR codes might be possible, but we need to experiment with them a bit.

### *Can Specter-DIY register cosigner xpubs like ColdCard? I know you wipe private keys on shutdown, but do you save stuff like that?*

Yes, we keep wallet descriptors and other public info.

### *Once you add the javacard (secure element) you'll save the private keys, too?*

With the secure element you will have three options:

 - agnostic mode, forgets key after shutdown
 - store key on the smartcard but do all crypto on application MCU
 - store key and do crypto on the secure element

Last seems to be the most secure, but then you trust proprietary crypto implementation. Second option saves private key on the secure element under pin protection, but also encrypted, so secure element never knows the private key.

## TROUBLESHOOT

### The AppImage is not starting on Debian 10
This is a known issue. See [here](https://github.com/cryptoadvance/specter-desktop/issues/769). A questionable workaround might be to start with `--no-sandbox`. The security-implications are beyond this FAQ. Please check the issues for more information.

### I have issues connecting my Hardware-Wallet via USB?!

* Make sure to not use the Safari-Browser. Chrome is the best option, Firefox should work as well. 
* Make sure that your USB-cable is working. Often enough they are not working anymore. 
* Also, make sure to upgrade to the latest firmware, ledger but also others are known to not work with specific older versions. 
* On Linux, there is also something called [udev-rules](../udev/README.md) which have to be installed.
* Then, there might be confusion about the computer to plug it in. Do you run specter locally or on some remote-computer? Without the hwi-bridge, you need to plug your hardware wallet in the USB-port of the computer you're running specter on. If you want to use your computer and not the remote one, checkout the [HWIBridge](./hwibridge.md)
* Also unplug other maybe exotic USB hardware like game-controllers, printers and basically everything, just for testing purposes.
* If you're using the hwi-bridge, skip it for testing purposes and use specter locally to let it connect to your local 

### *How to upgrade Specter-desktop?*

This depends very much on how you've installed it in the first place. You might have it running on a node-implementation like nodl, RaspiBlitz or MyNode or you have it running on your desktop or laptop. MyNode doesn't support manual upgrade, but let's start with the laptop:

### Laptop/Desktop
If you have downloaded a binary, simply do it again with the new version. If you have a pip-installation (and installed it as described), use this command:
`pip3 install cryptoadvance.specter --upgrade`
To check (before and/or afterwards) your installed version, you can use: `pip3 show cryptoadvance.specter`

### Raspiblitz
You might want to wait until raspiblitz is providing an update. It takes longer but if you're not technically literate, that might be a better option. However, up from Version 1.6.1, Raspiblitz offers an update-possibility in the menu. Prior to that or as a part of troubleshooting-procedure, you can also do something like this:
```
sudo su - specter
. ./.env/bin/activate
pip3 list | grep specter
pip3 install cryptoadvance.specter --upgrade
pip3 list | grep specter
exit
sudo systemctl restart specter
```

### umbrel


### *How can I access the web interface if it's hosted on a headless computer?* 

You can either set --host 0.0.0.0 `python -m cryptoadvance.specter server --host 0.0.0.0` or configure nginx to forward connections from specific port to specter.
 
Alternatively, you can also define --port 80 if you want to have it on default http port of the computer.

One drawback though is that with http and **external access** you will not get camera scanning functionality. It is an issue if you are using specter-DIY as it's necessary to scan QR codes with signed transactions. To fix that you will need a self-signed certificate, we have a document on that [here](https://github.com/cryptoadvance/specter-desktop/blob/master/docs/self-signed-certificates.md)

### *How can I access the Specter Desktop web interface with my phone?*

Similar as above, add `--host 0.0.0.0` when starting the Specter server (to bind the Specter server to the local IP of the machine that you are running Specter on), thus `python -m cryptoadvance.specter server --host 0.0.0.0`. You can then access the Specter server with your phone by typing `http://LOCAL_IP_OF_MACHINE_RUNNING_SPECTER:25441/` in the phone's browser. 

**Note**: Your phone and the machine running Specter have to be connected to the same LAN for this simple approach to work. You might also need to adjust your firewall settings on the machine running Specter. For remote access of your Specter server check the [Tor docs](https://docs.specter.solutions/desktop/tor/).

### *Keep getting: No matching distribution found for cryptoadvance.specter*

Try `pip3 install cryptoadvance.specter`

Specter only works with python3, so use pip3 to install it
`brew install python3`

### *Even after upgrading to python3 it's still looking at 2.7 version. I uninstalled 2.7, so not sure where to go next?*

Run it with the
 command `python3 -m cryptoadvance.specter server` - then it will use python3
 
### *I created an existing wallets but even after rescanning, specter couldn't find any (or not enough) funds?*

Make sure you're using the right type of wallet. Specter is only supporting "Nested Segwit" and "Native SegWit". If you have an older wallet, where addresses are starting with "1" or "3", those funds won't be able to show up in specter. So, make sure you know which type of wallet you want to choose. Also, it's relevant whether you're watching enough addresses. By default only 20 addresses are watched. Maybe your wallet needs more so increase them in the settings-menu of the wallet.

If you're running a pruned node, it's not possible to scan for the entire transaction history without doing a full re-download of the blockchain (IBD). Alternatively, we also support scanning for only the existing wallet balance (UTXO) which is very quick and supports both full and pruned nodes. However, for pruned nodes to support this feature, we must query some external data from an outside source (such as a block explorer, configurable by the user). This does not constitute a security risk, as the validity of the data can be verified against the hash existing on the pruned node itself, but can be a potential privacy risk, although it's possible to get the data over Tor to reduce the potential privacy leak. Yet, we still strongly recommend using a non-pruned-node (if possible) when dealing with older wallets.

Also be aware that if you've use more than one "account" in your old wallet-software, you'd need to create the corresponding key in the device first and create a new wallet based on that account/key. In Specter, one wallet is always tied to exactly one Bitcoin Account (other than e.g. trezor). Bitcoin accounts are actually specified at the device level. By default Specter imports the keys for just your first account. To import keys for additional accounts:

* click on your device to "Add more keys"
* click the "Edit" button at the top right
* click the "Add account" that will have now appeared
* Account 0 is the default that Specter imports on its own. Specify your target account number (accounts start at 0, so your second account is 1, your third account is 2, and so on).
* click "Add account"
* retrieve keys from your device as usual (over USB, airgapped SD card, or QR code)

Now that the other account's keys have been imported, create a new wallet using the new key. After scanning this new wallet for funds, you should see your expected balance.

Apart from that, your old wallet might have used non-standard derivation pathes or extended them in a non-standard-way. [https://walletsrecovery.org/](https://walletsrecovery.org/) is a good source for collecting such information about your old wallet.

### *How to delete a wallet using a remote full node?*

You can't delete the wallet if you are using remote Bitcoin Core node - there is no RPC call to do it remotely. So, deleting wallet works only on the same computer. 
You can also just delete the wallet manually. It's a folder in `~/.bitcoin` directory and in `~/.specter` as well.

### *Trying to connect specter-desktop to my remote node on my LAN few times but no success. `bitcoin.conf` has the `server=1` option, should there be something else since I get this error `Process finished with code -1Error message: Failed to connect` message?*

`rpcallowip` and `rpcbind` parameters need to be set in `bitcoin.conf`

### Backup files not showing when trying to load backups

When trying to load backups you are required to select the backup folders for either devices or wallets, you are NOT trying to select the JSON files.  You can also select the specter-backup folder itself which will allow both devices and wallets to be loaded together.  If you have issues doing this on the Specter app then try in browser instead. 

## DIY TROUBLESHOOT

### *Does anyone have any tips on mounting the power bank and QR code scanner to the STM32 board in a somewhat ergonomic manner?*

Use the smallest powerbank possible.

## HWW TROUBLESHOOT

Got stuck for a second because I wasn't safely removing my SD card reader, so the files were 0 bytes.

### *With achow's HWI tool, input and output PSBT are the same. And with Electrum 4, I get a rawtransaction, not a base64 PSBT.*

I solved my issue, it turns out my PSBT needed bip32 hints (whatever that means) included. I can now open lightning channels straight from hardware wallet!

## TECHNICAL QUESTIONS (not dev related)

### *Does specter-desktop require `txindex=1` to be set in your `bitcoin.conf`?*

No, but you need to enable wallets! `disablewallet=0`

### *Does specter-desktop specify an RPC wallet in the `bitcoin.conf` or append wallet name to node url?*

It specifes `-rpcwallet` with every call to `bitcoin-cli`

## FUTURE FEATURES

### *How are you guys planning to do air-gapped firmware updates via QR codes?*

We haven't tested it yet. We will work on the bootloader soon and try different update mechanisms. QR codes is one of them. Also considering SD card - might be easier as firmware is 1Mb, so it would require 1000 QR codes.

### *Will this device be Shamir Secret Shares compatible?*

Yes it will be, and especially effective in "forget after turn off" mode. Then one could use it to split a secret for wallets that don't support it.

### *Will there be CoinJoin support in the future?*

When CoinJoin servers and hardware wallets support proof of ownership: https://github.com/satoshilabs/slips/blob/slips-19-20-coinjoin-proofs/slip-0019.md

## VIDEOS

### **1** [Getting started with Specter-DIY and Specter-Desktop](https://twitter.com/CryptoAdvance/status/1235151027348926464)
![video](https://www.youtube.com/embed/eF4cgK_L6T4)

How to flash and set up an air-gapped hardware wallet that uses QR codes to communicate with the host.

In the video: 

 - Flashing the firmware
 - Generating a new key 
 - Importing keys to Specter-Desktop software 
 - Using single-key wallets 
 - Creating a multisignature wallet and importing it to the device 
 - Signing multisig transactions 

### **2** [Assembling Specter-DIY](https://www.youtube.com/watch?v=1H7FqG_FmCw)
![video](https://www.youtube.com/embed/1H7FqG_FmCw)

Specter-DIY hardware wallet: 

 - off-the-shelf components
 - costs 100$ - assemble in 5 minutes 
 - no soldering 
 - forgets your private key when powered off 

### **3** [Specter-DIY air-gapped open source bitcoin hardware wallet overview](https://twitter.com/KeithMukai/status/1189565099259944961)

### **4** [Build your own bitcoin hardware-wallet YT series](https://www.youtube.com/playlist?list=PLn2qRQUAAg0z_-R0swVuSsNS9bzRu6oP5&app=desktop)
![video](https://www.youtube.com/embed/AgOqTGeDrac)  [playlist](https://www.youtube.com/playlist?list=PLn2qRQUAAg0z_-R0swVuSsNS9bzRu6oP5&app=desktop)

### *What is the difference between that project (DIYbitcoinhardware) & Specter? Is DIYbitcoinhardware sort of a prerequisite for Specter?*

Specter is built on top of that micropython build. DIYbitcoinhardware is focusing more on the toolbox without actual application logic, Specter implements logic and GUI on top of it. 

Yes, that's why the video was recorded - to give some introduction about the tools we use, and hardware wallets logic in general.
