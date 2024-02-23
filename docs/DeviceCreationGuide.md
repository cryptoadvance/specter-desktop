# Device Creation Guide for Specter Hardware Wallets

## Introduction

Welcome to the Device Creation Guide for Specter Hardware Wallets. In this comprehensive guide, we'll walk you through the process of setting up hardware wallets within the Specter environment. Our focus is on ensuring the security of your digital assets while using various types of hardware wallets. We'll also delve into the crucial concept of derivation paths, which is essential for generating multiple keys from a single seed. Understanding these paths is key to managing and securing your Bitcoin effectively.

## Types of Hardware Wallets

### SD-Card Wallets

- **Features:** SD-Card hardware wallets offer unique features that prioritize both security and portability. We'll explore these features in detail to help you understand their advantages.
- **User background:** Alice, a traveling consultant, requires a secure yet portable solution to manage her digital assets. She often moves between locations and needs a reliable way to carry her Bitcoin wallet without internet connectivity risks.
- **Use Case:** Alice opts for an SD-Card hardware wallet. Its small size and portability make it an ideal choice for her travels. She can easily carry it in her purse or securely store it in a safe. The SD-Card wallet allows her to access her digital assets on the go, without the need for an internet connection, reducing the risk of online threats. Moreover, she uses the SD-Card as a secure backup, storing a duplicate in a safe location.
- **Supported Devices:**
  
  - BitBox02  <img src="../src/cryptoadvance/specter/static/img/devices/bitbox02_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> A Swiss-made hardware wallet known for its security and simplicity. It and features both SD-Card and USB interfaces for enhanced flexibility.
  - Coldcard  <img src="../src/cryptoadvance/specter/static/img/devices/coldcard_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> A popular choice for a secure and dedicated Bitcoin hardware wallet. Known for its advanced security features and ability to work with PSBT (Partially Signed Bitcoin Transactions).
  - Cobo  <img src="../src/cryptoadvance/specter/static/img/devices/cobo_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> Designed for durability and security, Cobo is a multi-cryptocurrency hardware wallet with SD-Card support for backup and recovery. 
  - Passport  <img src="../src/cryptoadvance/specter/static/img/devices/passport_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> This device emphasizes user-friendly design and privacy, offering air-gapped operation via QR codes and SD-Card backup.

### QR Code Wallets

- **Functionality:** QR code wallets operate differently, providing enhanced security through minimal direct connections with other devices. Learn how they work and why this matters.
- **User background:** Bob, a frequent user of Bitcoin for transactions, often finds himself in public places like coffee shops or conferences. He is concerned about the security risks associated with connecting his wallet to public Wi-Fi or potentially compromised devices.
- **Use Case:** Bob uses a QR Code wallet, which provides enhanced security through minimal direct connections. When making transactions, he simply scans the QR code displayed by his wallet. This method eliminates the need to connect to potentially insecure networks or devices, significantly reducing the risk of digital asset theft. The QR Code wallet’s ability to operate with minimal connectivity makes it an excellent choice for secure, hassle-free transactions in public settings.
- **Supported Devices:**
  
  - Jade  <img src="../src/cryptoadvance/specter/static/img/devices/jade_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> A budget-friendly hardware wallet with QR code functionality for secure and offline transactions.
  - SeedSigner  <img src="../src/cryptoadvance/specter/static/img/devices/seedsigner_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> An open-source project that focuses on creating a secure, offline transaction signing device using QR codes.

### USB Wallets

- **Characteristics:** USB wallets come with distinct features, including direct connectivity and user-friendly interfaces. Get a deeper understanding of what makes them stand out.
- **Scenarios:** Find out when and where USB wallets are your best choice. We'll showcase their versatility and compatibility with a wide range of devices.
- **User background:** Carol, a small business owner, accepts Bitcoin in her store. She needs a wallet that is both easy to use and compatible with various devices since she regularly deals with different types of transactions.
- **Use Case:** Carol chooses a USB wallet for its user-friendly interface and direct connectivity. The USB wallet's plug-and-play nature makes it simple to connect to her store's point-of-sale system or her personal computer. Its compatibility with various devices allows her to efficiently manage transactions without the need for specialized hardware. The USB wallet's intuitive interface makes it easy for Carol to navigate, making it an ideal choice for her everyday business transactions.
- **Supported Devices:**

  - BitBox02  <img src="../src/cryptoadvance/specter/static/img/devices/bitbox02_icon.svg" alt="BitBox02 Wallet" width="25" height="25"/> Swiss-made hardware wallet, offering a blend of security and simplicity. Bitcoin Only version available.
  - KeepKey  <img src="../src/cryptoadvance/specter/static/img/devices/keepkey_icon.svg" alt="Keystone Wallet" width="25" height="25"/> A user-friendly wallet with a large display, providing a secure environment for cryptocurrency storage and transactions.
  - Ledger  <img src="../src/cryptoadvance/specter/static/img/devices/ledger_icon.svg" alt="Ledger Wallet" width="25" height="25"/> Known for its security and sleek design, Ledger wallets support a wide range of cryptocurrencies. Less security since it contains code for other shitcoins.
  - Trezor  <img src="../src/cryptoadvance/specter/static/img/devices/trezor_icon.svg" alt="Trezor Wallet" width="25" height="25"/> One of the first hardware wallets in the market, renowned for its ease of use and robust security measures.
  - Keystone <img src="../src/cryptoadvance/specter/static/img/devices/keystone_icon.svg" alt="Keystone Wallet" width="25" height="25"/> Formerly known as Cobo Vault, Keystone wallets offer a high-security solution with air-gapped QR code signing. 

  
## Step-by-Step Guide for Device Creation in Specter

### Add a new device
Select signing device
![image](https://user-images.githubusercontent.com/47259243/223428531-2f3a04d4-177d-4626-8108-b66234892541.png)
Upload public keys
![image](https://user-images.githubusercontent.com/47259243/223427859-c06faec5-78ab-4592-9ba6-4018978280cc.png)

### Select how to connect to Bitcoin network
![image](https://user-images.githubusercontent.com/47259243/223425374-a3e68ac7-2bdb-48fe-a53b-59f235c59bd1.png)
Electrum server or...
![image](https://user-images.githubusercontent.com/47259243/223426046-dd225f00-ba18-45cb-871a-40efd7eefc1e.png)
...via Bitcoin Core node.
![image](https://user-images.githubusercontent.com/47259243/223426366-c3ba758a-34c4-4ce1-8aae-cf0cc335a892.png)


## Understanding Derivation Paths

### Concept Explanation

Understanding derivation paths is fundamental to managing the security of your digital assets. In this section, we'll provide you with an overview of what derivation paths are and why they matter. We'll also introduce key paths like BIP 44 (for multi-account hierarchy), BIP 49 (for SegWit compatibility), and BIP 84 (for native SegWit addresses). Each of these paths caters to different Bitcoin address types and plays a crucial role in organizing and securing your Bitcoin, especially within hardware wallets.

By default, Specter Wallets are set up with:
- BIP 44 for traditional multisig wallets.
- BIP 49 or BIP 84 for SegWit singlesig wallets.

These default settings cover the needs of most users, simplifying the wallet setup and usage process. However, understanding these paths can enhance your ability to tailor the wallet to your specific needs, especially if you have advanced security considerations.

### Challenges and Best Practices

1. **Complexity:** 
   - Derivation paths, especially when considering various Bitcoin address types like BIP 44, BIP 49, and BIP 84, can be intricate. The challenge lies in comprehending the nuances of each path and selecting the one that aligns with your specific use case. Best practice here is to educate yourself thoroughly and seek expert advice if needed.

2. **Compatibility:**
   - Using the wrong derivation path can lead to compatibility issues, making it challenging to access your funds. It's crucial to ensure that the path you choose is supported by your wallet software and the services you intend to use. Staying informed about updates and changes in the Bitcoin ecosystem is essential to avoid compatibility pitfalls.
   - To assist with this, [common derivation paths for different wallets can be found at Wallets Recovery](https://walletsrecovery.org/). This resource can be useful for understanding the standard practices of various wallets and ensuring compatibility.
   - Ensure that the path you choose is supported by your wallet software and the services you intend to use.

3. **Security Risks:**
   - Incorrectly managed derivation paths can introduce security risks. For instance, sharing your master public key (xpub) derived from an account with a third party may expose all the addresses generated from it. Best practice involves limiting the exposure of sensitive information and adopting a "need-to-know" approach when sharing keys or information related to derivation paths.
   - Limit the exposure of sensitive information and adopt a "need-to-know" approach when sharing keys or information related to derivation paths.

4. **Backup Strategies:**
   - Derivation paths affect how you back up your wallet. Implementing a robust backup strategy that includes the derivation path information is essential. Best practice is to maintain secure backups and periodically test your recovery process to ensure you can regain access to your digital assets if the need arises.
   - Implementing a robust backup strategy that includes the derivation path information is essential.

### Example 1: BIP 84 (Hierarchical Deterministic Wallets)
#### Scenario: Multiple Account Management

##### Context
Emily, a Bitcoin enthusiast, has diverse needs for managing her digital assets. She wants to separate her main funds from the stacking service provider she's using. For this, she needs a wallet structure that allows for clear separation while maintaining privacy and security.

##### Use Case
Emily opts to use the BIP 84 derivation path, which is designed for native SegWit addresses, providing her with an efficient and cost-effective way to manage her Bitcoin transactions. She uses two different paths within BIP 84 to separate her funds:
- For her main wallet, where she keeps the majority of her funds, Emily uses the derivation path `m/84'/0'/0'`. This path is for her personal use, ensuring that her primary funds remain secure and private.
- For the stacking service provider, which requires her to share her extended public key (xpub) for operational purposes, she uses the derivation path `m/84'/0'/1'`. This separation allows her to maintain privacy and security, as the service provider only has visibility over the funds in the dedicated stacking account.

##### Advantage
By using two distinct accounts under the BIP 84 standard, Emily efficiently manages her assets, keeping her main funds secure and private while still participating in stacking services.

### Example 2: BIP 49 (SegWit Compatibility in P2SH)
#### Scenario: Balancing Efficiency with Cost in Wallet Management

##### Context
John has been managing his Bitcoin assets using an older wallet setup. As the volume of his transactions increases, he's faced with the challenge of seeking more efficient transaction processing, both in terms of speed and reduced fees, without incurring significant costs in moving his funds.
##### Use Case
John's current wallet utilizes BIP 49, which enables SegWit compatibility through Pay to Script Hash (P2SH) addresses, identifiable by starting with '3'. His addresses follow the derivation path m/49'/0'/0'. Despite being aware of newer wallet technologies like those adhering to BIP 84, which offer even greater efficiencies by fully embracing native SegWit addresses (beginning with 'bc1'), John decides to stick with his current setup.
##### Advantage
John's decision is influenced by his desire to maintain his current UTXO set. He is cautious about the transaction fees that would be incurred in transferring his entire balance to a new wallet structure. By sticking with BIP 49, John still benefits from reduced transaction fees and improved speeds compared to legacy addresses, but he acknowledges that his setup is not as efficient as it could be with BIP 84. His choice represents a compromise between optimizing transaction efficiency and minimizing the costs associated with a complete migration to a new wallet system.

### Example 3: BIP 84 (Native SegWit Bech32 Addresses)
#### Scenario: Maximizing Efficiency and Exploring Testnets

##### Context
Lisa is a tech-savvy investor who keeps up with the latest developments in Bitcoin technology. She wants to use the most advanced and efficient method for managing her Bitcoin transactions. Additionally, Lisa is interested in exploring Bitcoin testnets for testing and educational purposes.

##### Use Case
Lisa opts for a wallet that implements BIP 84, which enables the creation of native SegWit addresses that start with 'bc1'. These are Bech32 addresses, which offer benefits such as more efficient block weight usage and better error detection. For her main Bitcoin transactions, her derivation path is: `m/84'/0'/0'`.

Moreover, Lisa is also experimenting with Bitcoin testnet. Testnets are crucial for trying out transactions without using real Bitcoin, which is an ideal environment for testing and learning. For her testnet transactions, she uses the derivation path `m/84'/1'/0'`. This path is specifically designated for testnet in BIP 84, allowing her to differentiate between real and test transactions easily.

##### Advantage
Using BIP 84, Lisa experiences lower fees and faster transactions in her main wallet. With the addition of the testnet path, she can safely experiment and learn without risking her actual Bitcoin. This approach not only future-proofs her wallet as the industry moves towards broader adoption of SegWit but also enhances her understanding and proficiency in managing digital assets.

### Conclusion
In each of these scenarios, the use of different derivation paths (BIP 44, BIP 49, and BIP 84) reflects a specific need and functionality in managing Bitcoin transactions:
- **BIP 44** is ideal for users like Emily, who require a structured organization for multiple types of transactions. It provides a clear hierarchical structure for different accounts under a single master seed.
- **BIP 49** benefits users like John, who seek efficiency and reduced costs in their transactions. The SegWit compatibility in P2SH format helps in lowering transaction fees and improving confirmation speeds.
- **BIP 84** is perfect for tech-savvy users like Lisa, who want to leverage the latest advancements in Bitcoin technology for optimal efficiency and future compatibility.

For those seeking a deeper understanding of derivation paths, we recommend exploring "[Learn Me a Bitcoin". This website provides in-depth information](https://learnmeabitcoin.com/technical/derivation-paths) on the topic, and you can integrate this knowledge into our guide for a more comprehensive grasp of derivation paths.

## Troubleshooting

### Common Issues

#### Check the USB Connection
- **Step 1:** Unplug the wallet from the computer.
- **Step 2:** Inspect the USB cable for any visible damage. If damaged, replace the cable.
- **Step 3:** Reconnect the wallet to the computer using a different USB port. Sometimes ports can malfunction or have poor connectivity.

#### Restart the Wallet and Computer
- **Step 1:** Safely eject the hardware wallet from your computer.
- **Step 2:** Restart the hardware wallet. If it has a power button, turn it off and then on again. If not, disconnect and reconnect it.
- **Step 3:** Restart your computer. This can resolve issues caused by temporary software glitches.

#### Update Wallet Firmware and Software
- **Step 1:** Check if your hardware wallet firmware is up to date. Refer to the wallet’s official website for the latest firmware version.
- **Step 2:** Update the wallet application on your computer. Ensure you're using the latest version.
- **Step 3:** After updating, reconnect the wallet and check if it is recognized.

#### Check Device Manager (Windows) or System Report (Mac)
**For Windows:**
- **Step 1:** Open 'Device Manager'.
- **Step 2:** Look under ‘Universal Serial Bus controllers’. Check if the wallet is listed or if there are any devices with a yellow exclamation mark.
- **Step 3:** If the wallet is listed with an error, right-click on it and select ‘Update driver’.

**For Mac:**
- **Step 1:** Click on the Apple logo and select ‘About This Mac’.
- **Step 2:** Go to ‘System Report’ and select ‘USB’.
- **Step 3:** Check if the wallet is listed under USB Device Tree.

#### Try a Different Computer
- **Step 1:** Connect the wallet to a different computer. This can help determine if the issue is with the original computer’s hardware or software.

#### Contact Customer Support or our Telegram Group
If none of the above steps work, the problem might be more complex or specific to the wallet. In this case, contact the customer support of the hardware wallet for further assistance.

### Preventive Measures
- Regularly update the wallet's firmware and the computer’s software to avoid compatibility issues.
- Use high-quality USB cables and ports to ensure a stable connection.
- Avoid exposing the hardware wallet to physical damage or extreme temperatures.

By the end of this guide, you'll be well-equipped to create and manage hardware wallets within the Specter environment and understand derivation paths. Let's get started on your journey to safeguarding your bitcoin journey.
