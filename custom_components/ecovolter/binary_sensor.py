"""Binary sensor platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .utils import camel_to_snake
from .const import (
    DOMAIN,
    KEY_STATUS,
)
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

# Key is used to get the value from the API
ENTITY_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="isCharging",
        name="Is Charging?",
        icon="mdi:ev-station",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    BinarySensorEntityDescription(
        key="isVehicleConnected",
        name="Is Vehicle Connected?",
        icon="mdi:ev-plug-type2",
        device_class=BinarySensorDeviceClass.PLUG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
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
            f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"
        )

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return f"{DOMAIN}_{camel_to_snake(self.entity_description.key)}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self.coordinator.data.get(KEY_STATUS, {}).get(
            self.entity_description.key, False
        )
