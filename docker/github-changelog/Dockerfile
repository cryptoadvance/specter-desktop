FROM python:3.8

ARG REPO=https://github.com/cryptoadvance/github-changelog

RUN apt update && apt install -y git

WORKDIR /

RUN git clone $REPO; 

WORKDIR /github-changelog
RUN git checkout master

RUN python3 setup.py install

ENV PYTHONUNBUFFERED="1"

ENTRYPOINT ["changelog"]
