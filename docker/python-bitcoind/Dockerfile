
FROM python:3.8

# Installing BerkleyDB 4.8.30
# Ubuntu specific buw works on debian Buster as well
RUN apt remove libdb5.3-dev -y
RUN wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8++-dev_4.8.30-artful3_amd64.deb && \
	wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/db4.8-util_4.8.30-artful3_amd64.deb && \
	wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8-dbg_4.8.30-artful3_amd64.deb && \
	wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8_4.8.30-artful3_amd64.deb && \
	wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8-dev_4.8.30-artful3_amd64.deb && \
	wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8++_4.8.30-artful3_amd64.deb
RUN dpkg -i *.deb && rm *.deb

RUN apt update && apt install git build-essential autoconf libboost-all-dev libssl-dev libprotobuf-dev protobuf-compiler libqt4-dev libqrencode-dev libtool libevent-dev pkg-config bsdmainutils -y 

RUN git clone https://github.com/bitcoin/bitcoin.git
RUN cd bitcoin && git checkout v0.20.1
RUN cd bitcoin && ./autogen.sh && ./configure && make
RUN cd bitcoin && make install

FROM python:3.8

# Installing BerkleyDB 4.8.30
# Works on debian Buster as well
RUN apt remove libdb5.3-dev -y
RUN wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8++-dev_4.8.30-artful3_amd64.deb && \
        wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/db4.8-util_4.8.30-artful3_amd64.deb && \
        wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8-dbg_4.8.30-artful3_amd64.deb && \
        wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8_4.8.30-artful3_amd64.deb && \
        wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8-dev_4.8.30-artful3_amd64.deb && \
        wget https://launchpad.net/~bitcoin/+archive/ubuntu/bitcoin/+files/libdb4.8++_4.8.30-artful3_amd64.deb
RUN dpkg -i *.deb && rm *.deb

RUN apt update && apt install libevent-dev libboost-system-dev libboost-filesystem-dev libboost-chrono-dev libboost-test-dev libboost-thread-dev -y

COPY --from=0 /usr/local/bin/bitcoind /usr/local/bin
COPY --from=0 /usr/local/bin/bitcoin-cli /usr/local/bin

COPY --from=docker:latest /usr/local/bin/docker /usr/local/bin


