import argparse
import threading
import time

from . import Monitor
from ....client import SimarineClient, SimarineUDPClient
from ....protocol import Message, MessageType


# --------------------------------------------------
# Pressure command
# --------------------------------------------------


class Pressure(Monitor):
  """Monitor pressure changes"""

  @classmethod
  def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
    super().add_arguments(parser)
    parser.add_argument("--convert", action="store_true")
    parser.add_argument("sensor_id", type=int)

  @classmethod
  def run(cls, args: argparse.Namespace, stop_event: threading.Event) -> None:
    with SimarineClient() as client:

      def handler(message: Message, addr: tuple[str, int]) -> None:
        if message.type != MessageType.ATMOSPHERIC_PRESSURE_HISTORY:
          return

        sensors_state = client.get_sensors_state()
        sensor_state = sensors_state.get(args.sensor_id)
        sensor_value = sensor_state.value
        if args.convert:
          sensor_value = sensor_value / 100

        history_field = message.fields[0]
        history_value = history_field.value[0]
        if args.convert:
          history_value = history_value / 20

        delta = history_value - sensor_value

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] sensor={sensor_value} udp={history_value} delta={delta:+.2f}")

      with SimarineUDPClient(handler):
        while not stop_event.is_set():
          time.sleep(2.0)
