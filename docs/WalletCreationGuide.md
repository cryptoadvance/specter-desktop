# Wallet Creation Guide

## Introduction

Specter wallets are designed to provide a user-friendly interface around Bitcoin Core, focusing on multisignature setups with airgapped signing devices, though they also support single-signature wallets. It's developed to make the interaction with Bitcoin Core more convenient for the users.

## Types of Wallets

### Single-Sig Wallets
- These involve one signing device or hardware wallet generating one seed.
- They are simpler and require only one secure location for seed backup.
- However, they are less secure against phishing attacks as one compromised seed can lead to lost Bitcoin.

### Multi-Sig Wallets
- More secure than single-sig, multisig wallets require two or more signing devices to authorize transactions.
- A key feature is the quorum requirement, which specifies the number of signatures needed out of the total number of devices. For example, a common scenario is requiring 2 signatures from a total of 3 devices (2/3 quorum). This setup enhances security as it requires multiple parties or devices to agree on a transaction.
- Multisig wallets are particularly effective against phishing and theft as compromising one seed or device is not enough to access the funds.
- They offer better security, as one compromised seed doesn't result in immediate loss of funds.
- However, they are more complex to set up and require multiple secure locations for seed backups.

#### Single-Sig Wallets Examples:

- A user with a **Ledger Nano S** hardware wallet creating a single-signature Specter wallet for added convenience in managing their Bitcoin holdings.
- Someone who wants a simple wallet setup opting for a single-signature wallet with their **Electrum** software wallet, as they trust their computer's security.

#### Multi-Sig Wallets Examples:

- A group of friends setting up a multi-signature Specter wallet for a shared investment fund, where multiple devices are required to authorize transactions, enhancing security. For more detailed guidance on setting up such a wallet, [refer to our Multi-Sig Wallet Guide](multisig-guide.md).
- A Bitcoin exchange using a multi-signature setup with several hardware wallets to protect customer funds against a single point of failure. [Our Multi-Sig Wallet Guide offers](multisig-guide.md) comprehensive steps and best practices for implementing such a secure system.


## Step-by-Step Guide for Single-Sig Wallets

1. **Setup and Installation**
   - Download and install the Specter Desktop app from the official GitHub release page. You can [find the installation guide here](install_guide.md).
   - Ensure your system meets the necessary requirements (like Python version, Bitcoin Core version).

2. **Running the App**
   - Start the Specter Desktop app.
   - It should automatically detect Bitcoin Core if it's using a default data folder.
   - If not, set rpcuser and rpcpassword in the Bitcoin Core's bitcoin.conf file and directly in the Specter app settings. You can [find the Node Connecting Guide here](connect-your-node.md).

3. **Creating a Wallet**
   - In Specter, navigate to the wallet creation section.
   - **Important:** Before proceeding, ensure you have imported your hardware wallet device (e.g., Ledger, BitBox, Trezor) into Specter Desktop. Specter is specifically designed to enhance security by working with hardware wallets, providing an extra layer of protection compared to hot wallets. For detailed instructions on connecting your hardware wallet, [refer to the Device Creation Guide](DeviceCreationGuide.md).
   - Choose the option for a single-signature wallet if you are setting up a wallet with one device. For enhanced security, consider setting up a multi-signature wallet.
   - When creating a single-signature wallet, Specter will interface with your hardware wallet. **Note:** If your hardware wallet is already initialized (which is the common scenario), Specter will use the existing seed from your device to manage the wallet. There is no need to generate a new seed within Specter. It is crucial to keep your seed secure and never enter it on the computer or share it with anyone.
   - **For New Hardware Wallet Users:**
    If your hardware wallet is new and not yet initialized, you will need to generate a new seed as part of the hardware wallet's setup process. This is typically done directly on the hardware wallet to ensure maximum security. Follow your hardware wallet's instructions for this step. Once your hardware wallet is initialized with a new seed, you can proceed to connect it with Specter Desktop.

4. **Backing Up the Wallet**
   - After creating the wallet, it's crucial to back up the seed securely.
   - For single-signature wallets, where the loss of the seed equates to the loss of funds, Specter strongly recommends storing seeds on steel. This method provides long-term durability against elements like fire and water, ensuring your backup remains intact in various scenarios.
   - While still advisable for multi-signature setups, steel backups in multisig configurations are slightly less critical since the loss of a single seed doesn’t necessarily mean loss of funds, provided other signatures are available. However, it is still a best practice to secure each seed with the utmost care.

5. **Testing the Wallet**
   - It's advisable to test the wallet by sending a small amount of Bitcoin to it and then trying to access these funds using the wallet.

## Backup PDFs

- Specter provides backup PDFs that contain crucial information like (master) public keys and fingerprints.
- These backups do not include the seed itself.
- Keep a copy of the backup PDFs with every seed backup, but ensure they are kept private as they allow anyone to recreate the wallet and see the balance.

## Notes

- Always ensure the safety of your seed phrases and backup information.
- Regularly update the Specter software and your Bitcoin Core node for security and functionality improvements.
- For multisig wallet creation, a separate, more detailed guide is recommended due to its complexity.
