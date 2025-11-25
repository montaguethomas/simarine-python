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

    self._crc_func = crcmod.mkCrcFun(
      0x11189,
      initCrc=0x0000,
      rev=False,
      xorOut=0x0000,
    )
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

  # --------------------------------------
  # Context Management
  # --------------------------------------

  def __enter__(self):
    self.open()
    return self

  def __exit__(self, exc_type, exc, tb):
    self.close()

  # --------------------------------------------------
  # Parsing
  # --------------------------------------------------

  def _parse_message(self, response: bytes, expected_type: Optional[protocol.MessageType] = None) -> tuple[protocol.MessageType, bytes]:
    if len(response) < protocol.MESSAGE_HEADER_SIZE:
      raise exceptions.InvalidHeaderLength(f"Response too short: {len(response)} < {protocol.MESSAGE_HEADER_SIZE}")

    if response[:6] != b"\x00\x00\x00\x00\x00\xff":
      raise exceptions.InvalidHeaderPrefix(f"Invalid header prefix: {response[:6].hex()}")

    if response[13] != 0xFF:
      raise exceptions.InvalidHeaderTerminator(f"Invalid header terminator byte: {response[13]:#04x}")

    msg_type = protocol.MessageType(response[6])

    if expected_type and msg_type != expected_type:
      raise exceptions.MessageTypeMismatch(f"Expected {expected_type.name} ({expected_type:#04x}), got {msg_type.name} ({msg_type:#04x})")

    expected_length = int.from_bytes(response[11:13], "big")
    msg_length = len(response) - protocol.MESSAGE_HEADER_SIZE + 1

    if expected_length != msg_length:
      raise exceptions.InvalidPayloadLength(f"Length mismatch: expected={expected_length}, got={msg_length}")

    expected_crc = response[-2:]
    msg_crc = self._crc_func(response[1:-3]).to_bytes(2, "big")

    if expected_crc != msg_crc:
      raise exceptions.CRCMismatch(f"CRC mismatch: expected={expected_crc.hex()}, got={msg_crc.hex()}")

    payload = response[protocol.MESSAGE_HEADER_SIZE : -2]
    return msg_type, payload


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

  def request(self, msg_type: protocol.MessageType, payload: bytes, bufsize: int = 8192) -> tuple[protocol.MessageType, bytes]:
    """
    Send a request and return decoded payload.

    Returns:
      (msg_type, payload_bytes)
    """
    if not self._sock:
      raise RuntimeError("Transport not connected")

    packet = self._build_frame(msg_type, payload)
    logging.debug(f"Sending: {packet.hex()}")
    self._sock.sendall(packet)

    response = self._sock.recv(bufsize)
    logging.debug(f"Received: {response.hex()}")

    return self._parse_message(response, msg_type)

  # --------------------------------------------------
  # Framing & Parsing
  # --------------------------------------------------

  def _build_frame(self, msg_type: protocol.MessageType, payload: bytes) -> bytes:
    length_bytes = (len(payload) + 3).to_bytes(2, "big")

    frame = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, msg_type, 0x00, 0x00, 0x00, 0x00, length_bytes[0], length_bytes[1], 0xFF])
    frame.extend(payload)

    crc = self._crc_func(frame[1:-1])
    frame.extend(crc.to_bytes(2, "big"))

    return bytes(frame)


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

  def recv(self, bufsize: int = 8192) -> tuple[protocol.MessageType, bytes, tuple[str, int]]:
    """
    Receive one UDP broadcast packet.

    Returns:
      (msg_type, payload_bytes, (source_ip, source_port))
    """
    if not self._sock:
      raise RuntimeError("Transport not open")

    data, addr = self._sock.recvfrom(bufsize)
    logging.debug(f"Received UDP from {addr[0]}:{addr[1]}: {data.hex()}")

    msg_type, payload = self._parse_message(data)
    return msg_type, payload, addr

  def listen(
    self, bufsize: int = 8192, stop_event: Optional[threading.Event] = None
  ) -> Iterator[tuple[protocol.MessageType, bytes, tuple[str, int]]]:
    """
    Continuously yield received UDP packets.

    Yields:
      (msg_type, payload_bytes, (source_ip, source_port))
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
