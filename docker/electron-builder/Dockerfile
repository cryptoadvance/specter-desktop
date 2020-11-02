FROM electronuserland/builder:wine

RUN apt-get update && apt-get install -y python3.8 python3-pip zip unzip file apt libusb-1.0-0-dev libudev-dev
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1