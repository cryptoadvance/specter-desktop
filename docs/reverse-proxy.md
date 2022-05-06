# Specter over SSH-tunnel

If you want to have access to your wallet outside of your local network you can either [use Tor](./tor.md), or make a reverse proxy from your node to a cheap VPS somewhere.

Here we will describe how to set up your VPS server to forward all requests to your Bitcoin node.

You can either have both Specter and Bitcoin Core on the same node and forward Specter interface to remote server, or you can only do it for Bitcoin Core and keep Specter on your laptop. The following guide assumes the first option, however, if you want to go with the second one just change the port from `25441` to `8334` or whatever port your Core is using.

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

## Incorporate SSH tunnel into Specter.service file

To launch specter automatically on system startup, see [daemon.md](./daemon.md). Whether you use the specter python package or the tar.gz release, you can incorporate an ssh port forward to your reverse proxy to start automatically with specter. 

For the python approach, would use the following specter.service file:

```
[Unit]
Description=Specter Desktop Service
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
User=myusername
Type=simple
ExecStart=/usr/bin/python3 -m cryptoadvance.specter server & ssh -nN -R 25441:localhost:25441 user@specter.mydomain.com && fg
StandardInput=tty-force

[Install]
WantedBy=multi-user.target
```

The approach for using the tarball is commented out in the example in [daemon.md](./daemon.md).

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

## Authentication

We don't want random people to have access to our wallet, so we want to protect it with login and password. Specter has two methods of authentication built in.

You can configure the authentication method used by Specter at `https://specter.mydomain.com/settings/auth`

When authentication is enabled Specter rate limits attempts to login to frustrate brute force password guessing.

### Password Protection

User defined password is used by Specter to login (default: admin).

### RPC Password as PIN

The Bitcoin Core RPC password is used by Specter to login.

### Multiple Users

With this method you can choose the username and password of the Specter admin user. You can also invite other (limited) users to register also.

### Adding basic authentication via Nginx

*Note:* This part is only required if you do not want to use one of the built in Specter authentication methods. If you use Nginx basic authentication you should also think about rate limiting brute force attacks via software like `fail2ban`.

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
