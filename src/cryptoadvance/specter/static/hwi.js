class HWIBridge {
    constructor(url, chain) {
        this.url = url;
        this.deviceTypes = ['specter', 'coldcard', 'keepkey', 'ledger', 'bitbox02', 'trezor'];
        this.chain = chain;
        this.in_progress = false;
    }
    async fetch(command, params={}, timeout=0){
        if(this.in_progress){
            throw "HWI is busy processing previous request.";
        }
        this.in_progress = true;
        let data = null;
        const controller = new AbortController()

        if (timeout > 0) {
            const timeoutId = setTimeout(() => controller.abort(), timeout);
        }
        try{
            if (command != 'detect_device' && command != 'enumerate') {
                params.chain = this.chain;
            }
            data = await fetch(this.url, {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                signal: controller.signal,
                body: JSON.stringify({
                    'jsonrpc': '2.0', 
                    'method': command, 
                    'id': 1,
                    params,
                    forwarded_request: (this.url !== '/hwi/api/'),
                })
            }).then(response => response.json());
        }finally{
            this.in_progress = false;
        }
        if('error' in data){
            throw data.error;
        }
        return data.result;
    }
    async enumerate(passphrase="", useTimeout){
        return await this.fetch("enumerate", { 
            passphrase
        }, (useTimeout ? 60000 : 0));
    }
    async detectDevice(type, rescan=true){
        // TODO: fingerprint, path, type
        return await this.fetch("detect_device", 
            { device_type: type, rescan_devices: rescan });
    }

    async togglePassphrase(device) {
        /**
            Tells the server to send the 'togglepassphrase' command to the device.
            KeepKey and Trezor only.
        **/
        return await this.fetch('toggle_passphrase', {
            device_type: device.type,
            path: device.path
        });
    }

    async getBitbox02PairingCode() {
        /**
            Asks the HWI server for a pairing code for BitBox02.
            Returns {"code": ""} with the code or an empty string if none found.
        **/
        return await this.fetch('bitbox02_pairing', {});
    }

    async promptPin(device, passphrase="") {
        /**
            Tells the server to send the 'promptpin' command to the device.
            KeepKey and Trezor only.
        **/
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('prompt_pin', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
        });
    }

    async sendPin(device, pin, passphrase="") {
        /**
            Submits the PIN for the 'sendpin' command to the device.
            KeepKey and Trezor only.
        **/
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('send_pin', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
            pin: pin,
        });
    }

    async signTx(device, psbt, passphrase="") {
        /**
            Sends the current psbt to the server to relay to the HWI wallet.
        **/
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('sign_tx', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
            psbt: psbt
        });
    }

    async signMessage(device, message, derivationPath, passphrase="") {
        /**
            Sends the message and derivation path to sign with to the server to relay to the HWI wallet.
        **/
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('sign_message', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
            message: message,
            derivation_path: derivationPath
        });
    }

    async getXpubs(device, account=0, passphrase="", chain=""){
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('extract_xpubs', {
            device_type: device.type,
            account: account,
            path: device.path,
            passphrase: device.passphrase,
            chain: chain,
        });
    }


    async getXpub(device, derivation="", passphrase="", chain=""){
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('extract_xpub', {
            device_type: device.type,
            derivation: derivation,
            path: device.path,
            passphrase: device.passphrase,
            chain: chain,
        });
    }

    async getMasterBlindingKey(device, passphrase="", chain=""){
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('extract_master_blinding_key', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
            chain: chain,
        });
    }


    async displayAddress(device, descriptor, passphrase=""){
        if(!('passphrase' in device)){
            device.passphrase = passphrase;
        }
        return await this.fetch('display_address', {
            device_type: device.type,
            path: device.path,
            passphrase: device.passphrase,
            descriptor: JSON.parse(descriptor),
        });
    }
}
