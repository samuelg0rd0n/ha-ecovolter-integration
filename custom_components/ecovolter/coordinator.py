"""DataUpdateCoordinator for ecovolter."""

from __future__ import annotations

from datetime import timedelta
from logging import Logger
from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
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
    LOGGER,
    MAX_CONSECUTIVE_FAILURES,
    WRITE_REFRESH_DEBOUNCE_SECONDS,
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
    _consecutive_failures: int = 0

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator with a debounced post-write refresh.

        ``async_request_refresh()`` (the debounced path, used by the write
        sites) coalesces a burst of writes into one read-back poll
        ``WRITE_REFRESH_DEBOUNCE_SECONDS`` after the last write. The
        coordinator wires ``function=self._async_refresh`` onto the supplied
        debouncer itself.
        """
        super().__init__(
            hass=hass,
            logger=logger,
            name=name,
            update_interval=update_interval,
            request_refresh_debouncer=Debouncer(
                hass,
                logger,
                cooldown=WRITE_REFRESH_DEBOUNCE_SECONDS,
                immediate=False,
            ),
        )

    @property
    def data_is_fresh(self) -> bool:
        """True only right after a real successful poll.

        False while serving tolerated-stale data, so the optimistic layer
        never confirms or times out an optimistic value against stale data.
        """
        return self._consecutive_failures == 0

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
            # Auth failures are never tolerated; the counter is left untouched.
            raise ConfigEntryAuthFailed(exception) from exception
        except EcovolterApiClientError as exception:
            self._consecutive_failures += 1
            # Serve last-good data through the first MAX_CONSECUTIVE_FAILURES
            # failures so a single slow response doesn't blip every entity to
            # unavailable. The ``self.data is None`` guard ensures a failure
            # during async_config_entry_first_refresh still raises (and HA
            # surfaces ConfigEntryNotReady) rather than returning empty data.
            if (
                self._consecutive_failures <= MAX_CONSECUTIVE_FAILURES
                and self.data is not None
            ):
                LOGGER.warning(
                    "EcoVolter poll failed (%s/%s), keeping last good data: %s",
                    self._consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                    exception,
                )
                return self.data
            raise UpdateFailed(exception) from exception
        else:
            self._consecutive_failures = 0
            data: DataType = {
                KEY_STATUS: status,
                KEY_SETTINGS: settings,
                KEY_DIAGNOSTICS: diagnostics,
                KEY_TYPE_INFO: self._type_info_cache,
            }
            return data
