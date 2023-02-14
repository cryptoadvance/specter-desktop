# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

ARG USER=specter
ARG DIR=/data/

FROM python:3.10-slim-bullseye AS builder

ARG VERSION
ARG REPO

RUN apt update && apt install -y git build-essential libusb-1.0-0-dev libudev-dev libffi-dev libssl-dev rustc cargo libpq-dev

WORKDIR /

WORKDIR /specter-desktop

COPY . .

RUN pip3 install --upgrade pip
RUN pip3 install babel cryptography
RUN pip3 install .


FROM python:3.10-slim-bullseye as final

ARG USER
ARG DIR

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
COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=builder /usr/local/bin /usr/local/bin


# Expose ports
EXPOSE 25441 25442 25443 

ENTRYPOINT ["/usr/local/bin/python3", "-m", "cryptoadvance.specter", "server", "--host", "0.0.0.0"]
