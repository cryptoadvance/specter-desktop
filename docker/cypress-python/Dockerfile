FROM cypress/base:12

RUN apt-get update && apt-get install -y \
    python3-pip python3-virtualenv zip unzip file apt libusb-1.0-0-dev libudev-dev \
    bc

WORKDIR /test
RUN rm -rf node_modules package-lock.json ~/.cache/Cypress
RUN npm install --save-dev cypress@7.1.0
RUN $(npm bin)/cypress verify
