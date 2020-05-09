# Running Specter-Desktop on Windows

1. Install Python 3.7 from Microsoft Store (python 3.8 is not supported yet). You may need to install [Visual C++ Redistributable](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads) for it.
2. Install libusb:
	- Download latest binary from https://libusb.info/
	- Extract and copy content of MS64 folder to your `Windows\System32` folder
3. Edit Bitcoin Core config file and make sure `server=1` is set (it's in `~\AppData\Roaming\Bitcoin\bitcoin.conf`)

Now you can install specter-desktop and run as usual:

```sh
python3 -m pip install cryptoadvance.specter
python3 -m cryptoadvance.specter server
```

Web interface should be on http://localhost:25441/

*Note:* `--daemon` flag is not available on Windows yet. Also communication with a remote node is not tested yet.
