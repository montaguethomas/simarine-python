import argparse
from datetime import datetime
import logging
import threading

import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np

from . import Graph
from ....client import SimarineUDPClient
from ....protocol import Message, MessageType


# --------------------------------------------------
# PressureHistory command
# --------------------------------------------------


class PressureHistory(Graph):
  """Graph atmospheric pressure history"""

  @classmethod
  def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
    super().add_arguments(parser)
    parser.add_argument("--convert", action="store_true")

  @classmethod
  def run(cls, args: argparse.Namespace, stop_event: threading.Event) -> None:
    fig, ax = plt.subplots()

    ax.set_title("Atmospheric Pressure (mbar)")
    timestamp = ax.text(
      0.5,
      0.92,
      "",
      horizontalalignment="center",
      verticalalignment="center",
      transform=ax.transAxes,
      fontsize=12,
      color="gray",
    )

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Pressure (mbar)")

    # Grid styling
    ax.grid(which="major", linestyle="-", linewidth=0.8)
    ax.grid(which="minor", linestyle=":", linewidth=0.5, alpha=0.5)

    ax.xaxis.set_major_locator(MultipleLocator(12))  # Major ticks: every 12 hours
    ax.xaxis.set_minor_locator(MultipleLocator(2))  # Minor ticks: every 2 hours

    # ax.legend()

    # start with empty data
    (line,) = ax.plot([], [], label="Pressure")

    latest_value = None
    window_hours = 72

    def handler(message: Message, addr: tuple[str, int]) -> None:
      nonlocal latest_value

      if message.type != MessageType.ATMOSPHERIC_PRESSURE_HISTORY:
        return

      history_field = message.fields[0]
      history_values = history_field.value

      # Skip if timeseries hasn't updated
      if latest_value == history_values[0]:
        return
      latest_value = history_values[0]
      logging.info("Received updated history values")

      timestamp.set_text(datetime.fromtimestamp(history_field.timestamp))

      history_values = list(reversed(history_values))
      if args.convert:
        history_values = list(map(lambda v: v * 0.05, history_values))

      # Time axis from -window_hours to 0
      t = np.linspace(-window_hours, 0, len(history_values))

      # Update line data
      line.set_xdata(t)
      line.set_ydata(history_values)

    def tick():
      if stop_event.is_set():
        plt.close(fig)

      # Rescale axes to fit new data
      ax.relim()
      ax.autoscale_view()

      # Force redraw
      fig.canvas.draw()
      fig.canvas.flush_events()

    timer = fig.canvas.new_timer(interval=1000)
    timer.add_callback(tick)
    timer.start()

    with SimarineUDPClient(handler):
      plt.show()
