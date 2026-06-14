"""
unit_converter — pure Python unit conversion package.

The top-level package re-exports the public API surface of the core sub-package
so callers can use either::

    from unit_converter.core.converter import list_magnitudes, list_units, convert
    # or the short form:
    from unit_converter import list_magnitudes, list_units, convert

License: GPLv3
"""

from unit_converter.core.converter import list_magnitudes, list_units, convert

__all__ = ["list_magnitudes", "list_units", "convert"]
__version__ = "1.1.0"
__author__ = "Juan Garcia Sanchez"
__license__ = "GPLv3"
