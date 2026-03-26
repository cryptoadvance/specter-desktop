import socket
import logging


logger = logging.getLogger(__name__)


#
# Low-level Serial-via-TCP backend interface to Jade
# Calls to send and receive bytes over the interface.
# Intended for use via JadeInterface wrapper.
#
# Either:
#  a) use via JadeInterface.create_serial() (see JadeInterface)
# (recommended)
# or:
#  b) use JadeTCPImpl() directly, and call connect() before
#     using, and disconnect() when finished,
# (caveat cranium)
#
class JadeTCPImpl:
    PROTOCOL_PREFIX = "tcp:"

    @classmethod
    def isSupportedDevice(cls, device):
        return device is not None and device.startswith(cls.PROTOCOL_PREFIX)

    def __init__(self, device, timeout):
        assert self.isSupportedDevice(device)
        self.device = device
        self.timeout = timeout
        self.tcp_sock = None

    def connect(self):
        assert self.isSupportedDevice(self.device)
        assert self.tcp_sock is None

        logger.info("Connecting to {}".format(self.device))
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.settimeout(self.timeout)

        try:
            url = self.device[len(self.PROTOCOL_PREFIX):].split(":")
            if len(url) != 2:
                raise ValueError(f"Invalid device format: {self.device}. Expected tcp:host:port")
            host, port_str = url
            port = int(port_str)
            self.tcp_sock.connect((host, port))
            self.tcp_sock.__enter__()
            logger.info("Connected")
        except (socket.timeout, socket.error, OSError, ValueError) as e:
            logger.error(f"Failed to connect to Jade TCP: {e}")
            if self.tcp_sock is not None:
                try:
                    self.tcp_sock.__exit__(None, None, None)
                except Exception:
                    pass
                self.tcp_sock = None
            raise
        assert self.tcp_sock is not None

    def disconnect(self):
        assert self.tcp_sock is not None
        try:
            self.tcp_sock.__exit__(None, None, None)
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        
        # Reset state
        self.tcp_sock = None

    def write(self, bytes_):
        assert self.tcp_sock is not None
        return self.tcp_sock.send(bytes_)

    def read(self, n):
        assert self.tcp_sock is not None
        buf = self.tcp_sock.recv(n)
        while len(buf) < n:
            buf += self.tcp_sock.recv(n - len(buf))
        return buf
