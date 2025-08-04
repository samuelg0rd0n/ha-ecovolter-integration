"""Custom integration to integrate ecovolter with Home Assistant.

For more details about this integration, please refer to
https://github.com/ludeeus/ecovolter
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import IntegrationEcovolterApiClient
from .const import DOMAIN, LOGGER, SECRET_KEY, SERIAL_NUMBER
from .coordinator import EcovolterDataUpdateCoordinator
from .data import IntegrationEcovolterData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import IntegrationEcovolterConfigEntry

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.NUMBER, Platform.BINARY_SENSOR]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = EcovolterDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(seconds=30),
    )
    entry.runtime_data = IntegrationEcovolterData(
        client=IntegrationEcovolterApiClient(
            serial_number=entry.data[SERIAL_NUMBER],
            secret_key=entry.data[SECRET_KEY],
            session=async_get_clientsession(hass),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
