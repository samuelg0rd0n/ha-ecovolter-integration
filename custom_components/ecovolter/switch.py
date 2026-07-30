"""Switch platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
    SwitchDeviceClass,
)

from homeassistant.helpers.entity import EntityCategory

from .const import LOGGER
from .utils import camel_to_snake, get_settings
from .entity import OptimisticEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

# Key is used to get the value from the API
ENTITY_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="isThreePhaseModeEnable",
        translation_key="charging_phase_mode",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="isChargingEnable",
        translation_key="charging_enabled",
        icon="mdi:ev-station",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="isBoostModeEnable",
        translation_key="boost_mode_enabled",
        icon="mdi:lightning-bolt",
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key="isLocalPanelEnable",
        translation_key="local_panel_enabled",
        icon="mdi:monitor-lock",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
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


class IntegrationEcovolterSwitch(OptimisticEcovolterEntity, SwitchEntity):
    """ecovolter switch class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return camel_to_snake(self.entity_description.key)

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "isThreePhaseModeEnable":
            return "mdi:numeric-3-circle" if self.is_on else "mdi:numeric-1-circle"
        return super().icon

    def _device_value(self) -> bool | None:
        """Raw coordinator value normalized to the optimistic (bool) domain."""
        val = get_settings(self.coordinator).get(self.entity_description.key)
        return None if val is None else bool(val)

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self._optimistic_set:
            return bool(self._optimistic_value)
        return self._device_value()

    async def _async_write(self, value: bool) -> None:
        """Write a bool setting, suppressing a no-op PATCH.

        PATCH first; only set optimistic on success. If it raises, let it
        propagate — HA surfaces the error and the property falls back to
        coordinator data.
        """
        if self._is_no_op_write(value):
            LOGGER.debug(
                "Skipping no-op write for %s: %s already in effect",
                self.entity_id,
                value,
            )
            return

        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {self.entity_description.key: value}
        )
        self._apply_optimistic(value)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **_: Any) -> None:
        """Turn on the switch."""
        await self._async_write(True)

    async def async_turn_off(self, **_: Any) -> None:
        """Turn off the switch."""
        await self._async_write(False)
