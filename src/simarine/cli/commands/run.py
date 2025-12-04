import argparse
import json
import threading
import time
from datetime import datetime, timedelta
from enum import Enum

from . import Command
from ...client import SimarineClient


class Run(Command):
  """Continuously poll devices and sensors and emit JSON snapshots"""

  @classmethod
  def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)

  @classmethod
  def run(cls, args: argparse.Namespace, stop_event: threading.Event) -> None:
    with SimarineClient(args.host) as client:
      system_info = client.get_system_info()
      system_device = client.get_system_device()
      devices = client.get_devices()
      sensors = client.get_sensors()

      while not stop_event.is_set():
        client.update_sensors_state(sensors)

        snapshot = {
          "system_info": system_info,
          "system_device": system_device,
          "devices": devices,
          "sensors": sensors,
          "timestamp": time.time(),
        }

        if args.pretty:
          print(json.dumps(snapshot, cls=CustomEncoder, indent=2))
        else:
          print(json.dumps(snapshot, cls=CustomEncoder, separators=(",", ":")))

        time.sleep(args.interval)


# --------------------------------------------------
# JSON Encoder
# --------------------------------------------------


class CustomEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, bytes):
      return obj.hex(" ", 2)
    if isinstance(obj, datetime):
      return obj.isoformat()
    if isinstance(obj, timedelta):
      return str(obj)
    if isinstance(obj, Enum):
      return obj.name
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
      return obj.to_dict()
    return super().default(obj)
