# Binaries

There are two types of binaries:

## Specter Desktop
It's a windowed GUI application with Specter server included.
Supported platforms: [Windows](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/Specter-Setup-{{ data.version }}.exe), [MacOS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/Specter-{{ data.version }}.dmg), [Linux (x86_64)](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specter_desktop-{{ data.version }}-x86_64-linux-gnu.tar.gz)

**Note on Linux**: you need to set up udev rules (included in the archive). Check out [readme](https://github.com/cryptoadvance/specter-desktop/blob/master/udev/README.md#usage).

**Note on macOS**: The current build supports only macOS Catalina (10.15) or higher. If you'd like to run Specter on an older macOS version, you can [install Specter from Pip](https://github.com/cryptoadvance/specter-desktop#installing-specter-from-pip).

## specterd
It's a command-line program that only runs Specter server.
Supported platforms: [Windows](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-win64.zip), [MacOS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-osx.zip), [Linux (x86_64)](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-x86_64-linux-gnu.zip)

## Signatures and hashes
[SHA256SUMS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/SHA256SUMS) file contains sha256 hashes of all binary files and signed with "Specter Signer's" GPG key.
You can get the public key from [here](http://keyserver.ubuntu.com/pks/lookup?op=get&search=0x785a2269ee3a9736ac1a4f4c864b7cf9a811fef7).
Fingerprint of the key is `785A 2269 EE3A 9736 AC1A 4F4C 864B 7CF9 A811 FEF7`
This key has been signed by @k9ert's key which you might have used for validating th 1.7.0 release.

# Release notes
{{ data.release_notes }}
