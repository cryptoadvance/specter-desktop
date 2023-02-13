FROM registry.gitlab.com/cryptoadvance/specter-desktop/cypress-base-ubuntu-jammy:20220908

RUN apt-get update && apt-get install -y \
    python3-pip python3-virtualenv zip unzip file apt libusb-1.0-0-dev libudev-dev \
    bc libevent-2.1-7 jq wget curl  libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev \
    libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb
	# https://docs.cypress.io/guides/continuous-integration/introduction#Dependencies

# Stuff needed for Elements (compilation)
RUN DEBIAN_FRONTEND="noninteractive" apt-get install  --no-install-recommends -y bsdmainutils \
			libboost-test-dev libboost-filesystem-dev libboost-thread-dev libsqlite3-dev git \
			libevent-pthreads-2.1-7  

# Stuff from the pre_prep script
RUN DEBIAN_FRONTEND="noninteractive" apt-get install -y --no-install-recommends python3-dev python3-pip python3-virtualenv bc

WORKDIR /test
RUN rm -rf node_modules package-lock.json ~/.cache/Cypress
RUN npm install --save-dev cypress@9.7.0
RUN $(npm bin)/cypress verify
