import argparse
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Dict, Any, Iterable

from ..client import SimarineClient
from ..types import SimarineObject
from ..protocol import MessageFields


USE_COLOR = sys.stdout.isatty()

COLOR_RED = "\033[31m" if USE_COLOR else ""
COLOR_GREEN = "\033[32m" if USE_COLOR else ""
COLOR_YELLOW = "\033[33m" if USE_COLOR else ""
COLOR_RESET = "\033[0m" if USE_COLOR else ""


# --------------------------------------------------
# Observe command
# --------------------------------------------------


def add_observe_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]):
  observe = subparsers.add_parser("observe", help="Observe changes on a single device or sensor")
  observe_sub = observe.add_subparsers(dest="observe_type", required=True)

  add_observe_device_subcommand(observe_sub)
  add_observe_sensor_subcommand(observe_sub)


def add_common_observe_args(parser: argparse.ArgumentParser):
  parser.add_argument("--host")
  parser.add_argument("--interval", type=float, default=1.0)
  parser.add_argument("--once", action="store_true")
  parser.add_argument("--fields", help="Comma-separated field names or paths (ex: ohms,state_field,fields.18)")
  parser.add_argument("--json", action="store_true", help="Emit diffs as JSON")
  parser.add_argument("--include-unchanged", action="store_true", help="Include unchanged fields in output")
  parser.add_argument("--re-hints", action="store_true", help="Enable automatic RE hints for field behavior")


def add_observe_device_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]):
  parser = subparsers.add_parser("device", help="Observe a device by ID")
  parser.add_argument("device_id", type=int)
  add_common_observe_args(parser)
  parser.set_defaults(func=cmd_observe_device)


def add_observe_sensor_subcommand(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]):
  parser = subparsers.add_parser("sensor", help="Observe a sensor by ID")
  parser.add_argument("sensor_id", type=int)
  add_common_observe_args(parser)
  parser.set_defaults(func=cmd_observe_sensor)


def _parse_field_filter(value: Optional[str]) -> Optional[set[str]]:
  if not value:
    return None
  return {v.strip() for v in value.split(",") if v.strip()}


def cmd_observe_device(args: argparse.Namespace, stop_event: threading.Event):
  field_filter = _parse_field_filter(args.fields)

  with SimarineClient(args.host) as client:

    def getter():
      return client.get_device(args.device_id)

    observer = ObjectObserver(
      stop_event=stop_event,
      getter=getter,
      interval=args.interval,
      field_filter=field_filter,
      json_mode=args.json,
      include_unchanged=args.include_unchanged,
      re_hints=args.re_hints,
    )

    if args.once:
      observer.sample()
    else:
      observer.run()


def cmd_observe_sensor(args: argparse.Namespace, stop_event: threading.Event):
  field_filter = _parse_field_filter(args.fields)

  with SimarineClient(args.host) as client:

    def getter():
      sensor = client.get_sensor(args.sensor_id)
      client.update_sensors_state({sensor.id: sensor})
      return sensor

    observer = ObjectObserver(
      stop_event=stop_event,
      getter=getter,
      interval=args.interval,
      field_filter=field_filter,
      json_mode=args.json,
      include_unchanged=args.include_unchanged,
      re_hints=args.re_hints,
    )

    if args.once:
      observer.sample()
    else:
      observer.run()


# --------------------------------------------------
# Diff model
# --------------------------------------------------


@dataclass
class ObjectDiff:
  before: Dict[str, Any]
  after: Dict[str, Any]
  changes: Dict[str, tuple[Any, Any]]
  unchanged: Dict[str, Any]
  timestamp: float
  hints: Optional[Dict[str, str]] = None


# --------------------------------------------------
# ObjectObserver
# --------------------------------------------------


class ObjectObserver:
  """
  Observe changes on a SimarineObject.

  Features:
    - Getter-based polling
    - Normalized field values
    - Field name/key filtering
    - Colorized diffs or JSON output
    - Optional RE hint generation
  """

  def __init__(
    self,
    stop_event: threading.Event,
    getter: Callable[[], SimarineObject],
    interval: float = 1.0,
    diff_fn: Optional[Callable[[dict, dict], ObjectDiff]] = None,
    on_change: Optional[Callable[[ObjectDiff], None]] = None,
    field_filter: Optional[Iterable[str]] = None,
    json_mode: bool = False,
    include_unchanged: bool = False,
    re_hints: bool = False,
  ):
    self.stop_event = stop_event
    self.getter = getter
    self.interval = interval
    self.diff_fn = diff_fn or self._default_diff
    self.on_change = on_change
    self.field_filter = set(field_filter) if field_filter else None
    self.json_mode = json_mode
    self.include_unchanged = include_unchanged
    self.re_hints = re_hints

    self._previous_state: Optional[Dict[str, Any]] = None
    self._previous_obj: Optional[SimarineObject] = None

  # -------------------------------
  # Normalization
  # -------------------------------

  @classmethod
  def _normalize_value(cls, value):
    """
    Convert nested values to primitives for easier diffing.
    """
    if isinstance(value, SimarineObject):
      return {k: cls._normalize_value(v) for k, v in value.to_dict().items()}

    if isinstance(value, dict):
      normalized = {}
      for k, v in value.items():
        if isinstance(v, MessageFields):
          normalized[str(k)] = cls._normalize_value(v.value)
          continue
        if isinstance(k, int):
          normalized[f"fields.{k}"] = cls._normalize_value(v)
          continue
        normalized[str(k)] = cls._normalize_value(v)
      return normalized

    if isinstance(value, list):
      return [cls._normalize_value(v) for v in value]

    if hasattr(value, "value"):
      try:
        return cls._normalize_value(value.value)
      except Exception:
        pass

    if isinstance(value, bytes):
      return value.hex()

    if isinstance(value, Enum):
      return value.name

    return value

  # -------------------------------
  # Object description
  # -------------------------------

  @staticmethod
  def _format_object(obj: SimarineObject) -> str:
    cls_name = obj.__class__.__name__
    obj_id = getattr(obj, "id", None)
    name = getattr(obj, "name", None)
    obj_type = getattr(obj, "type", None)

    parts = [cls_name]
    if obj_id is not None:
      parts.append(f"#{obj_id}")
    if name:
      parts.append(f'"{name}"')
    if obj_type:
      parts.append(f"(type={obj_type})")

    return " ".join(parts)

  # -------------------------------
  # Hint engine
  # -------------------------------

  def _generate_hints(self, changes: Dict[str, tuple[Any, Any]], unchanged: Dict[str, Any]) -> Dict[str, str]:
    hints: Dict[str, str] = {}

    for key, (old, new) in changes.items():
      # simple hint heuristics
      if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        delta = new - old
        if delta == 0:
          hints[key] = "no change"
        elif abs(delta) < 5:
          hints[key] = "small incremental change"
        elif abs(delta) > 10000:
          hints[key] = "large jump — maybe counter or timestamp"
        else:
          hints[key] = "likely analog measurement"
      else:
        hints[key] = "value changed type/flag"

    return hints

  # -------------------------------
  # Diff logic
  # -------------------------------

  def _default_diff(self, before: dict, after: dict):
    changes = {}
    unchanged = {}

    for key in before.keys() | after.keys():
      old = before.get(key)
      new = after.get(key)

      if self.field_filter and not self._matches_field_filter(key):
        continue

      if old == new:
        if self.include_unchanged:
          unchanged[key] = new
        continue

      changes[key] = (old, new)

    if not changes and not (self.include_unchanged and unchanged):
      return None

    hints = self._generate_hints(changes, unchanged) if self.re_hints else None

    return ObjectDiff(before=before, after=after, changes=changes, unchanged=unchanged, timestamp=time.time(), hints=hints)

  def _matches_field_filter(self, key: str) -> bool:
    key_lower = key.lower()
    for rule in self.field_filter or []:
      rule_lower = rule.lower()
      if rule_lower == key_lower or key_lower.startswith(rule_lower) or rule_lower in key_lower:
        return True
    return False

  # -------------------------------
  # Sampling
  # -------------------------------

  def sample(self):
    obj = self.getter()
    if obj is None:
      return

    raw = obj.to_dict()
    current = self._normalize_value(raw)

    if self._previous_state is not None:
      diff = self.diff_fn(self._previous_state, current)
      if diff:
        self._handle_diff(diff, obj)

    self._previous_state = current
    self._previous_obj = obj

  # -------------------------------
  # Output
  # -------------------------------

  def _handle_diff(self, diff: ObjectDiff, obj: SimarineObject):
    if self.on_change:
      self.on_change(diff)
      return

    if self.json_mode:
      self._emit_json(diff, obj)
      return

    logging.info("==== Simarine Object Change ====")
    logging.info("Object: %s", self._format_object(obj))
    logging.info("Time  : %s", time.strftime("%H:%M:%S", time.localtime(diff.timestamp)))

    for key, (old, new) in diff.changes.items():
      old_str = f"{COLOR_RED}{old}{COLOR_RESET}"
      new_str = f"{COLOR_GREEN}{new}{COLOR_RESET}"
      logging.info("  %-30s %s → %s", key, old_str, new_str)

    if self.include_unchanged and diff.unchanged:
      logging.info("  ---- unchanged ----")
      for key, value in diff.unchanged.items():
        logging.info("  %-30s %s", key, value)

    if self.re_hints and diff.hints:
      logging.info("  ---- hints ----")
      for key, hint in diff.hints.items():
        logging.info("  %-30s %s", key, hint)

  def _emit_json(self, diff: ObjectDiff, obj: SimarineObject):
    data: Dict[str, Any] = {
      "timestamp": diff.timestamp,
      "object": {
        "class": obj.__class__.__name__,
        "id": getattr(obj, "id", None),
        "name": getattr(obj, "name", None),
        "type": str(getattr(obj, "type", None)),
      },
      "changed": {key: {"old": old, "new": new} for key, (old, new) in diff.changes.items()},
      "unchanged": diff.unchanged if self.include_unchanged else {},
    }

    if self.re_hints and diff.hints:
      data["hints"] = diff.hints

    print(json.dumps(data, separators=(",", ":")))

  # -------------------------------
  # Loop control
  # -------------------------------

  def run(self, max_samples=None):
    count = 0

    while not self.stop_event.is_set():
      self.sample()

      count += 1
      if max_samples and count >= max_samples:
        break

      time.sleep(self.interval)
