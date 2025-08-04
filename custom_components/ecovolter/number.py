"""Number platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import UnitOfElectricCurrent

from .const import DOMAIN
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import IntegrationEcovolterConfigEntry

ENTITY_DESCRIPTIONS = (
    NumberEntityDescription(
        key="target_current",
        name="Target Current",
        icon="mdi:current-dc",
        native_min_value=6,
        native_max_value=16,
        native_step=1,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntegrationEcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    async_add_entities(
        IntegrationEcovolterNumber(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationEcovolterNumber(IntegrationEcovolterEntity, NumberEntity):
    """ecovolter number class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initialize the number class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_name = entity_description.name

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return f"{DOMAIN}_{self.entity_description.key}"

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return self.coordinator.data.get("settings", {}).get("targetCurrent", 6)

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {"targetCurrent": int(value)}
        )
        await self.coordinator.async_request_refresh()
