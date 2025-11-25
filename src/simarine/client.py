import logging
from typing import Dict, Optional

from . import protocol, transport
from . import types as simarinetypes


class SimarineClient:
  """
  High-level Pico client built on SimarineTransport.
  """

  def __init__(self, host: str, port: int = transport.DEFAULT_TCP_PORT):
    self.transport = transport.MessageTransportTCP(host, port)

  def __enter__(self):
    self.transport.connect()
    return self

  def __exit__(self, exc_type, exc, tb):
    self.transport.close()

  # --------------------------------------
  # Device & Sensor Counts
  # --------------------------------------

  def get_counts(self) -> tuple[Optional[int], Optional[int]]:
    payload = self.transport.request(protocol.MessageType.DEVICE_SENSOR_COUNT, bytes())
    fields = protocol.MessageFields(payload)
    return fields.get(1).value, fields.get(2).value

  # --------------------------------------
  # Devices
  # --------------------------------------

  @classmethod
  def _device_info_request_payload(cls, idx: int) -> bytes:
    return bytes([0x00, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x01, 0x03, 0x00, 0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xFF])

  def get_devices(self) -> Dict[int, simarinetypes.Device]:
    device_count, _ = self.get_counts()
    logging.info("Device count: %s", device_count)

    devices = {}
    indices = range(0, device_count + 1)
    for idx in indices:
      payload = self.transport.request(protocol.MessageType.DEVICE_INFO, self._device_info_request_payload(idx))

      fields = protocol.MessageFields(payload)
      device = simarinetypes.DeviceFactory.create(fields)

      devices[idx] = device
      logging.info("Device index=%d id=%s type=%s name=%s", idx, device.id, device.type, device.name)

    return devices

  # --------------------------------------
  # Sensors
  # --------------------------------------

  @classmethod
  def _sensor_info_request_payload(cls, idx: int) -> bytes:
    return bytes([0x01, 0x01, 0x00, 0x00, 0x00, idx, 0xFF, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0xFF])

  def get_sensors(self) -> Dict[int, simarinetypes.Sensor]:
    _, sensor_count = self.get_counts()
    logging.info("Sensor count: %s", sensor_count)

    sensors = {}
    indices = range(0, sensor_count + 1)
    for idx in indices:
      payload = self.transport.request(protocol.MessageType.SENSOR_INFO, self._sensor_info_request_payload(idx))

      fields = protocol.MessageFields(payload)
      sensor = simarinetypes.SensorFactory.create(fields)

      sensors[idx] = sensor
      logging.info("Sensor index=%d id=%s type=%s", idx, sensor.id, sensor.type)

    return sensors

  # --------------------------------------
  # Update Sensors State
  # --------------------------------------

  def update_sensors_state(self, sensors: Dict[int, simarinetypes.Sensor]):
    payload = self.transport.request(protocol.MessageType.SENSORS_STATE, bytes())
    for field in protocol.MessageFields(payload):
      if field.id in sensors:
        sensors[field.id].state_field = field
