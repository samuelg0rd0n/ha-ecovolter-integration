"""DataUpdateCoordinator for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientError,
)

from .const import (
    KEY_STATUS,
    KEY_SETTINGS,
    KEY_DIAGNOSTICS,
    KEY_TYPE_INFO,
)

if TYPE_CHECKING:
    from .data import EcovolterConfigEntry


class DataType(TypedDict):
    """Data type for coordinator."""

    status: dict[str, Any]
    settings: dict[str, Any]
    diagnostics: dict[str, Any]
    type_info: dict[str, Any]


# https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
class EcovolterDataUpdateCoordinator(DataUpdateCoordinator[DataType]):
    """Class to manage fetching data from the API."""

    config_entry: EcovolterConfigEntry

    _type_info_cache: dict[str, Any] | None = None

    async def _async_update_data(self) -> DataType:
        """Update data via library."""
        try:
            status = (
                await self.config_entry.runtime_data.client.async_get_status()
            )  # /api/v1/charger/status
            settings = (
                await self.config_entry.runtime_data.client.async_get_settings()
            )  # /api/v1/charger/settings
            diagnostics = (
                await self.config_entry.runtime_data.client.async_get_diagnostics()
            )  # /api/v1/charger/diagnostic

            # fetch type info once and cache
            if self._type_info_cache is None:
                self._type_info_cache = (
                    await self.config_entry.runtime_data.client.async_get_type()
                )  # /api/v1/charger/type

        except EcovolterApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except EcovolterApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            data: DataType = {
                KEY_STATUS: status,
                KEY_SETTINGS: settings,
                KEY_DIAGNOSTICS: diagnostics,
                KEY_TYPE_INFO: self._type_info_cache,
            }
            return data
