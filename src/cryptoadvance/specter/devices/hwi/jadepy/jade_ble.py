import logging
import asyncio
import aioitertools
import collections
import subprocess
import platform
import bleak

from .jade_error import JadeError

logger = logging.getLogger(__name__)


#
# Low-level BLE backend interface to Jade
# Calls to send and receive bytes over the interface.
# Intended for use via JadeInterface wrapper.
#
# Either:
#  a) use via JadeInterface.create_ble() (see JadeInterface)
# (recommended)
# or:
#  b) use JadeBleImpl() directly, and call connect() before
#     using, and disconnect() when finished,
# (caveat cranium)
#
class JadeBleImpl:
    IO_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    IO_TX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    IO_RX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
    BLE_MAX_WRITE_SIZE = 517 - 8

    def __init__(self, device_name, serial_number, scan_timeout, loop=None):
        self.device_name = device_name
        self.serial_number = serial_number
        self.scan_timeout = max(1, scan_timeout)
        self.inputstream = None
        self.write_task = None
        self.client = None
        self.rx_char_handle = None

        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop

    # Helper to await async coroutines
    def _run(self, coro):
        assert coro and self.loop and not self.loop.is_closed()
        return self.loop.run_until_complete(coro)

    async def _connect_impl(self):
        assert self.client is None

        # Input received, buffered awaiting external read
        inbufs = collections.deque()

        # Async stream of those items for reading
        async def _input_stream():
            # Poll for new input all the time client exists
            while self.client is not None:
                while inbufs:
                    buf = inbufs.popleft()
                    for b in buf:
                        yield b

                # No data, yield to event loop awaiting arrival of more data
                await asyncio.sleep(0.01)

            # Stream drained and client connection no longer exists
            self.inputstream = None

        self.inputstream = _input_stream()

        # Scan for expected ble device
        # Match device-name only if no serial number provided
        device_mac = None
        while not device_mac and self.scan_timeout > 0:
            logger.info("Scanning, timeout = {}s".format(self.scan_timeout))
            scan_time = min(2, self.scan_timeout)
            self.scan_timeout -= scan_time

            devices = await bleak.discover(scan_time)
            for dev in devices:
                logger.debug("Seen: {}".format(dev.name))
                if (
                    dev.name
                    and dev.name.startswith(self.device_name)
                    and (
                        self.serial_number is None
                        or dev.name.endswith(self.serial_number)
                    )
                ):
                    # Map pretty name to mac-type address
                    device_mac = dev.address
                    full_name = dev.name

        if not device_mac:
            raise JadeError(
                1,
                "Unable to locate BLE device",
                "Device name: {}, Serial number: {}".format(
                    self.device_name, self.serial_number or "<any>"
                ),
            )

        # Remove previous bt/ble pairing data for this device
        if platform.system() == "Linux":
            command = "bt-device --remove '{}'".format(device_mac)
            process = subprocess.run(command, shell=True, stdout=subprocess.DEVNULL)

        # Connect - seems pretty flaky so allow retries
        connected = False
        attempts_remaining = 3
        while not connected:
            try:
                attempts_remaining -= 1
                client = bleak.BleakClient(device_mac)
                logger.info("Connecting to: {} ({})".format(full_name, device_mac))
                await client.connect()
                connected = client.is_connected
                logger.info("Connected: {}".format(connected))
            except Exception as e:
                logger.warning("BLE connection exception: '{}'".format(e))
                if not attempts_remaining:
                    logger.warning("Exhausted retries - BLE connection failed")
                    raise

        # Peruse services and characteristics
        # Get the 'handle' of the receiving charactersitic
        for service in client.services:
            for char in service.characteristics:
                if char.uuid == JadeBleImpl.IO_RX_CHAR_UUID:
                    logger.debug(
                        "Found RX characterisitic - handle: ".format(char.handle)
                    )
                    self.rx_char_handle = char.handle

                if "read" in char.properties:
                    await client.read_gatt_char(char.uuid)

                for descriptor in char.descriptors:
                    await client.read_gatt_descriptor(descriptor.handle)

        # Attach handler to be notified of new data on the receiving characteristic
        def _notification_handler(char_handle, data):
            assert char_handle == self.rx_char_handle
            inbufs.append(data)

        assert self.rx_char_handle
        await client.start_notify(self.rx_char_handle, _notification_handler)

        # Attach handler called when disconnected
        def _disconnection_handler(client):

            # Set the client to None - that will cause the receive
            # generator to terminate and not wait forever for data.
            assert client == self.client
            self.client = None

            # Also cancel any running task trying to write data,
            # as otherwise that hangs forever too ...
            if self.write_task:
                self.write_task.cancel()
                self.write_task = None

        client.set_disconnected_callback(_disconnection_handler)

        # Done
        self.client = client

    def connect(self):
        return self._run(self._connect_impl())

    async def _disconnect_impl(self):
        try:
            if self.client is not None and self.client.is_connected:
                # Stop listening for incoming data
                if self.rx_char_handle:
                    await self.client.stop_notify(self.rx_char_handle)

                # Disconnect underlying client - this should trigger the _disconnection_handler()
                # above to run before this returns from the 'await'
                await self.client.disconnect()
        except Exception as err:
            # Sometimes get an exception when testing connection
            # if the client has already internally disconnected ...
            logger.warning("Exception when disconnecting ble: {}".format(err))

        # Set the client to None in any case - that will cause the receive
        # generator to terminate and not wait forever for data.
        self.rx_char_handle = None
        self.client = None

    def disconnect(self):
        return self._run(self._disconnect_impl())

    async def _write_impl(self, bytes_):
        assert self.client is not None
        assert self.write_task is None

        towrite = len(bytes_)
        written = 0

        async def _write():
            if self.client is not None:
                nonlocal written

                # Write out in small chunks
                while written < towrite:
                    remaining = towrite - written
                    length = min(remaining, JadeBleImpl.BLE_MAX_WRITE_SIZE)
                    ulimit = written + length
                    await self.client.write_gatt_char(
                        JadeBleImpl.IO_TX_CHAR_UUID,
                        bytearray(bytes_[written:ulimit]),
                        response=True,
                    )

                    written = ulimit

        # Hold on to the write task in case we need to cancel it
        # whie it is running (eg. unexpected disconnection)
        self.write_task = asyncio.create_task(_write())
        try:
            await self.write_task
        except asyncio.CancelledError:
            logger.warning(
                "write() task cancelled having written "
                "{} of {} bytes".format(written, towrite)
            )
        finally:
            self.write_task = None

        return written

    def write(self, bytes_):
        return self._run(self._write_impl(bytes_))

    async def _read_impl(self, n):
        assert self.inputstream is not None
        return bytes([b async for b in aioitertools.islice(self.inputstream, n)])

    def read(self, n):
        return self._run(self._read_impl(n))
