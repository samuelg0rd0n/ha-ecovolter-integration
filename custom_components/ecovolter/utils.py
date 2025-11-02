import re

from typing import (
    Any,
    Mapping,
)

from .const import (
    KEY_STATUS,
    KEY_SETTINGS,
    KEY_DIAGNOSTICS,
    KEY_TYPE_INFO,
    MAX_CURRENT,
    CHARGER_TYPE_MAX_CURRENT,
)


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


# Safe conversions


def as_float(val: Any) -> float | None:
    """Convert any numeric-like value to float safely."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val)
        except ValueError:
            return None
    return None


def as_int(val: Any) -> int | None:
    """Convert any integer-like value to int safely."""
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    if isinstance(val, str):
        try:
            return int(float(val))
        except ValueError:
            return None
    return None


# Access to Coordinator data


def get_section(data: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    return dict(data.get(key) or {}) if isinstance(data, Mapping) else {}


def get_status(coordinator) -> dict[str, Any]:
    return get_section(coordinator.data, KEY_STATUS)


def get_settings(coordinator) -> dict[str, Any]:
    return get_section(coordinator.data, KEY_SETTINGS)


def get_diagnostics(coordinator) -> dict[str, Any]:
    return get_section(coordinator.data, KEY_DIAGNOSTICS)


def get_type_info(coordinator) -> dict[str, Any]:
    return get_section(coordinator.data, KEY_TYPE_INFO)


def extract_temperature(status: dict[str, Any], key: str) -> float | None:
    """Extract temperatures from the device status section."""
    temps = status.get("temperatures", {})
    if key == "temperature_internal":
        val = temps.get("internal")
    elif key.startswith("temperature_adapter"):
        idx = int(key[-1]) - 1
        val = temps.get("adapter", [None])[idx]
    elif key.startswith("temperature_relay"):
        idx = int(key[-1]) - 1
        val = temps.get("relay", [None])[idx]
    else:
        val = None

    return as_float(val)


def get_charger_type_maximum_charging_current(coordinator) -> int:
    """Get maximum charging current for this charger type."""
    type_info = get_type_info(coordinator)
    charger_type = type_info.get("chargerType")
    type_max = (
        CHARGER_TYPE_MAX_CURRENT.get(charger_type, MAX_CURRENT)
        if isinstance(charger_type, int)
        else MAX_CURRENT
    )
    return type_max


def clamp_int(value: int, lo: int, hi: int) -> int:
    """Clamp an integer value to always be between lo and hi."""
    return max(lo, min(value, hi))
