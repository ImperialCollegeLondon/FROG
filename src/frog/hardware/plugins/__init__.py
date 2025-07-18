"""Plugins for the hardware module."""

import sys
from collections.abc import Iterable
from importlib import import_module
from pkgutil import iter_modules
from types import ModuleType


def _import_recursively(module: ModuleType) -> Iterable[str]:
    """Recursively import module's submodules.

    Yields the names of the imported packages.
    """
    if not hasattr(module, "__path__"):
        return

    for modinfo in iter_modules(module.__path__):
        package = f"{module.__name__}.{modinfo.name}"
        yield package
        yield from _import_recursively(import_module(package))


def load_all_plugins() -> list[str]:
    """Load all the device types from this module and its submodules.

    Returns:
        A list of imported plugins
    """
    return list(_import_recursively(sys.modules[__name__]))
