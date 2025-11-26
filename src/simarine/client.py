import logging
import threading
from typing import Callable, Optional

from . import exceptions, protocol, transport
from . import types as simarinetypes


class SimarineClient:
  """
  High-level Simarine client built on SimarineTransport.

  Supports:
    - TCP control
    - UDP auto discovery & broadcast listening
  """

  def __init__(
    self,
    host: Optional[str] = None,
    tcp_kwargs: Optional[dict] = None,
    udp_kwargs: Optional[dict] = None,
    auto_discover: bool = True,
  ):
    tcp_kwargs = tcp_kwargs or {}
    tcp_kwargs.setdefault("host", host)
    udp_kwargs = udp_kwargs or {}

    if not tcp_kwargs.get("host") and auto_discover:
      tcp_kwargs["host"], _, _ = self.discover(udp_kwargs)
      if not tcp_kwargs.get("host"):
        raise ValueError("Unable to discover Simarine device via UDP broadcast")

    if not tcp_kwargs.get("host"):
      raise ValueError("Host must be provided or auto_discover must be True")

    self._tcp = transport.MessageTransportTCP(**tcp_kwargs)
    self._udp = transport.MessageTransportUDP(**udp_kwargs)
    self._udp_thread: Optional[threading.Thread] = None
    self._udp_stop = threading.Event()

  # --------------------------------------
  # Context Management
  # --------------------------------------

  def __enter__(self):
    self._tcp.open()
    return self

  def __exit__(self, exc_type, exc, tb):
    self._tcp.close()
    self.stop_udp_listener()

  # --------------------------------------
  # System Information
  # --------------------------------------

  def get_system_info(self) -> tuple[int, str]:
    msg = self._tcp.request(protocol.MessageType.SYSTEM_INFO, bytes())
    return msg.fields.get(1).uint32, f"{msg.fields.get(2).int16_hi}.{msg.fields.get(2).int16_lo}"

  # --------------------------------------
  # Device & Sensor Counts
  # --------------------------------------

  def get_counts(self) -> tuple[int, int]:
    msg = self._tcp.request(protocol.MessageType.DEVICE_SENSOR_COUNT, bytes())
    return msg.fields.get(1).value, msg.fields.get(2).value

  # --------------------------------------
  # Devices
  # --------------------------------------

  @staticmethod
  def _device_info_request_payload(idx: int) -> bytes:
    return bytes([0x00, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xFF])

  def get_device(self, id: int) -> simarinetypes.Device:
    msg = self._tcp.request(protocol.MessageType.DEVICE_INFO, self._device_info_request_payload(id))
    return simarinetypes.DeviceFactory.create(msg.fields)

  def get_devices(self) -> dict[int, simarinetypes.Device]:
    device_count, _ = self.get_counts()
    logging.info("Device count: %s", device_count)

    devices = {}
    indices = range(0, device_count + 1)
    for idx in indices:
      device = self.get_device(idx)
      devices[idx] = device
      logging.info("Device index=%d id=%s type=%s name=%s", idx, device.id, device.type, device.name)

    return devices

  # --------------------------------------
  # Sensors
  # --------------------------------------

  @staticmethod
  def _sensor_info_request_payload(idx: int) -> bytes:
    return bytes([0x01, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0xFF])

  def get_sensor(self, id: int) -> simarinetypes.Sensor:
    msg = self._tcp.request(protocol.MessageType.SENSOR_INFO, self._sensor_info_request_payload(id))
    return simarinetypes.SensorFactory.create(msg.fields)

  def get_sensors(self) -> dict[int, simarinetypes.Sensor]:
    _, sensor_count = self.get_counts()
    logging.info("Sensor count: %s", sensor_count)

    sensors = {}
    indices = range(0, sensor_count + 1)
    for idx in indices:
      sensor = self.get_sensor(idx)
      sensors[idx] = sensor
      logging.info("Sensor index=%d id=%s type=%s", idx, sensor.id, sensor.type)

    return sensors

  # --------------------------------------
  # Update Sensors State
  # --------------------------------------

  def update_sensors_state(self, sensors: dict[int, simarinetypes.Sensor]):
    msg = self._tcp.request(protocol.MessageType.SENSORS_STATE, bytes())
    for field in msg.fields:
      if field.id in sensors:
        sensors[field.id].state_field = field

  # --------------------------------------
  # UDP LISTENING
  # --------------------------------------

  def start_udp_listener(self, handler: Callable[[protocol.Message, tuple[str, int]], None]):
    """
    Start background UDP listener.

    handler(msg_type, payload, source_addr)
    """
    if self._udp_thread and self._udp_thread.is_alive():
      raise exceptions.UDPListenerAlreadyRunning("UDP listener already running")

    self._udp_stop.clear()
    self._udp.open()

    def loop():
      for msg, addr in self._udp.listen(stop_event=self._udp_stop):
        try:
          handler(msg, addr)
        except Exception:
          logging.exception("UDP handler error")

    self._udp_thread = threading.Thread(target=loop, daemon=True, name="simarine-udp-listener")
    self._udp_thread.start()
    logging.info("UDP listener started")

  def stop_udp_listener(self):
    if self._udp_thread:
      self._udp_stop.set()
      self._udp_thread.join()
      self._udp_thread = None
      self._udp.close()
      logging.info("UDP listener stopped")

  # --------------------------------------
  # AUTO DISCOVERY
  # --------------------------------------

  @staticmethod
  def discover(udp_kwargs: Optional[dict] = None) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Listen for Simarine UDP broadcasts and extract system information.

    Returns:
      (ip, serial_number, firmware_version)
    """
    logging.info("Discovering Simarine device...")
    udp_kwargs = udp_kwargs or {}
    with transport.MessageTransportUDP(**udp_kwargs) as udp:
      try:
        _, addr = udp.recv()
      except TimeoutError:
        logging.info("Discovery timed out")
        return None, None, None
      except Exception:
        logging.exception("Discovery failed")
        return None, None, None

    logging.info(f"Found device at {addr[0]}:{addr[1]}, probing system information...")
    with SimarineClient(addr[0], auto_discover=False) as client:
      try:
        serial_number, firmware_version = client.get_system_info()
      except Exception:
        logging.exception("Failed to probe system information")
        return addr[0], None, None

    logging.info(f"Simarine device: ip={addr[0]} serial={serial_number}, firmware={firmware_version}")
    return addr[0], serial_number, firmware_version
