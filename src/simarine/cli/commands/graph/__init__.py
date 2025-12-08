import importlib
import pathlib
import pkgutil

from .. import Command


# --------------------------------------------------
# Graph commands
# --------------------------------------------------


class Graph(Command):
  """Generate graph"""


# --------------------------------------------------
# Automatic Import
# --------------------------------------------------

pkg_dir = pathlib.Path(__file__).parent

for module in pkgutil.iter_modules([str(pkg_dir)]):
  importlib.import_module(f"{__name__}.{module.name}")
