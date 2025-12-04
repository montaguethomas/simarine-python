"""
Simarine CLI
"""

import logging
import signal
import threading

from . import commands


def main():
  """
  Entry point for the Simarine CLI.
  Builds the full command parser and dispatches to the appropriate handler.
  """
  stop_event = threading.Event()

  def handle_interrupt(signum, frame):
    logging.info("Interrupt received, shutting down...")
    stop_event.set()

  signal.signal(signal.SIGINT, handle_interrupt)
  signal.signal(signal.SIGTERM, handle_interrupt)

  parser = commands.Command.build_parser(description="Simarine CLI")
  args = parser.parse_args()

  loglevel = logging.DEBUG if args.debug else logging.INFO
  logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(message)s")

  try:
    args.handler(args, stop_event)
  except KeyboardInterrupt:
    logging.info("Exiting.")
