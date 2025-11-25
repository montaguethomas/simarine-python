import argparse
import json
import logging
import time
from datetime import datetime
from enum import Enum

from .client import SimarineClient


# --------------------------------------------------
# cli / main
# --------------------------------------------------


# JSON Encoder
class CustomEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, bytes):
      return obj.hex(" ", 2)
    if isinstance(obj, datetime):
      return obj.isoformat()
    if isinstance(obj, Enum):
      return obj.name
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
      return obj.to_dict()
    return super().default(obj)


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--host", required=True)
  ap.add_argument("--pretty", action="store_true")
  ap.add_argument("--debug", action="store_true")
  ap.add_argument("--interval", type=float, default=5.0)
  args = ap.parse_args()

  loglevel = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(message)s")

  with SimarineClient(args.host) as client:
    devices = client.get_devices()
    sensors = client.get_sensors()

    while True:
      client.update_sensors_state(sensors)

      snapshot = {
        "devices": devices,
        "sensors": sensors,
        "timestamp": time.time(),
      }

      if args.pretty:
        print(json.dumps(snapshot, cls=CustomEncoder, indent=2))
      else:
        print(json.dumps(snapshot, cls=CustomEncoder, separators=(",", ":")))

      time.sleep(args.interval)
