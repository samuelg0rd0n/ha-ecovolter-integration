"""Constants for ecovolter."""

from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ecovolter"
ATTRIBUTION = "Data provided by EcoVolter charger"

CONF_SERIAL_NUMBER = "serial_number"
CONF_SECRET_KEY = "secret_key"
CONF_BASE_URI = "base_uri"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL_SECONDS = 15
MIN_UPDATE_INTERVAL_SECONDS = 5

MIN_CURRENT = 6
MAX_CURRENT = 16

KEY_STATUS: Final = "status"
KEY_SETTINGS: Final = "settings"

CURRENCY_MAP: dict[int, str] = {
    0: "EUR",
    1: "CZK",
    2: "USD",
    3: "GBP",
    4: "HUF",
    5: "PLN",
    6: "RSD",
    7: "SEK",
    8: "TRL",
    9: "BAM",
    10: "BGN",
    11: "CHF",
    12: "DKK",
    13: "ISK",
    14: "NOK",
}

# Reverse currency map
CURRENCY_INV_MAP: dict[str, int] = {v: k for k, v in CURRENCY_MAP.items()}