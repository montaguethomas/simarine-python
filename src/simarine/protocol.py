"""
Simarine Protocol
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar, Dict, Optional

import crcmod

from . import exceptions


# --------------------------------------------------
# Simarine Message Type
# --------------------------------------------------


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
    0000000000 ff 01 84b3ee93 0011
    ff 01 01 84b3ee93   -> Serial Number ( uint32(84b3ee93) = 2226384531)
    ff 02 01 00010015   -> Firmware Version ( int16(0001) . int16(0015) = 1.21)
    ff 97a3
  """

  DEVICE_SENSOR_COUNT = 0x02
  """
  Request device and sensor counts.

  Request:
    0000000000 ff 02 00000000 0003 ff 7688

  Response:
    0000000000 ff 02 84b3ee93 0011
    ff 01 01 00000013   -> Device Count / Last Device Id (zero index)
    ff 02 01 0000001a   -> Sensor Count / Last Sensor Id (zero index)
    ff 76e9
  """

  DEVICE_INFO = 0x41
  """
  Request device information for a specific device index.

  Request:
    0000000000 ff 41 00000000 0016
    ff 00 01 0000000b               -> Device Id
    ff 01 03 00000000 ff 00000000   -> Unknown
    ff fe6d

  Response:
    0000000000 ff 41 84b3ee93 005a
    ff 00 01 0000000b
    ff 01 03 65932547 ff 00000001
    ff 02 01 00000000
    ff 03 04 65932547ff5343353033205b313736355d2031 00
    ff 04 01 2cb15f45
    ff 05 01 00000001
    ff 06 03 678ef359 ff 00000011
    ff 07 03 00000000 ff 39420bbb
    ff 4e7f

  Response contains structured binary fields:
  - Field 0: Device Id
  - Field 1: Device Type
  - Field 3: Device Name
  """

  SENSOR_INFO = 0x20
  """
  Request sensor information for given device index.

  Request:
    0000000000 ff 20 00000000 0011
    ff 01 01 00000002   -> Sensor Id
    ff 02 01 00000000   -> Unknown
    ff 74ee

  Response:
    0000000000 ff 20 84b3ee93 008b
    ff 01 01 00000002
    ff 02 01 00000005
    ff 03 01 00000005
    ff 04 01 00000000
    ff 05 03 00000000 ff 00000000
    ff 06 03 00000000 ff 32ff1202
    ff 07 03 00000000 ff 012c0014
    ff 08 03 00000000 ff 00000000
    ff 09 03 00000000 ff 32ff1202
    ff 0a 03 00000000 ff 012c0014
    ff 0b 03 00000000 ff 00000002
    ff 0c 03 00000000 ff 00000000
    ff 0d 03 00000000 ff 00000000
    ff 6fd9

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
    0000000000 ff b0 84b3ee93 00ab
    ff 00 01 691c8a3c
    ff 01 01 691c43ea
    ff 02 01 fffffc16
    ff 03 01 00018e8f
    ff 04 01 fffffc16
    ff 05 01 0000342a
    ff 09 01 691c8947
    ff 0a 01 fffffc16
    ff 0b 01 000001dd
    ff 0c 01 0008d88b
    ff 0d 01 000033f4
    ff 0e 01 00000000
    ff 0f 01 0000ffff
    ff 10 01 0000ffff
    ff 11 01 00005e64
    ff 12 01 00000039
    ff 13 01 33410062
    ff 14 01 000001dd
    ff 15 01 000033f4
    ff 16 01 7fffffff
    ff 17 01 000133e4
    ff 18 01 ffffffc9
    ff 19 01 00000035
    ff 1a 01 7fffffff
    ff 1ec5

  Response provides:
  - Sensor Id
  - Sensor Value
  """

  UNKNOWN_03 = 0x03
  """
  Unknown type 0x03

  Request:
    0000000000 ff 03 00000000 000a
    ff 01 01 00000000
    ff 24d2

  Response:
    0000000000 ff 03 84b3ee93 000a
    ff 01 01 00000001
    ff b56e
  """

  UNKNOWN_10 = 0x10
  """
  Unknown type 0x10

  Request:
    0000000000 ff 10 00000000 0011
    ff 01 01 691c8a3a   -> timestamp
    ff 02 01 ffffb9b0   -> int32? -18000
    ff 0301

  Response:
    0000000000 ff aa 84b3ee93 000a
    ff 01 01 0000ff10
    ff 85d5
  """

  UNKNOWN_50 = 0x50
  """
  Unknown type 0x50

  Request:
    0000000000 ff 50 00000000 0003 ff 3036

  Response:
    0000000000 ff aa 84b3ee93 000a
    ff 01 01 0000ff50   -> int32? 65360
    ff a1b1
  """

  UNKNOWN_AA = 0xAA
  """
  Unknown type 0xAA

  Request:
    0000000000 ff 10 00000000 0011
    ff 01 01 691c8a3a
    ff 02 01 ffffb9b0
    ff 0301

  Response:
    0000000000 ff aa 84b3ee93 000a
    ff 01 01 0000ff10
    ff 85d5
  """

  ATMOSPHERIC_PRESSURE_HISTORY = 0xC1
  """
  Broadcasted atmospheric pressure history (timeseries).

  Sampled over 72 hrs, ordered newest -> oldest.

  Received:
    0000000000 ff c1 84b3ee93 0477
    ff 00 0b 691c89f0 ff 691c89f0 -> field id (0), field type (0b -> 11), timestamp1 (uint32), marker, timestamp2 (uint32)
    ff e1 -> number of 32-bit blocks!
    ff 560b560a -> int16_hi, int16_lo? millibars graph over time? max 72 hrs
    ff 560f5611 ff 560e5609 ff 560b560f ff 5611561a ff 56195621 ff 5624562a ff 561e5612 ff 5619561f ff 5614560d
    ff 5611560c ff 5606560e ff 560b5616 ff 5613560b ff 560555fd ff 55f155ea ff 55db55d4 ff 55d155d4 ff 55ce55d2 ff 55b955a9
    ff 55a05591 ff 558a5581 ff 556a556c ff 5567556e ff 55695563 ff 555d5549 ff 55315525 ff 551e5516 ff 5512550c ff 55075504
    ff 550054fb ff 54f354f3 ff 54e854e5 ff 54df54ce ff 54be54b1 ff 54a854a6 ff 54a0549e ff 5499549f ff 549a5491 ff 54895489
    ff 54865489 ff 54875477 ff 546c5462 ff 54545449 ff 5443543c ff 54335426 ff 541d5416 ff 5418540f ff 540453f6 ff 53e853dd
    ff 53ce53c6 ff 53ba53b3 ff 53a85399 ff 53805371 ff 5362535c ff 5355534a ff 533e5333 ff 5322530f ff 52f952dd ff 52d752c5
    ff 52b952aa ff 52985283 ff 52695258 ff 524d523d ff 522c5221 ff 520c51f9 ff 51ec51e0 ff 51c651b1 ff 51a651a4 ff 51a451a6
    ff 51b251ad ff 51aa51b8 ff 51b351b8 ff 51bd51b7 ff 51b551c7 ff 51bd51c2 ff 51b151b6 ff 51af51b2 ff 51b051b8 ff 51b751af
    ff 51a05194 ff 518f5189 ff 518d5186 ff 5185517c ff 51745165 ff 5154514a ff 5134512b ff 511c5109 ff 50ed50dc ff 50d150bc
    ff 50a95095 ff 50775060 ff 50465036 ff 50215015 ff 5010500d ff 50015000 ff 4ff54fe7 ff 4fdc4fc6 ff 4fae4fa1 ff 4f984f89
    ff 4f814f85 ff 4f804f74 ff 4f6d4f6a ff 4f684f63 ff 4f5d4f57 ff 4f534f4a ff 4f444f42 ff 4f3b4f34 ff 4f314f31 ff 4f284f20
    ff 4f204f1a ff 4f1a4f1b ff 4f1a4f17 ff 4f0a4efe ff 4efd4efc ff 4ef94ef1 ff 4eee4eef ff 4eed4ee7 ff 4ee74eec ff 4ee84ee9
    ff 4ee44edf ff 4ece4ecd ff 4ebf4eb3 ff 4ea74e9b ff 4e9d4e93 ff 4e874e78 ff 4e694e51 ff 4e3d4e30 ff 4e184dff ff 4de34dc0
    ff 4da44d8a ff 4d6a4d60 ff 4d504d37 ff 4d1d4d03 ff 4ceb4cdd ff 4cc54cb4 ff 4ca24c93 ff 4c7f4c67 ff 4c654c46 ff 4c2d4c17
    ff 4bff4bd9 ff 4bce4bd4 ff 4bcf4bbb ff 4bc94bbe ff 4be54be9 ff 4be54be6 ff 4bd54bce ff 4bc64bb0 ff 4ba74bb2 ff 4bb54bbe
    ff 4bbd4bc4 ff 4bbc4bb4 ff 4baa4b8c ff 4b654b72 ff 4b644b66 ff 4b574b5a ff 4b4e4b31 ff 4b164b00 ff 4afd4ae4 ff 4ac74ab1
    ff 4a9d4a84 ff 4a7f4a69 ff 4a5a4a46 ff 4a404a37 ff 4a2d4a2a ff 4a244a18 ff 4a0f49fc ff 49f049f6 ff 49f649f3 ff 49f549eb
    ff 49dd49c0 ff 499f4994 ff 498d4976 ff 4971496a ff 4979499c ff 49a349a6 ff 49914999 ff 4998499a ff 49a349a2 ff 49bb49d1
    ff 49e249f1 ff 49f549e8 ff 49fc4a03 ff 4a0b4a23 ff 4a354a59 ff 4a624a7c ff 4a894aa0 ff 4abb4ad8 ff 4ae74aec ff 4b024b1f
    ff 4b504b70 ff 4b994bab ff 4bb24bb0 ff 4bd24bdf ff 4be94c0e ff 4c264c29 ff 4c3d4c62 ff 4c6e4c7b ff 4c904cb9 ff 4ce24cf7
    ff 4d084d13 ff 4d184d06 ff 4d1e4d36 ff 4d3c4d3d ff 4d4d4d68 ff 4d914db0 ff 4dcd4ddf ff 4e0d4e18 ff 4e2d4e37 ff 4e4a4e51
    ff 4e674e87 ff 4e9e4eaa ff 4ec54ed1 ff 4ed84ee4 ff 4eff4f1f ff 4f394f4c ff 4f6d4f8d ff 4fb54fcc ff 4fd34ffa ff 4ff85026
    ff 50445056 ff 507f5076 ff 5083509d ff 50a750b0 ff 50cb50e7
    ff -> end marker
    ff 026c
  """


# --------------------------------------------------
# Simarine Message
# --------------------------------------------------


@dataclass(frozen=True, slots=True)
class Message:
  """
  Simarine Pico Message

  Message Layout:
    0..4      : PREAMBLE
    5         : MARKER(HeaderSection)
    6         : type(MessageType)
    7..10     : serial_number(uint32)
    11..12    : length(uint16)
    13..N-3   : payload(MessageFields)
    N-2       : MARKER(ChecksumSection)
    N-1..N    : CRC16
  """

  bytes: bytes
  fields: MessageFields
  length: int
  payload: bytes
  serial_number: int
  type: MessageType

  HEADER_SIZE: ClassVar[int] = 13
  """The number of bytes used for the message header."""

  MARKER_BYTE: ClassVar[int] = 0xFF
  """The byte used to marker separation between fields/sections."""

  PREAMBLE_BYTES: ClassVar[bytes] = bytes([0x00, 0x00, 0x00, 0x00, 0x00])
  """The static message preamble bytes."""

  PREAMBLE_SIZE: ClassVar[int] = 5
  """The number of bytes used for message preamble bytes."""

  TYPE_POS: ClassVar[int] = 6
  """The position of the message type byte in a message header."""

  SERIAL_NUMBER_POS: ClassVar[int] = 7
  """The position of the system serial number bytes in a message header."""

  SERIAL_NUMBER_SIZE: ClassVar[int] = 4
  """The number of bytes used for the system serial number bytes."""

  LENGTH_POS: ClassVar[int] = 11
  """The position of the message length bytes in a message header."""

  LENGTH_SIZE: ClassVar[int] = 2
  """The number of bytes used for the message length bytes."""

  CRC_MARKER_POS: ClassVar[int] = -3
  """The position of the marker byte for the message checksum section."""

  CRC_POS: ClassVar[int] = -2
  """The position of the message checksum bytes in a message."""

  CRC_SIZE: ClassVar[int] = 2
  """The number of bytes used for the message checksum bytes."""

  _CRC_FUNC: ClassVar = crcmod.mkCrcFun(0x11189, initCrc=0x0000, rev=False, xorOut=0x0000)
  """
  The message checksum calculation function.

  The message checksum region is all message data, including header bytes, up to the message checksum section.
  """

  def __repr__(self):
    return (
      f"<Message type={self.type.name} sn={self.serial_number} len={self.length} payload_len={len(self.payload)} bytes={self.bytes.hex()}>"
    )

  @classmethod
  def build(cls, msg_type: MessageType, payload: bytes, serial_number: int = None):
    fields = MessageFields(payload)

    length = len(payload) + 1 + cls.CRC_SIZE  # Add the checksum marker byte
    length_bytes = length.to_bytes(cls.LENGTH_SIZE, "big", signed=False)

    serial_number = 0 if serial_number is None else serial_number
    serial_number_bytes = serial_number.to_bytes(cls.SERIAL_NUMBER_SIZE, "big", signed=False)

    msg_bytes = bytearray(cls.PREAMBLE_BYTES)
    msg_bytes.append(cls.MARKER_BYTE)
    msg_bytes.append(msg_type.value)
    msg_bytes.extend(serial_number_bytes)
    msg_bytes.extend(length_bytes)
    # msg_bytes.append(cls.MARKER_BYTE) # payload should include a leading marker byte
    msg_bytes.extend(payload)

    crc = cls._CRC_FUNC(msg_bytes)
    msg_bytes.append(cls.MARKER_BYTE)
    msg_bytes.extend(crc.to_bytes(cls.CRC_SIZE, "big", signed=False))

    return cls(
      bytes=bytes(msg_bytes),
      fields=fields,
      length=length,
      payload=payload,
      serial_number=serial_number,
      type=msg_type,
    )

  @classmethod
  def from_bytes(cls, msg_bytes: bytes, expected_type: Optional[MessageType] = None):
    if len(msg_bytes) < cls.HEADER_SIZE + cls.CRC_SIZE:
      raise exceptions.InvalidHeaderLength(f"Response too short: {len(msg_bytes)} < {cls.HEADER_SIZE + cls.CRC_SIZE}")

    if msg_bytes[: cls.PREAMBLE_SIZE] != cls.PREAMBLE_BYTES:
      raise exceptions.InvalidHeaderPreamble(f"Invalid preamble: {msg_bytes[: cls.PREAMBLE_SIZE].hex()}")

    if msg_bytes[cls.PREAMBLE_SIZE] != cls.MARKER_BYTE:
      raise exceptions.InvalidHeaderMarker(f"Invalid header marker byte: 0x{msg_bytes[cls.PREAMBLE_SIZE]:02X}")

    msg_type = MessageType(msg_bytes[cls.TYPE_POS])

    if expected_type and msg_type != expected_type:
      raise exceptions.MessageTypeMismatch(f"Expected {expected_type.name}, got {msg_type.name}")

    msg_serial_number = int.from_bytes(
      msg_bytes[cls.SERIAL_NUMBER_POS : cls.SERIAL_NUMBER_POS + cls.SERIAL_NUMBER_SIZE], "big", signed=False
    )

    msg_length = int.from_bytes(msg_bytes[cls.LENGTH_POS : cls.LENGTH_POS + cls.LENGTH_SIZE], "big", signed=False)
    expected_length = len(msg_bytes) - cls.HEADER_SIZE

    if expected_length != msg_length:
      raise exceptions.InvalidMessageLength(f"Length mismatch: expected={expected_length}, got={msg_length}")

    if msg_bytes[cls.CRC_MARKER_POS] != cls.MARKER_BYTE:
      raise exceptions.InvalidChecksumMarker(f"Invalid checksum marker byte: 0x{msg_bytes[cls.CRC_MARKER_POS]:02X}")

    msg_crc = msg_bytes[cls.CRC_POS :]
    expected_crc = cls._CRC_FUNC(msg_bytes[: cls.CRC_MARKER_POS]).to_bytes(cls.CRC_SIZE, "big", signed=False)

    if expected_crc != msg_crc:
      raise exceptions.CRCMismatch(f"CRC mismatch: expected={expected_crc.hex()}, got={msg_crc.hex()}")

    payload = msg_bytes[cls.HEADER_SIZE : cls.CRC_MARKER_POS]
    fields = MessageFields(payload)

    return cls(
      bytes=msg_bytes,
      fields=fields,
      length=msg_length,
      payload=payload,
      serial_number=msg_serial_number,
      type=msg_type,
    )


# --------------------------------------------------
# Simarine Message Fields
# --------------------------------------------------


class MessageFieldType(IntEnum):
  INT = 0x01
  TIMESTAMPED_INT = 0x03
  TIMESTAMPED_TEXT = 0x04
  TIMESERIES = 0x0B


class MessageFields:
  """
  Simarine Pico Message Fields

  Message Field Layout:
    0       : MARKER(FieldSection)
    1       : id(int32)
    2       : type(MessageFieldType)
    3..6    : value(int32) | timestamp(uint32)
    7       : MARKER(ExtendedValueSection)
    8..12   : value(int32)    <- if type==TIMESTAMPED_INT
    8..N-1  : text(str(utf8)) <- if type==TIMESTAMPED_TEXT
    N       : TEXT_END_MARKER <- if type==TIMESTAMPED_TEXT
  """

  FIELD_MARKER_POS: ClassVar[int] = 0
  ID_POS: ClassVar[int] = 1
  TYPE_POS: ClassVar[int] = 2
  VALUE_POS: ClassVar[int] = 3
  VALUE_SIZE: ClassVar[int] = 4
  TIMESTAMPED_VALUE_POS: ClassVar[int] = 8
  TIMESERIES_COUNT_POS: ClassVar[int] = 13
  TIMESERIES_VALUE_POS: ClassVar[int] = 14
  TIMESERIES_VALUE_SIZE: ClassVar[int] = 5
  TEXT_END_MARKER_BYTE: ClassVar[int] = 0x00

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

  def __repr__(self):
    return f"<MessageFields id={self.id} type={self.type.name} value={self.value}>"

  def get(self, field_id: int) -> Optional[MessageFields]:
    self._parse_all()
    return self._fields.get(field_id)

  def __getitem__(self, field_id: int) -> Optional[MessageFields]:
    return self.get(field_id)

  def items(self):
    self._parse_all()
    return self._fields.items()

  def as_dict(self) -> Dict[int, MessageFields]:
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
    return self._data[self._offset + self.ID_POS]

  @property
  def type(self) -> MessageFieldType:
    return MessageFieldType(self._data[self._offset + self.TYPE_POS])

  @property
  def length(self) -> int:
    match self.type:
      case MessageFieldType.INT:
        return 7
      case MessageFieldType.TIMESTAMPED_INT:
        return 12
      case MessageFieldType.TIMESTAMPED_TEXT:
        i = self._data.find(self.TEXT_END_MARKER_BYTE, self._offset + self.TIMESTAMPED_VALUE_POS)
        if i < 0:
          raise ValueError("Unterminated text field")
        return i + 1 - self._offset  # Add the text end marker byte
      case MessageFieldType.TIMESERIES:
        # ff 00 0b 69319d40 ff 69319d40 ff e1 ff 546a 5464 ff 5461 5453 ... ff 5849 5846 ff ff <checksum>
        count = self._data[self.TIMESERIES_COUNT_POS]
        marker_pos = self.TIMESERIES_VALUE_POS + (count * self.TIMESERIES_VALUE_SIZE)
        if self._data[self._offset + marker_pos] != Message.MARKER_BYTE:
          raise ValueError("Unterminated timeseries field")
        return marker_pos + 1  # Include the end marker

  @property
  def _field_bytes(self) -> bytes:
    return self._data[self._offset : self._offset + self.length]

  @property
  def _timestamp_bytes(self) -> Optional[bytes]:
    if self.type in [MessageFieldType.TIMESTAMPED_INT, MessageFieldType.TIMESTAMPED_TEXT, MessageFieldType.TIMESERIES]:
      return self._field_bytes[self.VALUE_POS : self.VALUE_POS + self.VALUE_SIZE]

  @property
  def _value_bytes(self) -> bytes:
    match self.type:
      case MessageFieldType.INT:
        return self._field_bytes[self.VALUE_POS : self.VALUE_POS + self.VALUE_SIZE]
      case MessageFieldType.TIMESTAMPED_INT:
        return self._field_bytes[self.TIMESTAMPED_VALUE_POS : self.TIMESTAMPED_VALUE_POS + self.VALUE_SIZE]
      case MessageFieldType.TIMESTAMPED_TEXT:
        return self._field_bytes[self.TIMESTAMPED_VALUE_POS : -1]
      case MessageFieldType.TIMESERIES:
        return self._field_bytes[self.TIMESERIES_VALUE_POS : -1]
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
  def timeseries(self) -> Optional[list[int]]:
    if self.type == MessageFieldType.TIMESERIES:
      series: list[int] = []
      for i in range(0, len(self._value_bytes), 5):
        if self._value_bytes[i] != Message.MARKER_BYTE:
          raise ValueError(f"Timeseries block mismatch at index {i}, expected {Message.MARKER_BYTE}, got 0x{self._value_bytes[i]:02X}")
        series.append(int.from_bytes(self._value_bytes[i + 1 : i + 3], "big", signed=False))
        series.append(int.from_bytes(self._value_bytes[i + 3 : i + 5], "big", signed=False))
      return series

  @property
  def value(self) -> int | str:
    match self.type:
      case MessageFieldType.TIMESTAMPED_TEXT:
        return self.text
      case MessageFieldType.TIMESERIES:
        return self.timeseries
      case _:
        return self.int32
