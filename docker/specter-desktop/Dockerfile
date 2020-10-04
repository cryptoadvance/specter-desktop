FROM python:3

RUN apt-get update && apt-get install -y libusb-1.0-0-dev libudev-dev
RUN pip3 install cryptoadvance.specter

CMD ['python3', '-m', 'cryptoadvance.specter', 'server']
