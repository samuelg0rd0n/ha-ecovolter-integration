"""Custom integration to integrate ecovolter with Home Assistant."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import EcovolterApiClient
from .const import (
    DOMAIN,
    LOGGER,
    CONF_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    CONF_BASE_URI,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
)
from .coordinator import EcovolterDataUpdateCoordinator
from .data import EcovolterData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from .data import EcovolterConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
) -> bool:
    """Set up this integration using UI."""

    # 1) Resolve the polling interval (options > data > default)
    raw_interval = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS),
    )
    try:
        interval_seconds = int(raw_interval)
    except (TypeError, ValueError):
        interval_seconds = DEFAULT_UPDATE_INTERVAL_SECONDS

    # Clamp to a sensible minimum
    interval_seconds = max(interval_seconds, MIN_UPDATE_INTERVAL_SECONDS)

    coordinator = EcovolterDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(seconds=int(interval_seconds)),
    )

    # 2) Build the API client (base_uri is optional → .get)
    client = EcovolterApiClient(
        serial_number=entry.data[CONF_SERIAL_NUMBER],
        secret_key=entry.data[CONF_SECRET_KEY],
        base_uri=entry.data.get(CONF_BASE_URI),
        session=async_get_clientsession(hass),
    )

    # 3) Stash runtime objects for platforms
    entry.runtime_data = EcovolterData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # 4) First refresh, then set up platforms
    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 5) Reload the entry if options change (eg. user tweaks interval)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True

async def async_unload_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

async def async_reload_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
