FROM electronuserland/builder:14-wine-mono-08.22@sha256:d1e77adc30731b96080ca5fdd59f0445b93a62502e92a18bd44bea4ad5330dc2

RUN apt-get update && apt-get install -y python3.10 python3.10-dev python3-pip zip unzip file apt libusb-1.0-0-dev libudev-dev
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
