"""Sensor platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription

from .const import DOMAIN
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import IntegrationEcovolterConfigEntry

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="is_charging",
        name="Is Charging?",
        icon="mdi:format-quote-close",
    ),
    SensorEntityDescription(
        key="is_vehicle_connected",
        name="Is Vehicle Connected?",
        icon="mdi:format-quote-close",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_entities(
        IntegrationEcovolterSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationEcovolterSensor(IntegrationEcovolterEntity, SensorEntity):
    """ecovolter Sensor class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return f"{DOMAIN}_{self.entity_description.key}"

    @property
    def native_value(self) -> str | None:
        """Return the native value of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)
