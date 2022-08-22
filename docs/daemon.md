# Running as a daemon

How to use Specter as a service - launch on boot, start and stop in the background. This guide is for Linux-Users only.

## Specter as a Service

1. Create a file `/lib/systemd/system/specter.service` with the following content (replace `User=myusername` to your username):
```
[Unit]
Description=Specter Desktop Service
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
User=myusername
Type=simple
ExecStart=/usr/bin/python3 -m cryptoadvance.specter server
StandardInput=tty-force

[Install]
WantedBy=multi-user.target
```
2. Reload systemd with `sudo systemctl daemon-reload`
3. Enable service to run on boot with `sudo systemctl enable specter.service` (optional)
4. Start service with `sudo systemctl start specter.service`

To stop run `sudo systemctl stop specter.service`, to restart `sudo systemctl restart specter.service`

### Specter as a Service using the linux tarball (tar.gz) release

Users may want to run the linux tarball release as a system service. This has the added benefits over the python release of being easily verifiable using the release signing keys.
Unfortunately, there are some legacy locale issues that make running the tarball service difficult, so we will need to set local variables in a startup script that will then be called by the systemd service file.

1. Create a file where you normally add manually installed apps and scripts: e.g. `/usr/local/bin/start_specterd`
2. Add the following to the file:
```
#!/bin/bash

#script to set correct system local before starting specterd

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

/usr/bin/specterd server --host localhost --port 25441 \
# & ssh -nN -R 25441:localhost:25441 user@specter.mydomain.com \
# && fg

```
3. Make the script executable `sudo chmod +x /ust/local/bin/start_specterd`
4. Incorporate the script into your `specter.service` file:

```
[Unit]
Description=Specter Desktop Service
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
User=myusername
Type=simple
ExecStart=/usr/local/bin/start_specterd
StandardInput=tty-force

[Install]
WantedBy=multi-user.target
```
5. To start the specter service run `sudo systemctl daemon-reload && sudo systemctl enable --now specter.service`

You can check the status of specter.service by running `systemctl status specter.service` or for debugging, you can get more information by running `sudo journalctl -fu specter.service`

The commented section of the service file above refers to an optional reverse proxy setup which is covered in the [reverse_proxy.md](reverse-proxy.md) document.

## bitcoind as a Service

You can do the same for `bitcoind` if you want to, then both Specter and bitcoind will start on system boot.
To make bitcoind service follow the same steps, just name the service `bitcoind.service` and set `ExecStart=bitcoind` there.

## Specter with virtual environment

If you don't want to have Specter in your global python modules, you can use a virtual environment instead.

First create the virtual environment and install Specter there. Let's say the path is `/home/myusername/.venv_specter`.

Then you need to change the `specter.service` to the following:

```
[Unit]
Description=Specter Desktop Service
After=multi-user.target
Conflicts=getty@tty1.service

[Service]
User=myusername
Type=simple
ExecStart=/home/myusername/.venv_specter/bin/python -m cryptoadvance.specter server
Environment="PATH=/home/myusername/.venv_specter/bin"
StandardInput=tty-force

[Install]
WantedBy=multi-user.target
```
