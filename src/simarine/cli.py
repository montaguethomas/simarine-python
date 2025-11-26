import argparse
import logging
import signal
import threading

from .commands.observe import add_observe_subcommand
from .commands.run import add_run_subcommand


# --------------------------------------------------
# main
# --------------------------------------------------


def main():
  stop_event = threading.Event()

  def handle_interrupt(signum, frame):
    logging.info("Interrupt received, shutting down...")
    stop_event.set()

  signal.signal(signal.SIGINT, handle_interrupt)
  signal.signal(signal.SIGTERM, handle_interrupt)

  parser = argparse.ArgumentParser()
  parser.add_argument("--debug", action="store_true")
  subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

  add_observe_subcommand(subparsers)
  add_run_subcommand(subparsers)

  args = parser.parse_args()

  loglevel = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(message)s")

  try:
    args.func(args, stop_event)
  except KeyboardInterrupt:
    logging.info("Exiting.")
