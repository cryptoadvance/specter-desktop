# Running Specter-Desktop on Windows

This description is for a pip-installation on windows. Regular Windows users please simply install the windows-specific binary. However having a pip-installation on windows might make sense for specific users:

1. Install Python 3.9 from Microsoft Store. You may need to install [Visual C++ Redistributable](https://support.microsoft.com/en-us/help/2977003/the-latest-supported-visual-c-downloads) for it.
2. Install libusb:
	- Download latest binary from https://libusb.info/ and extract
	- For 32-bit Windows:
		- Copy `MS32\dll\libusb-1.0.dll` to `C:\Windows\System32`
	- For 64-bit Windows:
		- Copy `MS64\dll\libusb-1.0.dll` to `C:\Windows\System32`
		- Copy `MS32\dll\libusb-1.0.dll` to `C:\Windows\SysWOW64`
3. Edit Bitcoin Core config file and make sure `server=1` is set (it's in `~\AppData\Roaming\Bitcoin\bitcoin.conf`)

Now you can install specter-desktop and run as usual:

```sh
python3 -m pip install cryptoadvance.specter
python3 -m cryptoadvance.specter server
```

Web interface should be on http://localhost:25441/

If you are running into problems with pip, you can install it via:
- download [get-pip.py](https://bootstrap.pypa.io/get-pip.py)
- in Command Prompt navigate to the folder where this file is located
- run `python3 get-pip.py`
- now you can install specter-desktop from Command Prompt and run as usual
