from ubuntu:jammy

# 1. python-stuff and HWI dependencies
# 2. capability to build bitcoind
# 3. cypress dependencies
RUN apt update && DEBIAN_FRONTEND="noninteractive" apt-get install --no-install-recommends -y \
    libusb-1.0-0-dev libudev-dev python3 python3-virtualenv python3-dev python3-pip \
    build-essential libtool autotools-dev automake autoconf pkg-config bsdmainutils libevent-dev libboost-dev libboost-system-dev libboost-filesystem-dev libboost-test-dev bc  \
    nodejs npm libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb \
    wget libzmq5-dev  

# Stuff needed for Elements (compilation)
RUN DEBIAN_FRONTEND="noninteractive" apt-get install  --no-install-recommends -y  libboost-thread-dev libsqlite3-dev git
