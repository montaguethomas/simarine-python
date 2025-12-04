from __future__ import annotations

import argparse
import importlib
import pathlib
import pkgutil
import threading
from typing import ClassVar


class Command:
  """
  Base class for all CLI commands.

  - Subclasses auto-register themselves and inherit their parent's path.
  - `Command.build_root_parser()` builds the whole argparse command tree.
  - `Command.build_subparser()` builds command subtrees recursively.
  """

  registry: ClassVar[dict[tuple[str, ...], type[Command]]] = {}
  """Registry of subclasses mapping path -> subclass"""

  children: ClassVar[dict[tuple[str, ...], list[tuple[str, ...]]]] = {}
  """Map of child classes"""

  path: ClassVar[tuple[str, ...]]
  """Command path"""

  def __init_subclass__(cls, **kwargs) -> None:
    super().__init_subclass__(**kwargs)

    if cls is Command:
      return

    base = cls.__bases__[0]
    name = cls.__name__.lower()

    cls.path = (*base.path, name) if getattr(base, "path", None) else (name,)
    Command.registry[cls.path] = cls

    parent_path = cls.path[:-1]
    Command.children.setdefault(parent_path, []).append(cls.path)

  @classmethod
  def build_parser(cls, **kwargs) -> argparse.ArgumentParser:
    """
    Build and return the full argparse parser.
    """
    parser = argparse.ArgumentParser(**kwargs)
    subparsers = parser.add_subparsers(dest="command", title="commands", required=True)

    # top-level commands are those with a single segment path
    roots = [p for p in cls.registry if len(p) == 1]

    for path in sorted(roots):
      command_cls = cls.registry[path]
      command_cls.build_subparser(subparsers)

    return parser

  @classmethod
  def build_subparser(cls, parent_subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> argparse.ArgumentParser:
    """
    Create a subparser for this command under the given parent_subparsers.
    Recursively adds child commands.
    """

    segment = cls.path[-1]
    help_text = (cls.__doc__ or "").strip() or None

    parser = parent_subparsers.add_parser(segment, help=help_text)

    if cls.path in Command.children:
      # group command
      subparser = parser.add_subparsers(dest=f"{segment}_command", title=f"{segment} commands", required=True)

      for child_path in sorted(Command.children[cls.path]):
        child_cls = Command.registry[child_path]
        child_cls.build_subparser(subparser)

    else:
      # leaf command
      cls.add_arguments(parser)
      parser.set_defaults(handler=cls.run)

    return parser

  @classmethod
  def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
    """Override in subclasses to define arguments."""
    parser.add_argument("--debug", action="store_true")

  @classmethod
  def run(cls, args: argparse.Namespace, stop_event: threading.Event) -> None:
    """Override in subclasses to implement the command."""
    raise NotImplementedError("Leaf commands must implement run()")


# --------------------------------------------------
# Automatic Import
# --------------------------------------------------

pkg_dir = pathlib.Path(__file__).parent

for module in pkgutil.iter_modules([str(pkg_dir)]):
  importlib.import_module(f"{__name__}.{module.name}")
