"""EcovolterEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTRIBUTION,
    DOMAIN,
    CONF_SERIAL_NUMBER,
)
from .coordinator import EcovolterDataUpdateCoordinator


class IntegrationEcovolterEntity(CoordinatorEntity[EcovolterDataUpdateCoordinator]):
    """EcovolterEntity class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True  # let HA compose "<Device name> <Entity name>"

    def __init__(self, coordinator: EcovolterDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        serial = coordinator.config_entry.data.get(CONF_SERIAL_NUMBER) or "unknown"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            manufacturer="EcoVolter",
            model="EcoVolter II",  # change if you detect model dynamically
            name=f"EcoVolter ({serial})",  # -> shows up instead of "undefined"
        )
