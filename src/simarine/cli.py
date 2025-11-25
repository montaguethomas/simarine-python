import argparse
import json
import logging
import time
from datetime import datetime
from enum import Enum

from .client import SimarineClient
from .commands.observer import add_observe_subcommand


# --------------------------------------------------
# main
# --------------------------------------------------


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("--debug", action="store_true")
  subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

  add_observe_subcommand(subparsers)
  add_run_subcommand(subparsers)

  args = parser.parse_args()

  loglevel = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(message)s")

  args.func(args)


# --------------------------------------------------
# JSON Encoder
# --------------------------------------------------


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


# --------------------------------------------------
# Commands
# --------------------------------------------------


def add_run_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]):
  parser = subparsers.add_parser("run", help="Continuously poll devices and sensors and emit JSON snapshots")
  parser.add_argument("--host")
  parser.add_argument("--pretty", action="store_true")
  parser.add_argument("--interval", type=float, default=5.0)
  parser.set_defaults(func=cmd_run)


def cmd_run(args: argparse.Namespace):
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
