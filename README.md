# Simarine Python Package

A python implementation of the Simarine Pico Message Protocol.

Based on the reverse engineering work of https://github.com/htool/pico2signalk.

For details about the reverse engineered protocol, refer to [PROTOCOL.md](PROTOCOL.md).

## Installation

```sh
pip install git+https://github.com/montaguethomas/simarine-python.git
```

## Usage

A quick example displaying how to import and use the package:
````python
from simarine import SimarineClient

with SimarineClient("192.168.1.1") as client:
  print(client.get_system_info())

  devices = client.get_devices()
  for device in devices:
    print(device)

  sensors = client.get_sensors()
  client.update_sensors_state(sensors)

  for sensor in sensors.values():
    print(sensor)
````
