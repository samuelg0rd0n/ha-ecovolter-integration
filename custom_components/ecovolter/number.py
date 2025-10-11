"""Number platform for ecovolter."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    cast
)


from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberDeviceClass,
)

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfTime,
    UnitOfEnergy,
)

from homeassistant.helpers.entity import EntityCategory

from .utils import camel_to_snake
from .const import (
    KEY_SETTINGS,
    KEY_TYPE_INFO,
    MIN_CURRENT,
    MAX_CURRENT,
    CHARGER_TYPE_MAX_CURRENT,
    CURRENCY_MAP,
)
from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

# Key is used to get the value from the API
ENTITY_DESCRIPTIONS: tuple[NumberEntityDescription, ...]  = (
    NumberEntityDescription(
        key="targetCurrent",
        translation_key="target_current",
        icon="mdi:current-ac",
        native_min_value=MIN_CURRENT,
        native_max_value=MAX_CURRENT,
        native_step=1,
        device_class=NumberDeviceClass.CURRENT,        
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    NumberEntityDescription(
        key="boostCurrent",
        translation_key="boost_current",
        icon="mdi:lightning-bolt",
        native_min_value=MIN_CURRENT,
        native_max_value=MAX_CURRENT,
        native_step=1,
        device_class=NumberDeviceClass.CURRENT,        
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    NumberEntityDescription(
        key="maxCurrent",
        translation_key="max_current",
        icon="mdi:lightning-bolt-outline",
        native_min_value=MIN_CURRENT,
        native_max_value=MAX_CURRENT,
        native_step=1,
        device_class=NumberDeviceClass.CURRENT,        
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    NumberEntityDescription(
        key="boostTime",
        translation_key="boost_time",
        icon="mdi:clock-fast",
        native_min_value=0,
        native_max_value=86340,  # 23 hours, 59 minutes
        native_step=60,  # 1-minute resolution
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
    NumberEntityDescription(
        key="kwhPrice",
        translation_key="energy_price",
        icon="mdi:cash-multiple",
        native_min_value=0.0,
        native_max_value=999.99,
        native_step=0.01,
        entity_category=EntityCategory.CONFIG,
    ),
)

CURRENT_KEYS = {"targetCurrent", "boostCurrent"}

async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
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
            f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"
        )

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return camel_to_snake(self.entity_description.key)

    @property
    def native_max_value(self) -> float:
        """Dynamic max for target/boost current based on maxCurrent setting."""
        desc_max = cast(float, self.entity_description.native_max_value)
        key = self.entity_description.key

        # maxCurrent needs to be capped by charger type max current
        if key == "maxCurrent":
            type_info = self.coordinator.data.get(KEY_TYPE_INFO) or {}
            charger_type = type_info.get("chargerType")
            type_max = CHARGER_TYPE_MAX_CURRENT.get(charger_type, MAX_CURRENT) if isinstance(charger_type, int) else MAX_CURRENT

            return (float(type_max))

        # For current-related entities, cap by maxCurrent if available
        if key in CURRENT_KEYS:
            # Use charger type limit if available
            type_info = self.coordinator.data.get(KEY_TYPE_INFO) or {}
            charger_type = type_info.get("chargerType")
            type_max = CHARGER_TYPE_MAX_CURRENT.get(charger_type, MAX_CURRENT) if isinstance(charger_type, int) else MAX_CURRENT

            # Use maxCurrent setting if defined and lower than type_max
            dynamic_max = self.coordinator.data.get(KEY_SETTINGS, {}).get("maxCurrent")

            if isinstance(dynamic_max, (int, float)):
                return float(min(dynamic_max, type_max))
            return float(type_max)

        return desc_max

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.coordinator.data.get(KEY_SETTINGS, {}).get(self.entity_description.key)
        return None if value is None else float(value)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement for the entity."""
        if self.entity_description.key == "kwhPrice":
            currency_raw = self.coordinator.data.get(KEY_SETTINGS, {}).get("currency")
            currency_id = cast(int | None, currency_raw if isinstance(currency_raw, int) else None)
            iso = CURRENCY_MAP.get(currency_id or -1, "EUR")
            return f"{iso}/{UnitOfEnergy.KILO_WATT_HOUR}"
        return self.entity_description.native_unit_of_measurement

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        key = self.entity_description.key

        # For current-related entities, clamp dynamic limits
        if key in CURRENT_KEYS:
            min_v = float(self.entity_description.native_min_value or MIN_CURRENT)
            max_v = self.native_max_value
            value = int(max(min_v, min(value, max_v)))
        # For energy price, round to two decimals
        elif key == "kwhPrice":
            value = round(float(value), 2)
        else:
            value = int(value)

        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {key: value}
        )
        await self.coordinator.async_request_refresh()
