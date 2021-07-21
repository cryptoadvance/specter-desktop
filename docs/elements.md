# Elements/Liquid Support
Since `v1.5.0`, Specter-Desktop has basic Elements/Liquid Support. You can run/connect your own elements/liquid-node, you can create Liquid-Hotwallets and even combine them to multisig-wallets. Multisig with three hotwallets is indeed not that useful, but it's a start. We're planning to also support different assets (and might even have that already) and also support for Jade and specter-diy.

This document is a description on how to get started with elements/liquid. We'll first go into the details of setting up the node, mostly referring to external documents. Note that you have to checkout elements from source in order to get it running. The latest release `elements-0.18-1.12` is __not__ enough.

We'll first describe how to Compile elements, how to setup a elements-node (comparable to a bitcoin `regtest`) conveniently and then how to setup a liquid-node.

After that, we'll explain how to connect your Specter Desktop to that node, create wallets and sign transactions.

# Elements/Liquid Node

# Elements Compilation
Currently you have to checkout and compile elements yourself. You'll need to checkout the master-branch. If you want to be very sure that the collaboration works, you should checkout the exact commit which specter uses when doing automatic testing. You can see that commit in this [file](../tests/elements_gitrev_pinned) (currently `1ba24fe9b3cc3ad1166ed93a0969602d0c7898ff`).

You can checkout elements wherever you want as long as the `elementsd` and `elements-cli` will be available on the path or in the `tests/elements/src` folder. We assume here, you'll do the latter. If you have a ubuntu/debian-based linux, please check the easier way below before manually checking out:

```sh
cd tests
git clone https://github.com/ElementsProject/elements.git
cd elements
git checkout 1ba24fe9b3cc3ad1166ed93a0969602d0c7898ff # Use the commit from the file above
```

The rest is very system-specific and we're referring here to the documentation in liquid:
* [free-](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-freebsd.md)/[net-](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-netbsd.md)/[open-](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-openbsd.md)BSD
* [OsX](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-osx.md)
* [Unix/Linux](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-unix.md)
* [Windows](https://github.com/ElementsProject/elements/blob/elements-0.18.1.12/doc/build-windows.md)

If you're running a Debian/Ubuntu-based Linux-System, you can most probably use the script which we're using internally to setup our test-system. This will include the clone/checkout above. So simply start, from the root-folder of the project:

```sh
./tests/install_noded.sh --elements compile
```

Make sure that this is successfull by checking these two files to be existent:

```sh
ls tests/elements/src/elements-cli tests/elements/src/elementsd
tests/elements/src/elements-cli  tests/elements/src/elementsd
```

