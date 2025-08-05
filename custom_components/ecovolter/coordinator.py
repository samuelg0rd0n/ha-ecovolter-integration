"""DataUpdateCoordinator for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientError,
)

if TYPE_CHECKING:
    from .data import EcovolterConfigEntry


class DataType(TypedDict):
    """Data type for coordinator."""

    status: dict[str, Any]
    settings: dict[str, Any]


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class EcovolterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: EcovolterConfigEntry

    async def _async_update_data(self) -> DataType:
        """Update data via library."""
        try:
            status = (
                await self.config_entry.runtime_data.client.async_get_status()
            )  # /api/v1/charger/status
            settings = (
                await self.config_entry.runtime_data.client.async_get_settings()
            )  # /api/v1/charger/settings
        except EcovolterApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EcovolterApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return {
                "status": status,
                "settings": settings,
            }
