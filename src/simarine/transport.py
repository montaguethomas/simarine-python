import crcmod
import logging
import socket
import threading
from typing import Iterator, Optional

from . import exceptions, protocol


#: Default TCP port used by the Simarine Pico protocol.
#: The Pico device listens for control and data requests on this port.
DEFAULT_TCP_PORT = 5001

#: Default UDP port used by the Simarine Pico protocol.
#: The Pico device transmits broadcast data on this port.
DEFAULT_UDP_PORT = 43210


class MessageTransport:
  """
  Shared base for Simarine message transports.

  Handles:
    - CRC calculation
    - Frame validation
    - Payload extraction
  """

  def __init__(self, host: str, port: int, timeout: float = 5.0):
    self._host = host
    self._port = port
    self._timeout = timeout

    self._sock: Optional[socket.socket] = None

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self):
    raise NotImplementedError

  def close(self):
    if self._sock:
      self._sock.close()
      self._sock = None
      logging.info(f"Closed socket for {self._host}:{self._port}")

  # --------------------------------------
  # Context Management
  # --------------------------------------

  def __enter__(self):
    self.open()
    return self

  def __exit__(self, exc_type, exc, tb):
    self.close()


class MessageTransportTCP(MessageTransport):
  """
  Low-level TCP transport for communicating with a Simarine Pico device.

  Handles:
    - TCP connection
    - Message framing and CRC
    - Validation
    - Payload extraction
  """

  def __init__(self, host: str, port: int = DEFAULT_TCP_PORT, timeout: float = 5.0):
    super().__init__(host, port, timeout)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self):
    if self._sock:
      raise exceptions.TransportAlreadyOpen("Transport already open")

    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(self._timeout)
      sock.connect((self._host, self._port))
    except Exception as e:
      logging.exception(f"Failed to connect to {self._host}:{self._port}")
      raise exceptions.TransportOpenError(f"Failed to connect to {self._host}:{self._port}") from e

    self._sock = sock
    logging.info(f"Connected to {self._host}:{self._port}")

  # --------------------------------------------------
  # Send & Receive
  # --------------------------------------------------

  def request(self, msg_type: protocol.MessageType, payload: bytes, bufsize: int = 8192) -> protocol.Message:
    """
    Send a request and return decoded payload.

    Returns:
      Message
    """
    if not self._sock:
      raise RuntimeError("Transport not connected")

    msg = protocol.Message.build(msg_type, payload)
    logging.debug(f"Sending: {msg}")
    self._sock.sendall(msg.bytes)

    received = self._sock.recv(bufsize)
    logging.debug(f"Received: {received.hex()}")

    return protocol.Message.from_bytes(received, msg_type)


class MessageTransportUDP(MessageTransport):
  """
  Low-level UDP transport for Simarine Pico broadcast traffic.
  """

  def __init__(self, port: int = DEFAULT_UDP_PORT, timeout: float = 5.0, host: str = ""):
    super().__init__(host, port, timeout)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self):
    if self._sock:
      raise exceptions.TransportAlreadyOpen("Transport already open")

    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
      sock.settimeout(self._timeout)
      sock.bind((self._host, self._port))
    except Exception as e:
      logging.exception(f"Failed to bind to {self._host}:{self._port}")
      raise exceptions.TransportOpenError(f"Failed to bind to {self._host}:{self._port}") from e

    self._sock = sock
    logging.info(f"Listening for Simarine UDP broadcasts on {self._host}:{self._port}")

  # --------------------------------------------------
  # Receiving
  # --------------------------------------------------

  def recv(self, bufsize: int = 8192) -> tuple[protocol.Message, tuple[str, int]]:
    """
    Receive one UDP broadcast packet.

    Returns:
      (Message, (source_ip, source_port))
    """
    if not self._sock:
      raise RuntimeError("Transport not open")

    received, addr = self._sock.recvfrom(bufsize)
    logging.debug(f"Received UDP from {addr[0]}:{addr[1]}: {received.hex()}")

    return protocol.Message.from_bytes(received), addr

  def listen(self, bufsize: int = 8192, stop_event: Optional[threading.Event] = None) -> Iterator[tuple[protocol.Message, tuple[str, int]]]:
    """
    Continuously yield received UDP packets.

    Yields:
      (Message, (source_ip, source_port))
    """
    while True:
      if not self._sock:
        return
      if stop_event and stop_event.is_set():
        return

      try:
        yield self.recv(bufsize)
      except (socket.timeout, TimeoutError):
        continue
      except OSError:
        return
