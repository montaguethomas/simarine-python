import crcmod
import logging
import socket
from typing import Optional

from . import exceptions, protocol


#: Default TCP port used by the Simarine Pico protocol.
#: The Pico device listens for control and data requests on this port.
DEFAULT_TCP_PORT = 5001

#: Default UDP port used by the Simarine Pico protocol.
#: The Pico device transmits announcement data on this multicast group.
DEFAULT_UDP_PORT = 43210


class MessageTransport:
  """
  Low-level transport for communicating with a Simarine Pico device.

  Handles:
    - TCP connection
    - Message framing and CRC
    - Validation
    - Payload extraction
  """

  def __init__(self, host: str, port: int = DEFAULT_TCP_PORT, timeout: float = 5.0):
    self.host = host
    self.port = port
    self.timeout = timeout
    self.sock: Optional[socket.socket] = None

    self._crc_func = crcmod.mkCrcFun(
      0x11189,
      initCrc=0x0000,
      rev=False,
      xorOut=0x0000,
    )

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def connect(self):
    if self.sock:
      return

    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.settimeout(self.timeout)
    self.sock.connect((self.host, self.port))
    logging.info(f"Connected to Pico @ {self.host}:{self.port}")

  def close(self):
    if self.sock:
      self.sock.close()
      self.sock = None

  def __enter__(self):
    self.connect()
    return self

  def __exit__(self, exc_type, exc, tb):
    self.close()

  # --------------------------------------------------
  # Send & Receive
  # --------------------------------------------------

  def request(self, msg_type: protocol.MessageType, payload: bytes) -> bytes:
    """
    Send a request and return decoded payload.
    """
    if not self.sock:
      raise RuntimeError("Transport not connected")

    packet = self._build_frame(msg_type, payload)
    logging.debug("Sending: %s", packet.hex(" "))
    self.sock.sendall(packet)

    response = self.sock.recv(4096)
    logging.debug("Received: %s", response.hex(" "))

    return self._parse_response(msg_type, response)

  # --------------------------------------------------
  # Framing & Validation
  # --------------------------------------------------

  def _build_frame(self, msg_type: protocol.MessageType, payload: bytes) -> bytes:
    length_bytes = (len(payload) + 3).to_bytes(2, "big")

    frame = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, msg_type, 0x00, 0x00, 0x00, 0x00, length_bytes[0], length_bytes[1], 0xFF])
    frame.extend(payload)

    crc = self._crc_func(frame[1:-1])
    frame.extend(crc.to_bytes(2, "big"))

    return bytes(frame)

  def _parse_response(self, type_expected: protocol.MessageType, response: bytes) -> bytes:
    if len(response) < protocol.MESSAGE_HEADER_SIZE:
      raise exceptions.InvalidHeaderLength(f"Response too short: {len(response)} < {protocol.MESSAGE_HEADER_SIZE}")

    if response[:6] != b"\x00\x00\x00\x00\x00\xff":
      raise exceptions.InvalidHeaderPrefix(f"Invalid header prefix: {response[:6].hex()}")

    if response[13] != 0xFF:
      raise exceptions.InvalidHeaderTerminator(f"Invalid header terminator byte: 0x{response[13]:02x}")

    type = protocol.MessageType(response[6])
    if type != type_expected:
      raise exceptions.MessageTypeMismatch(f"Expected {type_expected.name} ({type_expected:#x}), got {type.name} ({type:#x})")

    length = int.from_bytes(response[11:13], "big")
    length_expected = len(response) - protocol.MESSAGE_HEADER_SIZE + 1
    if length != length_expected:
      raise exceptions.InvalidPayloadLength(f"Length mismatch: header={length}, actual={length_expected}")

    crc = response[-2:]
    crc_expected = self._crc_func(response[1:-3]).to_bytes(2, "big")
    if crc_expected != crc:
      raise exceptions.CRCMismatch(f"CRC mismatch: expected={crc_expected.hex()}, got={crc.hex()}")

    return response[protocol.MESSAGE_HEADER_SIZE : -2]
