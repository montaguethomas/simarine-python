# Simarine Pico Message Protocol (Reverse‑Engineered)

> **Status:**
> This document is based on reverse‑engineering of traffic between a Simarine Pico device and its companion application.
> It describes the on‑wire message framing and checksum format that are implemented in this repository.
> It is **not** an official specification from Simarine and may be incomplete or slightly inaccurate in places.

---

## 1. Transport Overview

The Simarine Pico ecosystem uses a simple, custom binary protocol transported over both TCP and UDP:

- **TCP control channel**
  - Default port: **5001**
  - Used for request/response style interactions (querying system info, devices, sensors, states, etc.).
- **UDP broadcast channel**
  - Default port: **43210**
  - Used for unsolicited state broadcasts and for discovery.

Both transports carry **the same message framing** described below.

All multi‑byte integer fields are big‑endian (“network byte order”).

---

## 2. Message Framing

Every message (both TCP and UDP) follows the same framing:

| Offset    | Length     | Name            | Type      | Description              | Example           | Notes                                                         |
| --------- | ---------- | --------------- | --------- | ------------------------ | ----------------- | ------------------------------------------------------------- |
| `0..4`    | 5 bytes    | Preamble        | Constant  | Reserved, all zero bytes | `00 00 00 00 00`  |                                                               |
| `5`       | 1 byte     | Header Marker   | Constant  | Header start marker      | `FF`              | Distinguishes start of the header                             |
| `6`       | 1 byte     | Type            | Enum[int] | Message Type             | `01`, `02`, `...` | Identifies the semantic meaning of payload                    |
| `7..10`   | 4 bytes    | Serial Number   | uint32    | System Serial Number     | `84 B3 EE 93`     | Used for request/response correlation                         |
| `11..12`  | 2 bytes    | Length          | uint16    | Number of trailing bytes | `00 10`           | See [Length](#25-length) section                              |
| `13..N-3` | N−16 bytes | Payload         | MsgFields | Message Fields           | `...`             | See [Message Field Framing](#3-message-field-framing) section |
| `N-2`     | 1 byte     | Checksum Marker | Constant  | Checksum start marker    | `FF`              | Distinguishes start of checksum                               |
| `N-1..N`  | 2 bytes    | Checksum        | uint16    | CRC-16 over message      | `89 B8`           | See [Checksum](#28-checksum) section                          |

### 2.1. Preamble

The **Preamble** (offset `0..4`) is always five null bytes.

```text
00 00 00 00 00
```

If a message does not start with this exact preamble, it is rejected as invalid.

### 2.2. Header Marker

The **Header Marker** (offset `5`) is a single constant byte to mark the start of the message header.

If this byte is not `0xFF`, the message is rejected.

### 2.3. Type

The **Type** (offset `6`) is a single byte and denotes the semantic meaning of the payload.
This implementation models it as an enum (`MessageType`), with values that have been observed to include, for example:

- System information
- Device and sensor enumeration
- Per‑sensor state snapshots
- Other configuration or status messages

Because this is a reverse‑engineered protocol and new message types may exist, this document intentionally stays at the
"opaque code" level:

- The wire format for the message type is **always 1 byte**.
- Unknown or new values should be treated as opaque and safely skipped or logged.

For precise constants, refer to the `MessageType` definitions in the codebase when implementing a client.

### 2.4. Serial Number

The **Serial Number** (offset `7..10`) is a 32-bit unsigned integer and denotes the system serial number.
Clients sending requests can set this to zero (`00 00 00 00`). Messages from a Simarine Pico device will set it.

Used primarily for correlation and traceability; the protocol as implemented does not currently enforce any particular
semantics beyond carrying this value through.

### 2.5. Length

The **Length** (offset `11..12`) is a 16-bit unsigned integer, denotes the number of trailing bytes after the header,
and is the end of the message header.

```text
length = len(MessageFields)
        + 1 (ChecksumMarker)
        + 2 (Checksum)
```

When parsing, this is validated by comparing against the actual number of byte present after the message header.

### 2.6. Payload

The **Payload** (offset `13..N-3`) is all bytes between the end of the message header and the checksum marker.
It is a sequence of **Message Field** bytes, which can be empty (zero bytes).

See the [Message Field Framing](#3-message-field-framing) section for more details.

### 2.7. Checksum Marker

The **Checksum Marker** (offset `N-2`) is a single constant byte to mark the start of the message checksum.

If this byte is not `0xFF`, the message is rejected.

### 2.8. Checksum

The **Checksum** (offset `N-1..N`) is a 16-bit unsigned integer and denotes the of the checksum of the message.

Any mismatch between the checksum in the message and the computed value causes the message to be rejected.

#### 2.8.1. Function

The message checksum is computed using this CRC-16 algorithm:

- **Polynomial:** `0x11189`
- **Initial Value:** `0x0000`
- **XOR In/Out:** `False`
- **Final XOR:** `0x0000`

#### 2.8.2. Coverage

The message checksum region is all message data, including header bytes, up to the message checksum marker.

```text
checksum = CRC_FUNC(message[0..-3])
```

When building a message, this is the entirety of the message. The resulting checksum value is appended to the message
with the checksum marker:

```text
checksum = CRC_FUNC(message)
message += 0xFF + ((checksum >> 8) & 0xFF) + (checksum & 0xFF)
```

---

## 3. Message Field Framing

Every message field follows the same framing:

| Offset | Length    | Name   | Type      | Description | Example          | Notes                                        |
| ------ | --------- | ------ | --------- | ----------- | ---------------- | -------------------------------------------- |
| `0`    | 1 byte    | Marker | Constant  | Field Start | `FF`             |                                              |
| `1`    | 1 byte    | ID     | int       | Field ID    | `01`             | The id or index of the field                 |
| `2`    | 1 byte    | Type   | Enum[int] | Field Type  | `01`, `03`, `04` | Identifies the semantic meaning of the field |
| `3..N` | N−3 bytes | Data   | Data      | Field Data  | `...`            | Varies based on field type                   |

### 3.1. Marker

The **Marker** (offset `0`) is a single constant byte to mark the start of the message field.

### 3.2. Id

The **Id** (offset `1`) is a single byte and denotes the ID and/or index of the message field.

### 3.3. Type

The **Type** (offset `2`) is a single byte and denotes the semantic meaning of the message field's data.
This implementation models it as an enum (`MessageFieldType`), with values that have been observed to include, for example:

- Integer (`0x01`)
- Timestamped Integer (`0x03`)
- Timestamped Text (`0x04`)
- Timeseries (`0x0B`)

Because this is a reverse‑engineered protocol and new field types may exist, this document intentionally stays at the
"opaque code" level:

- The wire format for the field type is **always 1 byte**.
- Unknown or new values should be treated as opaque and safely skipped or logged.

For precise constants, refer to the `MessageFieldType` definitions in the codebase when implementing a client.

### 3.4. Data

The **Data** (offset `3..N`) is a variable number of bytes determined by the type of message field.

#### 3.4.1. Integer

For **Integer** typed fields, the data is a 32-bit integer (4-bytes). The encoded integer value could be signed or unsigned.
Additionally, in some cases, the 32-bit integer is split into hi and low 16-bit integers.

#### 3.4.2. Timestamped Integer

For **Timestamped Integer** typed fields, the data is 9 bytes with a structure of:

| Offset | Description                                                       |
| ------ | ----------------------------------------------------------------- |
| `0..3` | 32-bit unsigned integer (4-bytes); unix timestamp value           |
| `4`    | Marker (`0xFF`)                                                   |
| `5..8` | 32-bit integer (4-bytes); handled like an [Integer](#341-integer) |

#### 3.4.3 Timestamped Text

For **Timestamped Text** typed fields, the data has a variable length with a structure of:

| Offset   | Description                                             |
| -------- | ------------------------------------------------------- |
| `0..3`   | 32-bit unsigned integer (4-bytes); unix timestamp value |
| `4`      | Marker (`0xFF`)                                         |
| `5..N-1` | utf-8 encoded string bytes                              |
| `N`      | Null byte (`0x00`)                                      |

#### 3.4.4 Timeseries

For **Timeseries** typed fields, the data has a variable length with a structure of:

| Offset    | Description                                             |
| --------- | ------------------------------------------------------- |
| `0..3`    | 32-bit unsigned integer (4-bytes); unix timestamp value |
| `4`       | Marker (`0xFF`)                                         |
| `5..8`    | 32-bit unsigned integer (4-bytes); unix timestamp value |
| `9`       | Marker (`0xFF`)                                         |
| `10`      | Number of 5-byte sample blocks                          |
| `11..N-1` | 5-byte sample blocks (`0xFF` + uint16_hi + uint16_lo)   |
| `N`       | Marker (`0xFF`)                                         |

---

## 4. Request / Response Pattern (TCP)

On the TCP control channel:

1. A client constructs a request `Message`:
   - Chooses a `MessageType`.
   - Builds a payload with the appropriate fields for that operation.
   - Optionally sets a serial number (or uses `0`).
   - Encodes the message using the framing rules above.
2. The message is written to the socket.
3. The client reads a response message from the socket and parses it:
   - Validates preamble, header marker, length, checksum marker, and checksum.
   - Validates that the response `MessageType` matches the expected type.
   - Extracts the payload and interprets it as a set of `MessageFields`.

Common invariants implemented:

- **Type echo / validation:** responses are checked to ensure that the `MessageType` matches the expected value for the request.
- **Length validation:** the `Length` field must be consistent with the actual message size.
- **Checksum validation:** checksum mismatches are treated as fatal for that message.

### 4.1. Example Message (SYSTEM_INFO Request)

The following is a real SYSTEM_INFO request as observed on the wire:

```text
00 00 00 00 00 FF 01 00 00 00 00 00 03 FF 89 B8
```

Breakdown:

- `00 00 00 00 00` – preamble
- `FF` - Header Marker
- `01` – `MessageType.SYSTEM_INFO`
- `00 00 00 00` – serial number = 0
- `00 03` – length = 3 (payload(0) + ChecksumMarker(1) + Checksum(2))
- *(no payload bytes in this request)*
- `FF` – Checksum Marker
- `89 B8` – Checksum over bytes `[0..-3]`

`MessageType.SYSTEM_INFO` responses use the same framing but include a payload containing version and device information
encoded as fields:

```text
    0000000000 FF 01 84B3EE93 0011
    ff 01 01 84B3 EE93   -> Serial Number ( uint32(84B3EE93) = 2226384531 )
    ff 02 01 0001 0015   -> Firmware Version ( int16(0001) . int16(0015) = 1.21 )
    ff 97A3
```

---

## 5. UDP Broadcasts & Discovery

On the UDP broadcast channel:

- Broadcast messages use the **same message structure** and checksum as TCP.
- The Simarine Pico periodically broadcasts messages.
- A client can:
  - Bind to the UDP port,
  - Discover the Pico’s IP address,
  - Listen for valid messages,
  - Parse them using the same `Message` logic,
  - Extract fields and process their values.

This implementation's discovery logic, for example, listens for a single valid broadcast, extracts the sender’s address,
and then opens a TCP control connection to that IP to request system information for the sender.

---

## 6. Error Handling Rules

A message is considered **invalid** and must be dropped if any of the following checks fail:

1. **Preamble**: first 5 bytes must be `00 00 00 00 00`.
2. **Header Marker**: byte at offset 5 must be `0xFF`.
3. **Length check**: the `Length` field must match the number of trailing bytes after the header.
1. **Type check** (when an expected type is known):
   - If the parsed `MessageType` does not match the expected type, the message is treated as a protocol error.
2. **Checksum check**: the checksum field must match the computed checksum over bytes `[0..-3]`.

These validation rules apply identically to both TCP and UDP messages.

---

## 7. Currently Known Interpretations

The following are the currently identified interpretations of the various messages types and message fields.

### 7.1. System Information

Field mapping for System Information (`MessageType = 0x01`) responses:

| Field ID | Type     | Name                    | Description |
| -------- | -------- | ----------------------- | ----------- |
| 1        | uint32   | Serial Number           |             |
| 2        | int16 hi | Major Firmeware Version |             |
| 2        | int16 lo | Minor Firmeware Version |             |

### 7.2. Device & Sensor Count

Field mapping for Device & Sensor Count (`MessageType = 0x02`) responses:

| Field ID | Type  | Name           | Description |
| -------- | ----- | -------------- | ----------- |
| 1        | int32 | Last Device ID |             |
| 2        | int32 | Last Sensor ID |             |

### 7.3. Device Information

Field mapping for Device Information (`MessageType = 0x41`) responses:

| Field ID | Type       | Name              | Description                 |
| -------- | ---------- | ----------------- | --------------------------- |
| 0        | int32      | Device ID         |                             |
| 1        | uint32     | Created Timestamp | When the device was created |
| 1        | int32      | Device Type       | The type of device          |
| 3        | text/int32 | Name/Role         | Normally name of device     |

Interpretation of the remaining fields depend on the device type.

#### 7.3.1. Device Types

The mapping of Device Types:

| Device Type | Name         | Description |
| ----------- | ------------ | ----------- |
| 0           | Null         |             |
| 1           | Voltmeter    |             |
| 2           | Amperemeter  |             |
| 3           | Thermometer  |             |
| 5           | Barometer    |             |
| 6           | Ohmmeter     |             |
| 7           | Time         |             |
| 8           | Tank         |             |
| 9           | Battery      |             |
| 10          | System       |             |
| 13          | Inclinometer |             |

### 7.4. Sensor Information

Field mapping for Sensor Information (`MessageType = 0x20`) responses:

| Field ID | Type  | Name             | Description                         |
| -------- | ----- | ---------------- | ----------------------------------- |
| 1        | int32 | Sensor ID        |                                     |
| 2        | int32 | Sensor Type      | The type of sensor                  |
| 3        | int32 | Device ID        | The parent device ID                |
| 4        | int32 | Device Sensor ID | The ID of the sensor for the device |

Interpretation of the remaining fields depend on the sensor type.

#### 7.4.1. Sensor Types

The mapping of Sensor Types:

| Sensor Type | Name             | Description |
| ----------- | ---------------- | ----------- |
| 0           | None             |             |
| 1           | Voltage          |             |
| 2           | Current          |             |
| 3           | Coulomb Counter  |             |
| 4           | Temperature      |             |
| 5           | Atmosphere       |             |
| 6           | Atmosphere Trend |             |
| 7           | Resistance       |             |
| 10          | Timestamp        |             |
| 11          | State of Charge  |             |
| 13          | Remaining Time   |             |
| 16          | Angle            |             |
| 22          | User             |             |

### 7.5. Sensor State

Field mapping for Sensor State (`MessageType = 0xB0`) responses:

| Field ID | Type         | Name         | Description             |
| -------- | ------------ | ------------ | ----------------------- |
| 1        | int32        | Sensor ID    |                         |
| 2        | int32/uint32 | Sensor State | The state of the sensor |

### 7.5.1. State Interpretations

State interpretation depends on the sensor type:

| Sensor Type      | Description                                  |
| ---------------- | -------------------------------------------- |
| None             |                                              |
| Voltage          | int32 / 1000 = volts                         |
| Current          | int32 / 100 = amps                           |
| Coulomb Counter  | int32 / 1000 = amp hours                     |
| Temperature      | int32 / 10 = celsius                         |
| Atmosphere       | int32 / 100 = millibars                      |
| Atmosphere Trend | int32 / 10 = millibars/hour                  |
| Resistance       | int32 = ohms                                 |
| Timestamp        | uint32 = unix timestamp                      |
| State of Charge  | int16_hi / 160 = percent; int16_lo = unknown |
| Remaining Time   | int32 = seconds                              |
| Angle            | int32 / 10 = degrees                         |
| User             |                                              |

---

## 8. Extensibility & Reverse‑Engineering Notes

Because this protocol is proprietary and only partially documented by the vendor, much of the understanding here comes
from reverse‑engineering:

- The `MessageType` enum will likely grow as additional interactions are discovered.
- New field IDs may appear in existing messages after firmware updates.
- The library is structured so that:
  - Message framing / checksum are handled centrally by the Message object.
  - Field decoding is layered on top and can be extended incrementally.
  - High‑level device/sensor models interpret fields into domain‑specific attributes.

When examining new traffic:

1. Parse messages using the common header + checksum rules above.
2. Capture raw payload bytes per `MessageType`.
3. Interpret payloads as sequences of fields:
   - Identify repeating patterns across messages.
   - Map field IDs to semantic meanings (voltage, current, SoC, etc.).
4. Update the field and type interpretations in the higher‑level models.

This design allows the protocol implementation to evolve without changing the core framing rules described in this document.

---

## 9. Summary

To integrate with a Simarine Pico device using this reverse‑engineered protocol, you need to:

1. Implement the **message framing** exactly as described (preamble, markers, header fields).
2. Compute and verify the **checksum** with polynomial `0x11189`, over the specified byte range.
3. Honour the **length** relationship when building and validating messages.
4. Treat the payload as a **field‑based structure**, where field IDs and encodings are interpreted according to message type.

Everything beyond that (specific message types, field IDs, and physical unit scaling) can evolve independently, as long as
these core framing rules and checksum semantics are preserved.
