*Please create a full backup* before migrating or any major internal changes like switching to an electrum based installation. You can easily create a backup in Settings --> Backup Specter (zip file).

## Artifacts

Specter is available in several forms: as a GUI application, as a binary that can be executed like a web app, and as a PyPI package. Additionally, Specter is available as a Docker image via the awesome [Chiang Mai LN devs](https://github.com/lncm/docker-specter-desktop).

Signed hashsum files are available for all binaries.

## GUI Application

This is a GUI application with a windowed interface, which includes the Specter server.
Supported platforms: [Windows](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/Specter-Setup-{{ data.version }}.exe), [MacOS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/Specter-{{ data.version }}.dmg), [Linux (x86_64)](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specter_desktop-{{ data.version }}-x86_64-linux-gnu.tar.gz)

**Note on Linux**: you need to set up udev rules (included in the archive). Check out the [readme](https://github.com/cryptoadvance/specter-desktop/blob/master/udev/README.md#usage).

**Note on macOS**: The current build supports only macOS Catalina (10.15) or higher. If you'd like to run Specter on an older macOS version, you can [install Specter from Pip](https://github.com/cryptoadvance/specter-desktop#installing-specter-from-pip).


## specterd
Specterd is a command-line program that runs only the Specter server, behaving like a traditional web application.
Supported platforms: [Windows](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-win64.zip), [MacOS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-osx.zip), [Linux (x86_64)](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/specterd-{{ data.version }}-x86_64-linux-gnu.zip)

## PyPi Packages

If you’re experienced Python user and/or developer, you might appreciate the [pypi-packages](https://pypi.org/project/cryptoadvance.specter/) which are also available on our github-release-page.

## Signatures and hashes
[SHA256SUMS](https://github.com/cryptoadvance/specter-desktop/releases/download/{{ data.version }}/SHA256SUMS) file contains sha256 hashes of all binary files and signed with "Specter Signer's" GPG key.
You can get the public key from [here](http://keyserver.ubuntu.com/pks/lookup?op=get&search=0x785a2269ee3a9736ac1a4f4c864b7cf9a811fef7).
Fingerprint of the key is `785A 2269 EE3A 9736 AC1A 4F4C 864B 7CF9 A811 FEF7`
This key has been signed by @k9ert's key. For more information about Verifying signatures, see, e.g. this video.

# Release notes
{{ data.release_notes }}
