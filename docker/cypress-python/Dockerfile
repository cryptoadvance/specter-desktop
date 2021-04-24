FROM cypress/base:12

RUN apt-get update && apt-get install -y \
    python3-pip python3-virtualenv zip unzip file apt libusb-1.0-0-dev libudev-dev \
    bc libevent-2.1-6

# Stuff needed for Elements (compilation)
RUN DEBIAN_FRONTEND="noninteractive" apt-get install  --no-install-recommends -y bsdmainutils libboost-test-dev libboost-filesystem-dev libboost-thread-dev libsqlite3-dev git

# Tor is dependent on /usr/lib/x86_64-linux-gnu/libevent-2.1.so.7 which is not available
# on this buster based image. So here is tiny ugly hack which make it working
RUN ln -s /usr/lib/x86_64-linux-gnu/libevent-2.1.so.6.0.2 /usr/lib/x86_64-linux-gnu/libevent-2.1.so.7


WORKDIR /test
RUN rm -rf node_modules package-lock.json ~/.cache/Cypress
RUN npm install --save-dev cypress@7.1.0
RUN $(npm bin)/cypress verify
