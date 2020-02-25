# Specter over SSH-tunnel

If you want to have access to your wallet outside of your local network you can either [use Tor](./tor.md), or make a reverse proxy from your node to a cheap VPS somewhere.

Here we will describe how to set up your VPS server to forward all requests to your Bitcoin node.

You can either have both Specter and Bitcoin Core on the same node and forward Specter interface to remote server, or you can only do it for Bitcoin Core and keep Specter on your laptop. I will assume first option, if you want to go with the second one just change the port from `25441` to `8334` or whatever port your Core is using.

## Basic configuration

Update your remote server:

```sh
apt update && apt upgrade
```

Install nginx:

```sh
apt install nginx
```

Add a new server to your nginx configuration `/etc/nginx/sites-enabled/default`:

```sh
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    # optinaly configure domain name
    server_name specter.mydomain.com;
    # set proxy pass
    location / {
        proxy_pass http://127.0.0.1:25441;
    }
}
```

Restart nginx:

```sh
nginx -s reload
```

On your local computer (where Specter is running) start a reverse proxy:

```sh
ssh -nN -R 25441:localhost:25441 user@specter.mydomain.com
```

Check in your browser - when you navigate to `http://specter.mydomain.com` you should see Specter already.

## Adding HTTPS

HTTPS is very important, not only because it is secure, but also because without HTTPS we can't use camera to scan QR codes. We need to get secure connection.

Letsencrypt issues certificates for free, they just need to check that you control the domain. So it doesn't work for local network or for Tor addresses. In these cases you would need to create a [self-signed certificate](./self-signed-certificates.md). But domains are cheap and probably everyone has a dozen that is not used. So we assume you have one.

Install certbot to issue certificate for us:

```sh
apt install software-properties-common
add-apt-repository universe
add-apt-repository ppa:certbot/certbot
apt update
apt install certbot python-certbot-nginx
```

Run `certbot` and answer it's questions:

```sh
certbot --nginx
```

Now Specter should be available over HTTPS: `https://specter.mydomain.com`

## Adding basic authentication

*Note:* This part is only required if you are running Specter on your node. If you are exposing your Bitcoin RPC it already has authentication with rpcuser and rpcpassword.

We don't want random people to have access to our wallet, so we want to protect it with login and password.

Nginx has a nice [documentation](https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-http-basic-authentication/) on the topic, but I will copy-paste main commands here.

Verify that `apache2-utils` (Debian, Ubuntu) or `httpd-tools` (RHEL/CentOS/Oracle Linux) is installed.

```sh
apt install apache2-utils
```

Create your user (let's call it `specter`) and type the password:

```sh
htpasswd -c /etc/nginx/.htpasswd specter
```

Add two lines to the server block in the nginx config (`/etc/nginx/sites-enabled/default`):

```sh
server {
    # ...

    auth_basic "You shall not pass!";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:25441;
    }
    # ...
}
```

Restart nginx:

```sh
nginx -s reload
```

Now when you try to access the server it will ask for credentials.
