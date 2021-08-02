import cbor
import json
import time
import logging
import collections
import traceback
import requests
import random

# JadeError
from .jade_error import JadeError

# Low-level comms backends
from .jade_serial import JadeSerialImpl

# Not used in HWI
# Removed to reduce transitive dependencies
# from .jade_ble import JadeBleImpl


# Default serial connection
DEFAULT_SERIAL_DEVICE = "/dev/ttyUSB0"
DEFAULT_BAUD_RATE = 115200
DEFAULT_SERIAL_TIMEOUT = 120

# Default BLE connection
DEFAULT_BLE_DEVICE_NAME = "Jade"
DEFAULT_BLE_SERIAL_NUMBER = None
DEFAULT_BLE_SCAN_TIMEOUT = 60

# 'jade' logger
logger = logging.getLogger("jade")
device_logger = logging.getLogger("jade-device")


#
# High-Level Jade Client API
# Builds on a JadeInterface to provide a meaningful API
#
# Either:
#  a) use with JadeAPI.create_[serial|ble]() as jade:
# (recommended)
# or:
#  b) use JadeAPI.create_[serial|ble], then call connect() before
#     using, and disconnect() when finished
# (caveat cranium)
# or:
#  c) use ctor to wrap existing JadeInterface instance
# (caveat cranium)
#
class JadeAPI:
    def __init__(self, jade):
        assert jade is not None
        self.jade = jade

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            logger.error("Exception causing JadeAPI context exit.")
            logger.error(exc_type)
            logger.error(exc)
            traceback.print_tb(tb)
        self.disconnect(exc_type is not None)

    @staticmethod
    def create_serial(device=None, baud=None, timeout=None):
        impl = JadeInterface.create_serial(device, baud, timeout)
        return JadeAPI(impl)

    @staticmethod
    def create_ble(device_name=None, serial_number=None, scan_timeout=None, loop=None):
        impl = JadeInterface.create_ble(device_name, serial_number, scan_timeout, loop)
        return JadeAPI(impl)

    # Connect underlying interface
    def connect(self):
        self.jade.connect()

    # Disconnect underlying interface
    def disconnect(self, drain=False):
        self.jade.disconnect(drain)

    # Drain all output from the interface
    def drain(self):
        self.jade.drain()

    # Simple http request function which can be used when a Jade response requires
    # an external http call.
    # The default implementation used in _jadeRpc() below.
    @staticmethod
    def _http_request(params):
        logger.debug("_http_request: {}".format(params))

        # Use the first non-onion url
        url = [url for url in params["urls"] if ".onion" not in url][0]
        if params["method"] == "GET":
            assert "data" not in params, "Cannot pass body to requests.get"
            f = requests.get(url)
        elif params["method"] == "POST":
            data = json.dumps(params["data"])
            f = requests.post(url, data)

        logger.debug("http_request received reply: {}".format(f.text))

        if f.status_code != 200:
            logger.error("http error {} : {}".format(f.status_code, f.text))
            raise ValueError(f.status_code)

        assert params["accept"] == "json"
        f = f.json()

        return {"body": f}

    # Raise any returned error as an exception
    @staticmethod
    def _get_result_or_raise_error(reply):
        if "error" in reply:
            e = reply["error"]
            raise JadeError(e.get("code"), e.get("message"), e.get("data"))

        return reply["result"]

    # Helper to call wrapper interface rpc invoker
    def _jadeRpc(
        self,
        method,
        params=None,
        inputid=None,
        http_request_fn=None,
        long_timeout=False,
    ):
        newid = inputid if inputid else str(random.randint(100000, 999999))
        request = self.jade.build_request(newid, method, params)
        reply = self.jade.make_rpc_call(request, long_timeout)
        result = self._get_result_or_raise_error(reply)

        # The Jade can respond with a request for interaction with a remote
        # http server. This is used for interaction with the pinserver but the
        # code below acts as a dumb proxy and simply makes the http request and
        # forwards the response back to the Jade.
        # Note: the function called to make the http-request can be passed in,
        # or defaults to the simple _http_request() function above.
        if isinstance(result, collections.Mapping) and "http_request" in result:
            make_http_request = http_request_fn or self._http_request
            http_request = result["http_request"]
            http_response = make_http_request(http_request["params"])
            return self._jadeRpc(
                http_request["on-reply"],
                http_response["body"],
                http_request_fn=make_http_request,
                long_timeout=long_timeout,
            )

        return result

    # Get version information from the hw
    def get_version_info(self):
        return self._jadeRpc("get_version_info")

    # Add client entropy to the hw rng
    def add_entropy(self, entropy):
        params = {"entropy": entropy}
        return self._jadeRpc("add_entropy", params)

    # OTA new firmware
    def ota_update(self, fwcmp, fwlen, chunksize, cb):

        compressed_size = len(fwcmp)

        # Initiate OTA
        params = {"fwsize": fwlen, "cmpsize": compressed_size}

        result = self._jadeRpc("ota", params)
        assert result is True

        # Write binary chunks
        written = 0
        while written < compressed_size:
            remaining = compressed_size - written
            length = min(remaining, chunksize)
            chunk = bytes(fwcmp[written : written + length])
            result = self._jadeRpc("ota_data", chunk)
            assert result is True
            written += length

            if cb:
                cb(written, compressed_size)

        # All binary data uploaded
        return self._jadeRpc("ota_complete")

    # Run (debug) healthcheck on the hw
    def run_remote_selfcheck(self):
        return self._jadeRpc("debug_selfcheck")

    # Set the (debug) mnemonic
    def set_mnemonic(self, mnemonic):
        params = {"mnemonic": mnemonic}
        return self._jadeRpc("debug_set_mnemonic", params)

    # Set the (debug) seed
    def set_seed(self, seed):
        params = {"seed": seed}
        return self._jadeRpc("debug_set_mnemonic", params)

    # Trigger user authentication on the hw
    # Involves pinserver handshake
    def auth_user(self, network, http_request_fn=None):
        params = {"network": network}
        return self._jadeRpc(
            "auth_user", params, http_request_fn=http_request_fn, long_timeout=True
        )

    # Get xpub given a path
    def get_xpub(self, network, path):
        params = {"network": network, "path": path}
        return self._jadeRpc("get_xpub", params)

    # Get receive-address for parameters
    def get_receive_address(
        self, *args, recovery_xpub=None, csv_blocks=0, variant=None
    ):
        if variant is not None:
            assert len(args) == 2
            keys = ["network", "path", "variant"]
            args += (variant,)
        else:
            assert len(args) == 4
            keys = [
                "network",
                "subaccount",
                "branch",
                "pointer",
                "recovery_xpub",
                "csv_blocks",
            ]
            args += (recovery_xpub, csv_blocks)
        return self._jadeRpc("get_receive_address", dict(zip(keys, args)))

    # Sign a message
    def sign_message(self, path, message):
        params = {"path": path, "message": message}
        return self._jadeRpc("sign_message", params)

    # Get a Liquid public blinding key for a given script
    def get_blinding_key(self, script):
        params = {"script": script}
        return self._jadeRpc("get_blinding_key", params)

    # Get the shared secret to unblind a tx, given the receiving script on
    # our side and the pubkey of the sender (sometimes called "nonce" in
    # Liquid)
    def get_shared_nonce(self, script, their_pubkey):
        params = {"script": script, "their_pubkey": their_pubkey}
        return self._jadeRpc("get_shared_nonce", params)

    # Get a "trusted" blinding factor to blind an output. Normally the blinding
    # factors are generated and returned in the `get_commitments` call, but
    # for the last output the VBF must be generated on the host side, so this
    # call allows the host to get a valid ABF to compute the generator and
    # then the "final" VBF. Nonetheless, this call is kept generic, and can
    # also generate VBFs, thus the "type" parameter.
    # `hash_prevouts` is computed as specified in BIP143 (double SHA of all
    #   the outpoints being spent as input. It's not checked right away since
    #   at this point Jade doesn't know anything about the tx we are referring
    #   to. It will be checked later during `sign_liquid_tx`.
    # `output_index` is the output we are trying to blind.
    # `type` can either be "ASSET" or "VALUE" to generate ABFs or VBFs.
    def get_blinding_factor(self, hash_prevouts, output_index, type):
        params = {
            "hash_prevouts": hash_prevouts,
            "output_index": output_index,
            "type": type,
        }
        return self._jadeRpc("get_blinding_factor", params)

    # Generate the blinding factors and commitments for a given output.
    # Can optionally get a "custom" VBF, normally used for the last
    # input where the VBF is not random, but generated accordingly to
    # all the others.
    # `hash_prevouts` and `output_index` have the same meaning as in
    #   the `get_blinding_factor` call.
    # NOTE: the `asset_id` should be passed as it is normally displayed, so
    # reversed compared to the "consensus" representation.
    def get_commitments(self, asset_id, value, hash_prevouts, output_index, vbf=None):
        params = {
            "asset_id": asset_id,
            "value": value,
            "hash_prevouts": hash_prevouts,
            "output_index": output_index,
        }
        if vbf is not None:
            params["vbf"] = vbf
        return self._jadeRpc("get_commitments", params)

    # Sign a Liquid txn
    def sign_liquid_tx(self, network, txn, inputs, commitments, change):
        # Protocol:
        # 1st message contains txn and number of inputs we are going to send.
        # Reply ok if that corresponds to the expected number of inputs (n).
        # Then we send one message per input - without expecting replies.
        # Once all n input messages are sent, the hw then sends all n replies
        # (as the user has a chance to confirm/cancel at this point).
        # Then receive all n replies for the n signatures.
        # NOTE: *NOT* a sequence of n blocking rpc calls.

        base_id = 100 * random.randint(1000, 9999)
        params = {
            "network": network,
            "txn": txn,
            "num_inputs": len(inputs),
            "trusted_commitments": commitments,
            "change": change,
        }
        reply = self._jadeRpc("sign_liquid_tx", params, str(base_id))
        assert reply

        # Send all n inputs
        requests = []
        for (i, txinput) in enumerate(inputs, 1):
            res_id = str(base_id + i)
            request = self.jade.build_request(res_id, "tx_input", txinput)
            self.jade.write_request(request)
            requests.append(request)
            time.sleep(0.1)

        # Receive all n signatures
        signatures = []
        for request in requests:
            reply = self.jade.read_response()
            self.jade.validate_reply(request, reply)
            signature = self._get_result_or_raise_error(reply)
            signatures.append(signature)

        assert len(signatures) == len(inputs)
        return signatures

    # Sign a txn
    def sign_tx(self, network, txn, inputs, change):
        # Protocol:
        # 1st message contains txn and number of inputs we are going to send.
        # Reply ok if that corresponds to the expected number of inputs (n).
        # Then we send one message per input - without expecting replies.
        # Once all n input messages are sent, the hw then sends all n replies
        # (as the user has a chance to confirm/cancel at this point).
        # Then receive all n replies for the n signatures.
        # NOTE: *NOT* a sequence of n blocking rpc calls.

        base_id = 100 * random.randint(1000, 9999)
        params = {
            "network": network,
            "txn": txn,
            "num_inputs": len(inputs),
            "change": change,
        }
        reply = self._jadeRpc("sign_tx", params, str(base_id))
        assert reply

        # Send all n inputs
        requests = []
        for (i, txinput) in enumerate(inputs, 1):
            res_id = str(base_id + i)
            request = self.jade.build_request(res_id, "tx_input", txinput)
            self.jade.write_request(request)
            requests.append(request)
            time.sleep(0.1)

        # Receive all n signatures
        signatures = []
        for request in requests:
            reply = self.jade.read_response()
            self.jade.validate_reply(request, reply)
            signature = self._get_result_or_raise_error(reply)
            signatures.append(signature)

        assert len(signatures) == len(inputs)
        return signatures


#
# Mid-level interface to Jade
# Wraps either a serial or a ble connection
# Calls to send and receive bytes and cbor messages over the interface.
#
# Either:
#  a) use wrapped with JadeAPI
# (recommended)
# or:
#  b) use with JadeInterface.create_[serial|ble]() as jade:
#       ...
# or:
#  c) use JadeInterface.create_[serial|ble], then call connect() before
#     using, and disconnect() when finished
# (caveat cranium)
# or:
#  d) use ctor to wrap existing low-level implementation instance
# (caveat cranium)
#
class JadeInterface:
    def __init__(self, impl):
        assert impl is not None
        self.impl = impl

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            logger.error("Exception causing JadeInterface context exit.")
            logger.error(exc_type)
            logger.error(exc)
            traceback.print_tb(tb)
        self.disconnect(exc_type is not None)

    @staticmethod
    def create_serial(device=None, baud=None, timeout=None):
        impl = JadeSerialImpl(
            device or DEFAULT_SERIAL_DEVICE,
            baud or DEFAULT_BAUD_RATE,
            timeout or DEFAULT_SERIAL_TIMEOUT,
        )
        return JadeInterface(impl)

    @staticmethod
    def create_ble(device_name=None, serial_number=None, scan_timeout=None, loop=None):
        impl = JadeBleImpl(
            device_name or DEFAULT_BLE_DEVICE_NAME,
            serial_number or DEFAULT_BLE_SERIAL_NUMBER,
            scan_timeout or DEFAULT_BLE_SCAN_TIMEOUT,
            loop=loop,
        )
        return JadeInterface(impl)

    def connect(self):
        self.impl.connect()

    def disconnect(self, drain=False):
        if drain:
            self.drain()

        self.impl.disconnect()

    def drain(self):
        logger.warn("Draining interface...")
        drained = bytearray()
        finished = False

        while not finished:
            byte_ = self.impl.read(1)
            drained.extend(byte_)
            finished = byte_ == b""

            if finished or byte_ == b"\n" or len(drained) > 256:
                try:
                    device_logger.warn(drained.decode("utf-8"))
                except Exception as e:
                    # Dump the bytes raw and as hex if decoding as utf-8 failed
                    device_logger.warn("Raw:")
                    device_logger.warn(drained)
                    device_logger.warn("----")
                    device_logger.warn("Hex dump:")
                    device_logger.warn(drained.hex())

                # Clear and loop to continue collecting
                drained.clear()

    @staticmethod
    def build_request(input_id, method, params=None):
        request = {"method": method, "id": input_id}
        if params is not None:
            request["params"] = params
        return request

    @staticmethod
    def serialise_cbor_request(request):
        dump = cbor.dumps(request)
        len_dump = len(dump)
        if "method" in request and "ota_data" in request["method"]:
            msg = "Sending ota_data message {} as cbor of size {}".format(
                request["id"], len_dump
            )
            logger.info(msg)
        else:
            logger.info("Sending: {} as cbor of size {}".format(request, len_dump))
        return dump

    def write(self, bytes_):
        logger.debug("Sending: {} bytes".format(len(bytes_)))
        wrote = self.impl.write(bytes_)
        logger.debug("Sent: {} bytes".format(len(bytes_)))
        return wrote

    def write_request(self, request):
        msg = self.serialise_cbor_request(request)
        written = 0
        while written < len(msg):
            written += self.write(msg[written:])

    def read(self, n):
        logger.debug("Reading {} bytes...".format(n))
        bytes_ = self.impl.read(n)
        logger.debug("Received: {} bytes".format(len(bytes_)))
        return bytes_

    def read_cbor_message(self):
        while True:
            # 'self' is sufficiently 'file-like' to act as a load source.
            # Throws EOFError on end of stream/timeout/lost-connection etc.
            message = cbor.load(self)

            # A message response (to a prior request)
            if "id" in message:
                logger.info("Received msg: {}".format(message))
                return message

            # A log message - handle as normal
            if "log" in message:
                response = message["log"].decode("utf-8")
                log_methods = {
                    "E": device_logger.error,
                    "W": device_logger.warn,
                    "I": device_logger.info,
                    "D": device_logger.debug,
                    "V": device_logger.debug,
                }
                log_method = device_logger.error
                if len(response) > 1 and response[1] == " ":
                    lvl = response[0]
                    log_method = log_methods.get(lvl, device_logger.error)

                log_method(">> {}".format(response))
            else:
                # Unknown/unhandled/unexpected message
                logger.error("Unhandled message received")
                device_logger.error(message)

    def read_response(self, long_timeout=False):
        while True:
            try:
                return self.read_cbor_message()
            except EOFError as e:
                if not long_timeout:
                    raise

    @staticmethod
    def validate_reply(request, reply):
        assert isinstance(reply, dict) and "id" in reply
        assert ("result" in reply) != ("error" in reply)
        assert reply["id"] == request["id"] or reply["id"] == "00" and "error" in reply

    def make_rpc_call(self, request, long_timeout=False):
        # Write outgoing request message
        assert isinstance(request, dict)
        assert "id" in request and len(request["id"]) > 0
        assert "method" in request and len(request["method"]) > 0
        assert len(request["id"]) < 16 and len(request["method"]) < 32
        self.write_request(request)

        # Read and validate incoming message
        reply = self.read_response(long_timeout)
        self.validate_reply(request, reply)

        return reply
