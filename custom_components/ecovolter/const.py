"""Constants for ecovolter."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "ecovolter"
ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"

CONF_SERIAL_NUMBER = "serial_number"
CONF_SECRET_KEY = "secret_key"
CONF_BASE_URI = "base_uri"
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UPDATE_INTERVAL_SECONDS = 15
MIN_UPDATE_INTERVAL_SECONDS = 5