"""Binary sensor platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .const import DOMAIN
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import IntegrationEcovolterConfigEntry

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="is_charging",
        name="Is Charging?",
        icon="mdi:battery-charging-60",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="is_vehicle_connected",
        name="Is Vehicle Connected?",
        icon="mdi:ev-plug-type2",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        IntegrationEcovolterBinarySensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationEcovolterBinarySensor(IntegrationEcovolterEntity, BinarySensorEntity):
    """ecovolter binary_sensor class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary_sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"v2{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_name = entity_description.name

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return f"{DOMAIN}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self.coordinator.data.get("settings", {}).get(
            self.entity_description.key, False
        )
