from __future__ import annotations


class UnitDimensionError(ValueError):
    pass


_DIMENSIONS = {
    "m": "length",
    "cm": "length",
    "mm": "length",
    "km": "length",
    "s": "time",
    "m/s": "velocity",
    "m/s^2": "acceleration",
    "kg": "mass",
    "N": "force",
    "W": "power",
    "Pa": "pressure",
    "K": "temperature",
    "A": "current",
    "T": "magnetic_flux_density",
    "1": "dimensionless",
}


def dimension(unit: str) -> str:
    try:
        return _DIMENSIONS[unit]
    except KeyError as exc:
        raise UnitDimensionError(f"unsupported_unit:{unit}") from exc


def validate_dimensions(left_unit: str, right_unit: str) -> None:
    if dimension(left_unit) != dimension(right_unit):
        raise UnitDimensionError(f"dimension_mismatch:{left_unit}:{right_unit}")
