"""
unit_converter.core — UI-independent conversion logic.

Exposes the three-function public API used by the GUI, REST layer, and MCP layer:
    list_magnitudes()
    list_units(magnitude)
    convert(magnitude, value, from_unit, to_unit, from_order, to_order)
"""

from unit_converter.core.converter import list_magnitudes, list_units, convert

__all__ = ["list_magnitudes", "list_units", "convert"]
