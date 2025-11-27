import re
from datetime import datetime
from enum import Enum
from typing import Callable, Dict, Any, Type

from . import protocol


# --------------------------------------------------
# Simarine Field Descriptor
# --------------------------------------------------


class SimarineField:
  def __init__(self, id: int, attr: str = "value", default: Any = None, scale: float = None, transform: Callable = None):
    self.id = id
    self.attr = attr
    self.default = default
    self.scale = scale
    self.transform = transform

  def __get__(self, instance, owner):
    if instance is None:
      return self

    field = self._get_field(instance, owner)
    if not field:
      return self.default

    value = getattr(field, self.attr)
    if value is None:
      return self.default

    if self.scale:
      value = value * self.scale

    if self.transform:
      return self.transform(value)

    return value

  def _get_field(self, instance, owner):
    return getattr(instance, "fields", {}).get(self.id)


class SimarineFieldTimestamp(SimarineField):
  def __init__(self, id: int, transform: Callable = datetime.fromtimestamp):
    super().__init__(id, "timestamp", None, None, transform)


class SimarineState(SimarineField):
  def __init__(self, default: Any = None, scale: float = None, transform: Callable = None):
    super().__init__(0, "value", default, scale, transform)

  def _get_field(self, instance, owner):
    return getattr(instance, "state_field", None)


# --------------------------------------------------
# Simarine Object
# --------------------------------------------------


# Create a synthetic enum instance for unknown values
class UnknownEnum(Enum):
  @classmethod
  def _missing_(cls, value):
    new = object.__new__(cls)
    new._name_ = f"UNKNOWN_{value}"
    new._value_ = value
    return new


class OnOffType(Enum):
  ON = 1
  OFF = 2


class SimarineObject:
  def __init__(self, fields: protocol.MessageFields):
    self.fields = fields

  @property
  def type(self) -> str:
    cls_name = self.__class__.__name__
    if cls_name == type(self).__mro__[-3].__name__:
      return "unknown"
    return re.sub(r"([a-z])([A-Z])", r"\1_\2", cls_name.removesuffix(type(self).__mro__[-3].__name__)).lower()


# --------------------------------------------------
# Simarine Device
# --------------------------------------------------


class Device(SimarineObject):
  id = SimarineField(0)
  created = SimarineFieldTimestamp(1)
  type_id = SimarineField(1)
  name = SimarineField(3)

  def __repr__(self):
    return f"<{self.__class__.__name__} id={self.id} name={self.name}>"

  def to_dict(self):
    out = {
      "id": self.id,
      "type": self.type,
      "type_id": self.type_id,
      "name": self.name,
    }
    for attr, value in self.__class__.__dict__.items():
      if isinstance(value, SimarineField):
        out[attr] = getattr(self, attr)
    out["fields"] = self.fields.as_dict()
    return out


class DeviceFactory:
  _registry: Dict[int, Type[Device]] = {}

  @classmethod
  def auto_register(cls):
    if cls._registry:
      return
    for subclass in Device.__subclasses__():
      if subclass.type_id is not None:
        cls._registry[subclass.type_id] = subclass

  @classmethod
  def create(cls, fields: protocol.MessageFields) -> Device:
    cls.auto_register()
    type_id = Device(fields).type_id
    device_cls = cls._registry.get(type_id, Device)
    return device_cls(fields)


# --------------------------------------------------
# Simarine Device Types
# --------------------------------------------------


class BatteryType(UnknownEnum):
  WEB_LOW_MAINTENANCE = 1
  WET_MAINTENANCE_FREE = 2
  AGM = 3
  DEEP_CYCLE = 4
  GEL = 5
  LIFEPO4 = 6


class InclinometerType(UnknownEnum):
  PITCH = 1
  ROLL = 2


class InclinometerDisplayType(UnknownEnum):
  LINE = 1
  CARAVAN = 2


class TankFluidType(UnknownEnum):
  WATER = 1
  FUEL = 2
  WASTE_WATER = 3


class ThermometerType(UnknownEnum):
  NTC_10K = 1
  NTC_5K = 2
  NTC_1K = 3
  VDO = 4


class NullDevice(Device):
  type_id = 0


class VoltmeterDevice(Device):
  type_id = 1

  parent_device_id_updated = SimarineFieldTimestamp(6)
  parent_device_id = SimarineField(6)  # 255 == unassigned


class AmperemeterDevice(Device):
  type_id = 2


class ThermometerDevice(Device):
  type_id = 3

  ntc_type_updated = SimarineFieldTimestamp(6)
  ntc_type = SimarineField(6, transform=ThermometerType)

  priority_updated = SimarineFieldTimestamp(9)
  priority = SimarineField(9)


class BarometerDevice(Device):
  type_id = 5


class OhmmeterDevice(Device):
  type_id = 6

  parent_device_id_updated = SimarineFieldTimestamp(7)
  parent_device_id = SimarineField(7)  # 255 == unassigned


class TimeDevice(Device):
  type_id = 7


class TankDevice(Device):
  type_id = 8

  fluid_type_updated = SimarineFieldTimestamp(6)
  fluid_type = SimarineField(6, transform=TankFluidType)
  # sensor_type = SimarineField(?, transform=lambda v: {?: "resistive", ?: "voltage", ?: "4_stage_level"}.get(v, "unknown"))
  # sensor_id = SimarineField(???)
  capacity_updated = SimarineFieldTimestamp(6)
  capacity = SimarineField(7, scale=0.1)


class BatteryDevice(Device):
  type_id = 9

  voltmeter_device_id = SimarineField(4)
  capacity_c20_updated = SimarineFieldTimestamp(5)
  capacity_c20 = SimarineField(5, scale=0.01)
  capacity_c10_updated = SimarineFieldTimestamp(6)
  capacity_c10 = SimarineField(6, scale=0.01)
  capacity_c5_updated = SimarineFieldTimestamp(7)
  capacity_c5 = SimarineField(7, scale=0.01)
  battery_type_updated = SimarineFieldTimestamp(8)
  battery_type = SimarineField(8, transform=BatteryType)
  temperature_device_id_updated = SimarineFieldTimestamp(10)
  temperature_device_id = SimarineField(10)


class SystemDevice(Device):
  type_id = 10

  # System device fields:
  # field 3 has serial number in uint32
  # field 9 timestamp (a_uint32) keeps updating each request, while value (b_uint32) doesn't change
  #
  serial_number = SimarineField(3)
  system_datetime = SimarineFieldTimestamp(9)
  wifi_ssid = SimarineField(10)
  tcp_port = SimarineField(12)
  udp_port = SimarineField(14)
  wifi_pass = SimarineField(15)


class InclinometerDevice(Device):
  type_id = 13

  name_updated = SimarineFieldTimestamp(3)
  name = SimarineField(3, transform=InclinometerType)
  axis = SimarineField(3, transform=InclinometerType)

  nonlinear_updated = SimarineFieldTimestamp(6)
  nonlinear = SimarineField(6, transform=OnOffType)

  display_type_updated = SimarineFieldTimestamp(7)
  display_type = SimarineField(7, transform=InclinometerDisplayType)

  reverse_updated = SimarineFieldTimestamp(9)
  reverse = SimarineField(9, transform=OnOffType)

  display_updated = SimarineFieldTimestamp(10)
  display = SimarineField(10, transform=OnOffType)


# --------------------------------------------------
# Simarine Sensor
# --------------------------------------------------


class Sensor(SimarineObject):
  state_field: protocol.MessageFields = None

  id = SimarineField(1)
  type_id = SimarineField(2)
  device_id = SimarineField(3)
  device_sensor_id = SimarineField(4)

  def __repr__(self):
    return f"<{self.__class__.__name__} id={self.id} device_id={self.device_id} device_sensor_id={self.device_sensor_id} state_field={self.state_field}>"

  def to_dict(self):
    out = {
      "id": self.id,
      "type": self.type,
      "type_id": self.type_id,
      "device_id": self.device_id,
      "device_sensor_id": self.device_sensor_id,
    }
    for attr, value in self.__class__.__dict__.items():
      if isinstance(value, SimarineField):
        out[attr] = getattr(self, attr)
      if isinstance(value, SimarineState):
        out[attr] = getattr(self, attr)
    out["fields"] = self.fields.as_dict()
    out["state_field"] = self.state_field
    return out


class SensorFactory:
  _registry: Dict[int, Type[Device]] = {}

  @classmethod
  def auto_register(cls):
    if cls._registry:
      return
    for subclass in Sensor.__subclasses__():
      if subclass.type_id is not None:
        cls._registry[subclass.type_id] = subclass

  @classmethod
  def create(cls, fields: protocol.MessageFields) -> Sensor:
    cls.auto_register()
    type_id = Sensor(fields).type_id
    sensor_cls = cls._registry.get(type_id, Sensor)
    return sensor_cls(fields)


# --------------------------------------------------
# Simarine Sensor Types
# --------------------------------------------------


class TimestampStateType(UnknownEnum):
  LOCALTIME = 0
  """System time, timezone adjusted. This is what's displayed."""

  UTC = 1
  """
  System time, UTC/GMT ... but invalid!

  Have found the value to be reverse adjusted (e.g. GMT-5, 1500 -> 1000 vs 2000).
  Pico Firmware v1.21
  """

  BOOT_TIME = 2
  """Boot time, timezone adjusted."""


class NoneSensor(Sensor):
  type_id = 0


class VoltageSensor(Sensor):
  type_id = 1
  unit = "volts"
  volts = SimarineState(scale=0.001)


class CurrentSensor(Sensor):
  type_id = 2
  unit = "amps"
  amps = SimarineState(scale=0.01)


class CoulombCounterSensor(Sensor):
  type_id = 3
  unit = "amp_hours"
  amp_hours = SimarineState(scale=0.001)


class TemperatureSensor(Sensor):
  type_id = 4
  unit = "celsius"
  celsius = SimarineState(scale=0.1)


class AtmosphereSensor(Sensor):
  type_id = 5
  unit = "millibars"
  millibars = SimarineState(scale=0.01)


class AtmosphereTrendSensor(Sensor):
  type_id = 6
  unit = "millibars_per_hour"
  millibars_per_hour = SimarineState(scale=0.1)


class ResistanceSensor(Sensor):
  type_id = 7
  unit = "ohms"
  ohms = SimarineState()


class TimestampSensor(Sensor):
  type_id = 10
  unit = "unix_timestamp"
  state_type = SimarineField(4, transform=TimestampStateType)

  unix_timestamp = SimarineState()
  datetime = SimarineState(transform=datetime.fromtimestamp)


class AngleSensor(Sensor):
  type_id = 16
  unit = "degrees"
  degrees = SimarineState(scale=0.1)


class UserSensor(Sensor):
  type_id = 22
