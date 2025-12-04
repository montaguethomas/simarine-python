"""
Simarine Transport
"""

import logging
import queue
import socket
import threading
from typing import Final, Iterator, Optional

import paho.mqtt.client as mqtt

from . import exceptions, protocol


#: Default TCP port used by the Simarine Pico protocol.
#: The Pico device listens for control and data requests on this port.
DEFAULT_TCP_PORT: Final[int] = 5001

#: Default UDP port used by the Simarine Pico protocol.
#: The Pico device transmits broadcast data on this port.
DEFAULT_UDP_PORT: Final[int] = 43210

#: Default MQTT host used by Simarine
DEFAULT_MQTT_HOST: Final[str] = "simarinemqtt.uksouth.cloudapp.azure.com"

#: Default MQTT port used by Simarine
DEFAULT_MQTT_PORT: Final[int] = 1883


class MessageTransport:
  """
  Shared base for Simarine message transports.
  """

  def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
    self._host: str = host
    self._port: int = port
    self._timeout: float = timeout

    self._sock: Optional[socket.socket] = None

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self) -> None:
    raise NotImplementedError

  def close(self) -> None:
    if self._sock:
      self._sock.close()
      self._sock = None
      logging.info(f"Closed socket for {self._host}:{self._port}")

  # --------------------------------------
  # Context Management
  # --------------------------------------

  def __enter__(self) -> "MessageTransport":
    self.open()
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    self.close()


class MessageTransportTCP(MessageTransport):
  """
  Low-level TCP transport for communicating with a Simarine Pico device.
  """

  def __init__(self, host: str, port: int = DEFAULT_TCP_PORT, timeout: float = 5.0) -> None:
    super().__init__(host, port, timeout)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self) -> None:
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

  def __init__(self, port: int = DEFAULT_UDP_PORT, timeout: float = 5.0, host: str = "") -> None:
    super().__init__(host, port, timeout)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self) -> None:
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


class MessageTransportMQTT(MessageTransport):
  """
  MQTT transport for communicating with a Simarine Pico device.
  """

  def __init__(self, serial_number: int, host: str = DEFAULT_MQTT_HOST, port: int = DEFAULT_MQTT_PORT, timeout: float = 5.0) -> None:
    super().__init__(host, port, timeout)

    self._topic_pub = f"/{serial_number}_APP"
    self._topic_sub = f"/{serial_number}_DEV"

    self._client: Optional[mqtt.Client] = None
    self._message_queue: queue.Queue[mqtt.MQTTMessage] = queue.Queue(maxsize=1)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def _message_callback(self, client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
    try:
      self._message_queue.put_nowait(message)
    except queue.Full:
      logging.warning(f"Transport message queue full, dropping message: {message}")

  def open(self) -> None:
    if self._client:
      raise exceptions.TransportAlreadyOpen("Transport already open")

    try:
      client = mqtt.Client(protocol=mqtt.MQTTv311)
      client.connect_timeout = self._timeout
      client.connect(self._host, self._port)
      client.on_message = self._message_callback
      client.subscribe(self._topic_sub)
      client.loop_start()
    except Exception as e:
      logging.exception(f"Failed to connect to {self._host}:{self._port}")
      raise exceptions.TransportOpenError(f"Failed to connect to {self._host}:{self._port}") from e

    self._client = client
    logging.info(f"Connected to {self._host}:{self._port}")

  def close(self) -> None:
    if self._client:
      self._client.loop_stop()
      self._client.disconnect()
      self._client = None
      logging.info(f"Closed connection for {self._host}:{self._port}")

  # --------------------------------------------------
  # Send & Receive
  # --------------------------------------------------

  def request(self, msg_type: protocol.MessageType, payload: bytes) -> protocol.Message:
    """
    Send a single request and wait for a single response.

    This is a simple 'first response wins' strategy: whatever arrives
    next on <serial>_DEV will be used as the response.
    """
    if self._client is None:
      raise RuntimeError("Transport not connected")

    # Clear any stale response
    try:
      while True:
        self._message_queue.get_nowait()
    except queue.Empty:
      pass

    msg = protocol.Message.build(msg_type, payload)
    logging.debug(f"Sending topic={self._topic_pub}: {msg}")

    result = self._client.publish(self._topic_pub, msg.bytes)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
      raise RuntimeError(f"Transport publish failed: rc={result.rc}")

    try:
      message = self._message_queue.get(timeout=self._timeout)
      logging.debug(f"Received topic={self._topic_sub}: {message.payload.hex()}")
    except queue.Empty:
      raise TimeoutError(f"Transport timed out waiting for response on {self._topic_sub}")

    return protocol.Message.from_bytes(message.payload, msg_type)
