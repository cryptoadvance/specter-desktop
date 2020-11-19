# Running as a daemon

How to use Specter as a service - launch on boot, start and stop in the background.

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

## bitcoind as a service

You can do the same for `bitcoind` if you want to, then both Specter and bitcoind will start on system boot.
To make bitcoind service follow the same steps, just name the service `bitcoind.service` and set `ExecStart=bitcoind` there.

## Specter with virtual environment

Let's say you don't want to have Specter in you global python modules, but use a virtual environment instead.

First create the virtual environment and install Specter there, let's say the path is `/home/myusername/.venv_specter`.

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
