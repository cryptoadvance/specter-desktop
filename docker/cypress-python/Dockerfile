FROM registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-focal:latest

RUN apt-get update && apt-get install -y \
    python3-pip python3-virtualenv zip unzip file apt libusb-1.0-0-dev libudev-dev \
    bc libevent-2.1-7 jq wget curl

# Stuff needed for Elements (compilation)
RUN DEBIAN_FRONTEND="noninteractive" apt-get install  --no-install-recommends -y bsdmainutils libboost-test-dev libboost-filesystem-dev libboost-thread-dev libsqlite3-dev git libevent-pthreads-2.1-7


WORKDIR /test
RUN rm -rf node_modules package-lock.json ~/.cache/Cypress
RUN npm install --save-dev cypress@7.1.0
RUN $(npm bin)/cypress verify
