import inspect
from enum import IntEnum
from typing import Dict, Optional


#: Size of the Simarine message header in bytes.
#:
#: The header precedes every protocol message and contains sync bytes,
#: message type, source ID, payload length and terminator marker.
#:
#: Example header format::
#:
#:   00 00 00 00 00 FF <type> <source-id:4> <length:2> FF
#:
#: Total size: 14 bytes.
MESSAGE_HEADER_SIZE = 14


class MessageType(IntEnum):
  """
  Simarine Pico TCP & UDP message types.

  These values represent the primary command / response identifiers
  used in the Simarine TCP & UDP protocol.

  Each enum entry documents known request/response patterns and
  field interpretations discovered through packet captures.
  """

  SYSTEM_INFO = 0x01
  """
  Request system information.

  Request:
      0000000000 ff 01 00000000 0003 ff 89b8

  Response:
      0000000000 ff 01 84b3ee93 0011 ff
      01 01 84b3ee93 ff   -> Device Serial Number (uint32: 84B3EE93)
      02 01 00010015 ff   -> Firmware Version (int16.int16: 0001.0015)
      97a3
  """

  DEVICE_SENSOR_COUNT = 0x02
  """
  Request device and sensor counts.

  Request:
      0000000000 ff 02 00000000 0003 ff 7688

  Response:
      0000000000 ff 02 84b3ee93 0011 ff
      01 01 00000013 ff   -> Device Count
      02 01 0000001a ff   -> Sensor Count
      76e9
  """

  DEVICE_INFO = 0x41
  """
  Request device information for a specific device index.

  Request:
      0000000000 ff 41 00000000 0016 ff 00010000000b ff 010300000000 ff 00000000 ff fe6d

  Response:
      0000000000 ff 41 84b3ee93 005a ff
      00 01 0000000b ff
      01 03 65932547 ff 00000001 ff
      02 01 00000000 ff
      03 04 65932547ff5343353033205b313736355d203100 ff
      04 01 2cb15f45 ff
      05 01 00000001 ff
      06 03 678ef359 ff 00000011 ff
      07 03 00000000 ff 39420bbb ff
      4e7f

  Response contains structured binary fields:
  - Field 0: Device Id
  - Field 1: Device Type
  - Field 3: Device Name
  """

  SENSOR_INFO = 0x20
  """
  Request sensor information for given device index.

  Request:
      0000000000 ff 20 00000000 0011 ff 010100000002 ff 020100000000 ff 74ee

  Response:
      0000000000 ff 20 84b3ee93 008b ff
      01 01 00000002 ff
      02 01 00000005 ff
      03 01 00000005 ff
      04 01 00000000 ff
      05 03 00000000 ff 00000000 ff
      06 03 00000000 ff 32ff1202 ff
      07 03 00000000 ff 012c0014 ff
      08 03 00000000 ff 00000000 ff
      09 03 00000000 ff 32ff1202 ff
      0a 03 00000000 ff 012c0014 ff
      0b 03 00000000 ff 00000002 ff
      0c 03 00000000 ff 00000000 ff
      0d 03 00000000 ff 00000000 ff
      6fd9

  Response provides:
  - Sensor Id
  - Sensor Type
  - Device Id
  """

  SENSORS_STATE = 0xB0
  """
  Request sensors state.

  Request:
      0000000000 ff b0000000000003 ff e237

  Response:
      0000000000 ff b0 84b3ee93 00ab ff
      00 01 691c8a3c ff
      01 01 691c43ea ff
      02 01 fffffc16 ff
      03 01 00018e8f ff
      04 01 fffffc16 ff
      05 01 0000342a ff
      09 01 691c8947 ff
      0a 01 fffffc16 ff
      0b 01 000001dd ff
      0c 01 0008d88b ff
      0d 01 000033f4 ff
      0e 01 00000000 ff
      0f 01 0000ffff ff
      10 01 0000ffff ff
      11 01 00005e64 ff
      12 01 00000039 ff
      13 01 33410062 ff
      14 01 000001dd ff
      15 01 000033f4 ff
      16 01 7fffffff ff
      17 01 000133e4 ff
      18 01 ffffffc9 ff
      19 01 00000035 ff
      1a 01 7fffffff ff
      1ec5

  Response provides:
  - Sensor Id
  - Sensor Value
  """

  UNKNOWN_03 = 0x03
  """
  Unknown type 0x03

  Request:
      0000000000 ff 03 00000000 000a ff 010100000000 ff 24d2

  Response:
      0000000000 ff 03 84b3ee93 000a ff
      01 01 00000001 ff
      b56e
  """

  UNKNOWN_10 = 0x10
  """
  Unknown type 0x10

  Request:
      0000000000 ff 10 00000000 0011 ff
      01 01 691c8a3a ff
      02 01 ffffb9b0 ff
      0301

  Response:
      0000000000 ff aa 84b3ee93 000a ff
      01 01 0000ff10 ff
      85d5
  """

  UNKNOWN_50 = 0x50
  """
  Unknown type 0x50

  Request:
      0000000000 ff 50 00000000 0003 ff 3036

  Response:
      0000000000 ff aa 84b3ee93 000a ff
      01 01 0000ff50 ff
      a1b1
  """

  UNKNOWN_AA = 0xAA
  """
  Unknown type 0xAA

  Request:
      0000000000 ff 10 00000000 0011 ff
      01 01 691c8a3a ff
      02 01 ffffb9b0 ff
      0301

  Response:
      0000000000 ff aa 84b3ee93 000a ff
      01 01 0000ff10 ff
      85d5
  """

  UNKNOWN_C1 = 0xC1
  """
  Unknown type 0xC1 (UDP multicast)

  Multicast Group: 43210

  Appears to broadcast waveform/trend ADC-like data stream.

  Characteristics:
  - High frequency
  - Repeating 16-bit word pairs
  - Likely internal sampling buffer or oscilloscope view
  - Probably intended only for diagnostics or internal UI

  Response: 0000000000 ff c184b3ee930477 ff 000b691c89f0 ff 691c89f0 ff e1ff 560b560a ff 560f5611 ff 560e5609ff560b560fff5611561aff56195621ff5624562aff561e5612ff5619561fff5614560dff5611560cff5606560eff560b5616ff5613560bff560555fdff55f155eaff55db55d4ff55d155d4ff55ce55d2ff55b955a9ff55a05591ff558a5581ff556a556cff5567556eff55695563ff555d5549ff55315525ff551e5516ff5512550cff55075504ff550054fbff54f354f3ff54e854e5ff54df54ceff54be54b1ff54a854a6ff54a0549eff5499549fff549a5491ff54895489ff54865489ff54875477ff546c5462ff54545449ff5443543cff54335426ff541d5416ff5418540fff540453f6ff53e853ddff53ce53c6ff53ba53b3ff53a85399ff53805371ff5362535cff5355534aff533e5333ff5322530fff52f952ddff52d752c5ff52b952aaff52985283ff52695258ff524d523dff522c5221ff520c51f9ff51ec51e0ff51c651b1ff51a651a4ff51a451a6ff51b251adff51aa51b8ff51b351b8ff51bd51b7ff51b551c7ff51bd51c2ff51b151b6ff51af51b2ff51b051b8ff51b751afff51a05194ff518f5189ff518d5186ff5185517cff51745165ff5154514aff5134512bff511c5109ff50ed50dcff50d150bcff50a95095ff50775060ff50465036ff50215015ff5010500dff50015000ff4ff54fe7ff4fdc4fc6ff4fae4fa1ff4f984f89ff4f814f85ff4f804f74ff4f6d4f6aff4f684f63ff4f5d4f57ff4f534f4aff4f444f42ff4f3b4f34ff4f314f31ff4f284f20ff4f204f1aff4f1a4f1bff4f1a4f17ff4f0a4efeff4efd4efcff4ef94ef1ff4eee4eefff4eed4ee7ff4ee74eecff4ee84ee9ff4ee44edfff4ece4ecdff4ebf4eb3ff4ea74e9bff4e9d4e93ff4e874e78ff4e694e51ff4e3d4e30ff4e184dffff4de34dc0ff4da44d8aff4d6a4d60ff4d504d37ff4d1d4d03ff4ceb4cddff4cc54cb4ff4ca24c93ff4c7f4c67ff4c654c46ff4c2d4c17ff4bff4bd9ff4bce4bd4ff4bcf4bbbff4bc94bbeff4be54be9ff4be54be6ff4bd54bceff4bc64bb0ff4ba74bb2ff4bb54bbeff4bbd4bc4ff4bbc4bb4ff4baa4b8cff4b654b72ff4b644b66ff4b574b5aff4b4e4b31ff4b164b00ff4afd4ae4ff4ac74ab1ff4a9d4a84ff4a7f4a69ff4a5a4a46ff4a404a37ff4a2d4a2aff4a244a18ff4a0f49fcff49f049f6ff49f649f3ff49f549ebff49dd49c0ff499f4994ff498d4976ff4971496aff4979499cff49a349a6ff49914999ff4998499aff49a349a2ff49bb49d1ff49e249f1ff49f549e8ff49fc4a03ff4a0b4a23ff4a354a59ff4a624a7cff4a894aa0ff4abb4ad8ff4ae74aecff4b024b1fff4b504b70ff4b994babff4bb24bb0ff4bd24bdfff4be94c0eff4c264c29ff4c3d4c62ff4c6e4c7bff4c904cb9ff4ce24cf7ff4d084d13ff4d184d06ff4d1e4d36ff4d3c4d3dff4d4d4d68ff4d914db0ff4dcd4ddfff4e0d4e18ff4e2d4e37ff4e4a4e51ff4e674e87ff4e9e4eaaff4ec54ed1ff4ed84ee4ff4eff4f1fff4f394f4cff4f6d4f8dff4fb54fccff4fd34ffaff4ff85026ff50445056ff507f5076ff5083509dff50a750b0ff50cb50e7ffff026c
  Response: 0000000000 ff c184b3ee930477 ff 000b691c89f0 ff 691c89f0 ff e1ff 560b560a ff 560f5611 ff 560e5609ff560b560fff5611561aff56195621ff5624562aff561e5612ff5619561fff5614560dff5611560cff5606560eff560b5616ff5613560bff560555fdff55f155eaff55db55d4ff55d155d4ff55ce55d2ff55b955a9ff55a05591ff558a5581ff556a556cff5567556eff55695563ff555d5549ff55315525ff551e5516ff5512550cff55075504ff550054fbff54f354f3ff54e854e5ff54df54ceff54be54b1ff54a854a6ff54a0549eff5499549fff549a5491ff54895489ff54865489ff54875477ff546c5462ff54545449ff5443543cff54335426ff541d5416ff5418540fff540453f6ff53e853ddff53ce53c6ff53ba53b3ff53a85399ff53805371ff5362535cff5355534aff533e5333ff5322530fff52f952ddff52d752c5ff52b952aaff52985283ff52695258ff524d523dff522c5221ff520c51f9ff51ec51e0ff51c651b1ff51a651a4ff51a451a6ff51b251adff51aa51b8ff51b351b8ff51bd51b7ff51b551c7ff51bd51c2ff51b151b6ff51af51b2ff51b051b8ff51b751afff51a05194ff518f5189ff518d5186ff5185517cff51745165ff5154514aff5134512bff511c5109ff50ed50dcff50d150bcff50a95095ff50775060ff50465036ff50215015ff5010500dff50015000ff4ff54fe7ff4fdc4fc6ff4fae4fa1ff4f984f89ff4f814f85ff4f804f74ff4f6d4f6aff4f684f63ff4f5d4f57ff4f534f4aff4f444f42ff4f3b4f34ff4f314f31ff4f284f20ff4f204f1aff4f1a4f1bff4f1a4f17ff4f0a4efeff4efd4efcff4ef94ef1ff4eee4eefff4eed4ee7ff4ee74eecff4ee84ee9ff4ee44edfff4ece4ecdff4ebf4eb3ff4ea74e9bff4e9d4e93ff4e874e78ff4e694e51ff4e3d4e30ff4e184dffff4de34dc0ff4da44d8aff4d6a4d60ff4d504d37ff4d1d4d03ff4ceb4cddff4cc54cb4ff4ca24c93ff4c7f4c67ff4c654c46ff4c2d4c17ff4bff4bd9ff4bce4bd4ff4bcf4bbbff4bc94bbeff4be54be9ff4be54be6ff4bd54bceff4bc64bb0ff4ba74bb2ff4bb54bbeff4bbd4bc4ff4bbc4bb4ff4baa4b8cff4b654b72ff4b644b66ff4b574b5aff4b4e4b31ff4b164b00ff4afd4ae4ff4ac74ab1ff4a9d4a84ff4a7f4a69ff4a5a4a46ff4a404a37ff4a2d4a2aff4a244a18ff4a0f49fcff49f049f6ff49f649f3ff49f549ebff49dd49c0ff499f4994ff498d4976ff4971496aff4979499cff49a349a6ff49914999ff4998499aff49a349a2ff49bb49d1ff49e249f1ff49f549e8ff49fc4a03ff4a0b4a23ff4a354a59ff4a624a7cff4a894aa0ff4abb4ad8ff4ae74aecff4b024b1fff4b504b70ff4b994babff4bb24bb0ff4bd24bdfff4be94c0eff4c264c29ff4c3d4c62ff4c6e4c7bff4c904cb9ff4ce24cf7ff4d084d13ff4d184d06ff4d1e4d36ff4d3c4d3dff4d4d4d68ff4d914db0ff4dcd4ddfff4e0d4e18ff4e2d4e37ff4e4a4e51ff4e674e87ff4e9e4eaaff4ec54ed1ff4ed84ee4ff4eff4f1fff4f394f4cff4f6d4f8dff4fb54fccff4fd34ffaff4ff85026ff50445056ff507f5076ff5083509dff50a750b0ff50cb50e7ffff026c
  Response: 0000000000 ff c184b3ee930477 ff 000b691c89f0 ff 691c89f0 ff e1ff 560b560a ff 560f5611 ff 560e5609ff560b560fff5611561aff56195621ff5624562aff561e5612ff5619561fff5614560dff5611560cff5606560eff560b5616ff5613560bff560555fdff55f155eaff55db55d4ff55d155d4ff55ce55d2ff55b955a9ff55a05591ff558a5581ff556a556cff5567556eff55695563ff555d5549ff55315525ff551e5516ff5512550cff55075504ff550054fbff54f354f3ff54e854e5ff54df54ceff54be54b1ff54a854a6ff54a0549eff5499549fff549a5491ff54895489ff54865489ff54875477ff546c5462ff54545449ff5443543cff54335426ff541d5416ff5418540fff540453f6ff53e853ddff53ce53c6ff53ba53b3ff53a85399ff53805371ff5362535cff5355534aff533e5333ff5322530fff52f952ddff52d752c5ff52b952aaff52985283ff52695258ff524d523dff522c5221ff520c51f9ff51ec51e0ff51c651b1ff51a651a4ff51a451a6ff51b251adff51aa51b8ff51b351b8ff51bd51b7ff51b551c7ff51bd51c2ff51b151b6ff51af51b2ff51b051b8ff51b751afff51a05194ff518f5189ff518d5186ff5185517cff51745165ff5154514aff5134512bff511c5109ff50ed50dcff50d150bcff50a95095ff50775060ff50465036ff50215015ff5010500dff50015000ff4ff54fe7ff4fdc4fc6ff4fae4fa1ff4f984f89ff4f814f85ff4f804f74ff4f6d4f6aff4f684f63ff4f5d4f57ff4f534f4aff4f444f42ff4f3b4f34ff4f314f31ff4f284f20ff4f204f1aff4f1a4f1bff4f1a4f17ff4f0a4efeff4efd4efcff4ef94ef1ff4eee4eefff4eed4ee7ff4ee74eecff4ee84ee9ff4ee44edfff4ece4ecdff4ebf4eb3ff4ea74e9bff4e9d4e93ff4e874e78ff4e694e51ff4e3d4e30ff4e184dffff4de34dc0ff4da44d8aff4d6a4d60ff4d504d37ff4d1d4d03ff4ceb4cddff4cc54cb4ff4ca24c93ff4c7f4c67ff4c654c46ff4c2d4c17ff4bff4bd9ff4bce4bd4ff4bcf4bbbff4bc94bbeff4be54be9ff4be54be6ff4bd54bceff4bc64bb0ff4ba74bb2ff4bb54bbeff4bbd4bc4ff4bbc4bb4ff4baa4b8cff4b654b72ff4b644b66ff4b574b5aff4b4e4b31ff4b164b00ff4afd4ae4ff4ac74ab1ff4a9d4a84ff4a7f4a69ff4a5a4a46ff4a404a37ff4a2d4a2aff4a244a18ff4a0f49fcff49f049f6ff49f649f3ff49f549ebff49dd49c0ff499f4994ff498d4976ff4971496aff4979499cff49a349a6ff49914999ff4998499aff49a349a2ff49bb49d1ff49e249f1ff49f549e8ff49fc4a03ff4a0b4a23ff4a354a59ff4a624a7cff4a894aa0ff4abb4ad8ff4ae74aecff4b024b1fff4b504b70ff4b994babff4bb24bb0ff4bd24bdfff4be94c0eff4c264c29ff4c3d4c62ff4c6e4c7bff4c904cb9ff4ce24cf7ff4d084d13ff4d184d06ff4d1e4d36ff4d3c4d3dff4d4d4d68ff4d914db0ff4dcd4ddfff4e0d4e18ff4e2d4e37ff4e4a4e51ff4e674e87ff4e9e4eaaff4ec54ed1ff4ed84ee4ff4eff4f1fff4f394f4cff4f6d4f8dff4fb54fccff4fd34ffaff4ff85026ff50445056ff507f5076ff5083509dff50a750b0ff50cb50e7ffff026c
  """


# --------------------------------------------------
# Simarine Message Parsing
# --------------------------------------------------


class MessageFieldType(IntEnum):
  INT = 1
  TIMESTAMPED_INT = 3
  TIMESTAMPED_TEXT = 4


class MessageFields:
  def __init__(self, data: bytes, offset: int = 0):
    self._data = data
    self._offset = offset

    self._fields: Dict[int, MessageFields] = {}
    self._iter_offset = 0
    self._parsed = False

  # --------------------------------------------------
  # Iteration
  # --------------------------------------------------

  def __iter__(self):
    self._iter_offset = 0
    return self

  def __next__(self):
    if self._offset + self._iter_offset >= len(self._data):
      raise StopIteration

    field = MessageFields(self._data, self._offset + self._iter_offset)
    self._iter_offset += field.length
    return field

  # --------------------------------------------------
  # Parsing
  # --------------------------------------------------

  def _parse_all(self):
    if self._parsed:
      return

    for field in self:
      self._fields[field.id] = field

    self._parsed = True

  # --------------------------------------------------
  # Access
  # --------------------------------------------------

  def get(self, field_id: int) -> Optional["MessageFields"]:
    self._parse_all()
    return self._fields.get(field_id)

  def __getitem__(self, field_id: int) -> Optional["MessageFields"]:
    return self.get(field_id)

  def items(self):
    self._parse_all()
    return self._fields.items()

  def as_dict(self) -> Dict[int, "MessageFields"]:
    self._parse_all()
    return self._fields

  def to_dict(self):
    data = {}
    for name, _ in inspect.getmembers(self.__class__, lambda x: isinstance(x, property)):
      data[name] = getattr(self, name)
    return data

  # --------------------------------------------------
  # Field Properties
  # --------------------------------------------------

  @property
  def id(self) -> int:
    return self._data[self._offset]

  @property
  def type(self) -> MessageFieldType:
    return MessageFieldType(self._data[self._offset + 1])

  @property
  def length(self) -> int:
    match self.type:
      case MessageFieldType.INT:
        return 7
      case MessageFieldType.TIMESTAMPED_INT:
        return 12
      case MessageFieldType.TIMESTAMPED_TEXT:
        i = self._data.find(b"\x00\xff", self._offset + 7)
        if i < 0:
          raise ValueError("Unterminated text field")
        return i + 2 - self._offset

  @property
  def _field_bytes(self) -> bytes:
    return self._data[self._offset : self._offset + self.length]

  @property
  def _timestamp_bytes(self) -> Optional[bytes]:
    if self.type in [MessageFieldType.TIMESTAMPED_INT, MessageFieldType.TIMESTAMPED_TEXT]:
      return self._field_bytes[2:6]

  @property
  def _value_bytes(self) -> bytes:
    match self.type:
      case MessageFieldType.INT:
        return self._field_bytes[2:6]
      case MessageFieldType.TIMESTAMPED_INT:
        return self._field_bytes[7:11]
      case MessageFieldType.TIMESTAMPED_TEXT:
        return self._field_bytes[7:-2]
      case _:
        return self._field_bytes

  @property
  def int16_hi(self) -> int:
    return int.from_bytes(self._value_bytes[0:2], "big", signed=True)

  @property
  def int16_lo(self) -> int:
    return int.from_bytes(self._value_bytes[2:4], "big", signed=True)

  @property
  def int32(self) -> int:
    return int.from_bytes(self._value_bytes, "big", signed=True)

  @property
  def uint16_hi(self) -> int:
    return int.from_bytes(self._value_bytes[0:2], "big", signed=False)

  @property
  def uint16_lo(self) -> int:
    return int.from_bytes(self._value_bytes[2:4], "big", signed=False)

  @property
  def uint32(self) -> int:
    return int.from_bytes(self._value_bytes, "big", signed=False)

  @property
  def text(self) -> Optional[str]:
    if self.type == MessageFieldType.TIMESTAMPED_TEXT:
      return self._value_bytes.decode("utf-8", errors="ignore")

  @property
  def timestamp(self) -> Optional[int]:
    if self._timestamp_bytes:
      return int.from_bytes(self._timestamp_bytes, "big", signed=False)

  @property
  def value(self) -> int | str:
    if self.type == MessageFieldType.TIMESTAMPED_TEXT:
      return self.text
    return self.int32
