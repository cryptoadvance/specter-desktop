# SSL Certificate
## Why a certificate is important

Browsers require secure communication with the server to use camera API. Without it we can't use QR code scanning.

If you are running a VPS it's easy - you just [issue a new certificate](./reverse-proxy#adding-https) with Letsencrypt.

If you are only using the node at home and want to use it from your local network and via camera, you need to run it via SSL.

## Easy solution

The easiest solution is to simply add `--ssl` to the serve-command and the certificate will get created automatically in the specter-home-folder.
```
python3 -m cryptoadance.specter server --ssl
```

## Manual creation


A second way, which provides more customization, is to run the [`gen-certificate.sh`](gen-certificate.sh) script in this folder with your node's IP address as an argument:

```sh
gen-certificate.sh <your-node-local-ip-address>
```

It will create two files - `cert.pem` and `key.pem`.

### Bare Specter over HTTPS

Provide these files to Specter as arguments:

```sh
python -m cryptoadvance.specter server --cert=./cert.pem --key=./key.pem
```

*Note:* Adding `--tor=your-tor-password` will create a tor hidden service with https.

### Specter with Nginx

Assuming you copied the files to `/etc/ssl/certs` and `/etc/ssl/private` add the following lines to server config (`/etc/nginx/sites-enabled/default`):

```sh
listen 443 ssl http2;

ssl_certificate /etc/ssl/certs/cert.pem;
ssl_certificate_key /etc/ssl/private/key.pem;
ssl_protocols TLSv1.2 TLSv1.1 TLSv1;
```

The config should look like this:

```
server{
  listen 80 default_server;
  listen 443 ssl http2;
  
  server_name your_domain_or_ip;

  ssl_certificate /etc/ssl/certs/cert.pem;
  ssl_certificate_key /etc/ssl/private/key.pem;
  ssl_protocols TLSv1.2 TLSv1.1 TLSv1;

  location / {
    proxy_pass http://127.0.0.1:25441;
  }
}
```

### Adding certificate to trusted

With these certificates you should be able to navigate to your node using https, but you will see a scary warning.

In Firefox you can still proceed to the website, in Chrome you can't unless you add `cert.pem` file to trusted (on the phone you still can).

On **Mac**: copy `cert.pem` to your computer, add it to your keychain and set `Trust`:

- Don't forget to quit Chrome
- Start the Keychain Access app and open the `Certificates` category
- Drag your certificate file onto the Keychain Access window
- Right-click on your certificate and unfold the `Trust` list
- In row `When using this certificate`, choose `Always Trust`

Other platforms: ???
