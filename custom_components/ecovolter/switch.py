"""Switch platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription

from .utils import camel_to_snake
from .const import (
    DOMAIN,
    KEY_SETTINGS,
)
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

# Key is used to get the value from the API
ENTITY_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="isThreePhaseModeEnable",
        translation_key="three_phase_mode_enabled",
        icon="mdi:numeric-3-circle",
    ),
    SwitchEntityDescription(
        key="isChargingEnable",
        translation_key="charging_enabled",
        icon="mdi:ev-station",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    async_add_entities(
        IntegrationEcovolterSwitch(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )


class IntegrationEcovolterSwitch(IntegrationEcovolterEntity, SwitchEntity):
    """ecovolter switch class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch class."""
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
        """Return true if the switch is on."""
        return self.coordinator.data.get(KEY_SETTINGS, {}).get(
            self.entity_description.key, False
        )

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {self.entity_description.key: True}
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {self.entity_description.key: False}
        )
        await self.coordinator.async_request_refresh()
