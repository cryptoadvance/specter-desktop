# This is a copy of https://github.com/lncm/docker-specter-desktop/blob/master/Dockerfile
# with as minimal changes as possible. I marked the changes with "(COMMENTED)"

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

ARG VERSION=master
ARG REPO=https://github.com/cryptoadvance/specter-desktop
ARG USER=specter
ARG DIR=/data/

FROM python:3.8.11-slim-buster AS builder

ARG VERSION
ARG REPO

RUN apt update && apt install -y git build-essential libusb-1.0-0-dev libudev-dev libffi-dev libssl-dev rustc cargo

WORKDIR /

# RUN git clone $REPO (COMMENTED) instead have the line below:
COPY . /specter-desktop

WORKDIR /specter-desktop

# RUN git checkout $VERSION (COMMENTED)
RUN sed -i "s/vx.y.z-get-replaced-by-release-script/${VERSION}/g; " setup.py
RUN pip3 install --upgrade pip
RUN pip3 install babel cryptography
RUN pip3 install .


FROM python:3.8.11-slim-buster as final

ARG USER
ARG DIR

LABEL maintainer="k9ert (k9ert@gmx.net)" # (CHANGED)

RUN apt update && apt install -y libusb-1.0-0-dev libudev-dev

# NOTE: Default GID == UID == 1000
RUN adduser --disabled-password \
            --home "$DIR" \
            --gecos "" \
            "$USER"

# Set user
USER $USER

# Make config directory
RUN mkdir -p "$DIR/.specter/"


# Copy over python stuff
COPY --from=builder /usr/local/lib/python3.8 /usr/local/lib/python3.8
COPY --from=builder /usr/local/bin /usr/local/bin


# Expose ports
EXPOSE 25441 25442 25443 

ENTRYPOINT ["/usr/local/bin/python3", "-m", "cryptoadvance.specter", "server", "--host", "0.0.0.0"]