import argparse
import logging

from .commands.observe import add_observe_subcommand
from .commands.run import add_run_subcommand


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
