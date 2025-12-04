"""
Simarine Client
"""

import logging
import threading
from typing import Callable, Optional

from . import exceptions, protocol, transport
from . import types as simarinetypes


class SimarineClient:
  """
  High-level Simarine client built on MessageTransportTCP.
  """

  def __init__(self, host: str = None, auto_discover: bool = True, **kwargs) -> None:
    kwargs.setdefault("host", host)
    if kwargs.get("host") is None and auto_discover:
      kwargs["host"], _, _ = self.discover()
      if not kwargs.get("host"):
        raise ValueError("Unable to discover Simarine device")

    if not kwargs.get("host"):
      raise ValueError("Host must be provided or auto_discover must be True")

    self._transport = transport.MessageTransportTCP(**kwargs)

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self) -> None:
    self._transport.open()

  def close(self) -> None:
    self._transport.close()

  # --------------------------------------
  # Context Management
  # --------------------------------------

  def __enter__(self) -> "SimarineClient":
    self.open()
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    self.close()

  # --------------------------------------
  # System Information
  # --------------------------------------

  def get_system_info(self) -> tuple[int, str]:
    """
    Requests the system information.

    :return: serial_number, firmware_version
    :rtype: tuple[int, str]
    """
    msg = self._transport.request(protocol.MessageType.SYSTEM_INFO, bytes())
    return msg.fields.get(1).uint32, f"{msg.fields.get(2).int16_hi}.{msg.fields.get(2).int16_lo}"

  def get_system_device(self) -> simarinetypes.Device:
    """
    Requests system device object.

    :return: system_device
    :rtype: Device
    """
    return self.get_device(0)

  # --------------------------------------
  # Device & Sensor Counts
  # --------------------------------------

  def get_counts(self) -> tuple[int, int]:
    """
    Requests the device and sensor counts.

    :return: device_count, sensor_count
    :rtype: tuple[int, int]
    """
    msg = self._transport.request(protocol.MessageType.DEVICE_SENSOR_COUNT, bytes())
    return msg.fields.get(1).value, msg.fields.get(2).value

  # --------------------------------------
  # Devices
  # --------------------------------------

  @staticmethod
  def _device_info_request_payload(idx: int) -> bytes:
    return bytes([0xFF, 0x00, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00])

  def get_device(self, id: int) -> simarinetypes.Device:
    """
    Requests a device object by id.

    :param id: Device ID
    :type id: int
    :return: device
    :rtype: Device
    """
    msg = self._transport.request(protocol.MessageType.DEVICE_INFO, self._device_info_request_payload(id))
    return simarinetypes.DeviceFactory.create(msg.fields)

  def get_devices(self, exclude_system: bool = True) -> dict[int, simarinetypes.Device]:
    """
    Requests all devices.

    :param exclude_system: If to exclude the system device or not.
    :type exclude_system: bool
    :return: devices
    :rtype: dict[int, Device]
    """
    device_count, _ = self.get_counts()
    logging.info(f"Device count: {device_count}")

    devices = {}
    for idx in range(int(exclude_system), device_count + 1):
      device = self.get_device(idx)
      devices[device.id] = device
      logging.info(f"Device index={idx} id={device.id} type={device.type} name={device.name}")

    return devices

  # --------------------------------------
  # Sensors
  # --------------------------------------

  @staticmethod
  def _sensor_info_request_payload(idx: int) -> bytes:
    return bytes([0xFF, 0x01, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00])

  def get_sensor(self, id: int) -> simarinetypes.Sensor:
    """
    Requests a sensor object by id.

    :param id: Sensor ID
    :type id: int
    :return: sensor
    :rtype: Sensor
    """
    msg = self._transport.request(protocol.MessageType.SENSOR_INFO, self._sensor_info_request_payload(id))
    return simarinetypes.SensorFactory.create(msg.fields)

  def get_sensors(self) -> dict[int, simarinetypes.Sensor]:
    """
    Requests all sensors.

    :return: sensors
    :rtype: dict[int, Sensor]
    """
    _, sensor_count = self.get_counts()
    logging.info(
      f"Sensor count: {sensor_count}",
    )

    sensors = {}
    indices = range(0, sensor_count + 1)
    for idx in indices:
      sensor = self.get_sensor(idx)
      sensors[sensor.id] = sensor
      logging.info(
        f"Sensor index={idx} id={sensor.id} type={sensor.type} device_id={sensor.device_id} device_sensor_id={sensor.device_sensor_id}"
      )

    return sensors

  # --------------------------------------
  # Sensors State
  # --------------------------------------

  def get_sensors_state(self) -> dict[int, protocol.MessageFields]:
    msg = self._transport.request(protocol.MessageType.SENSORS_STATE, bytes())
    sensors_state = {}
    for field in msg.fields:
      sensors_state[field.id] = field
    return sensors_state

  def update_sensors_state(self, sensors: dict[int, simarinetypes.Sensor]):
    msg = self._transport.request(protocol.MessageType.SENSORS_STATE, bytes())
    for field in msg.fields:
      if field.id in sensors:
        sensors[field.id].state_field = field

  # --------------------------------------
  # AUTO DISCOVERY
  # --------------------------------------

  @staticmethod
  def discover(**kwargs) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Listen for Simarine UDP broadcasts and extract system information.

    Returns:
      (ip, serial_number, firmware_version)
    """
    logging.info("Discovering Simarine device...")
    with transport.MessageTransportUDP(**kwargs) as udp:
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


class SimarineMQTTClient(SimarineClient):
  """
  High-level Simarine client built on MessageTransportMQTT.
  """

  def __init__(self, **kwargs) -> None:
    self._transport = transport.MessageTransportMQTT(**kwargs)


class SimarineUDPClient(SimarineClient):
  """
  High-level Simarine client built on MessageTransportUDP.
  """

  def __init__(self, handler: Callable[[protocol.Message, tuple[str, int]], None], **kwargs) -> None:
    if not handler or not callable(handler):
      raise ValueError("Handler function must be provided and callable")

    self._handler = handler
    self._transport: transport.MessageTransportUDP = transport.MessageTransportUDP(**kwargs)
    self._thread: Optional[threading.Thread] = None
    self._thread_event: threading.Event = threading.Event()

  # --------------------------------------------------
  # Connection Handling
  # --------------------------------------------------

  def open(self) -> None:
    """
    Start background UDP listener.
    """
    if self._thread and self._thread.is_alive():
      raise exceptions.UDPListenerAlreadyRunning("UDP listener already running")

    self._thread_event.clear()
    self._transport.open()

    def loop():
      for msg, addr in self._transport.listen(stop_event=self._thread_event):
        try:
          self._handler(msg, addr)
        except Exception:
          logging.exception("UDP handler error")

    self._thread = threading.Thread(target=loop, daemon=True, name="simarine-udp-listener")
    self._thread.start()
    logging.info("UDP listener started")

  def close(self) -> None:
    if self._thread:
      self._thread_event.set()
      self._thread.join()
      self._thread = None
      self._transport.close()
      logging.info("UDP listener stopped")
