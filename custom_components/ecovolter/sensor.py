"""Sensor platform for ecovolter."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

from homeassistant.const import (
    UnitOfTime,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)

from homeassistant.helpers.entity import EntityCategory

from .utils import (
    camel_to_snake,
    as_float,
    get_status,
    get_settings,
    get_diagnostics,
    get_type_info,
    extract_temperature,
)
from .const import (
    CURRENCY_MAP,
    CHARGER_TYPE_LABELS,
)

from .entity import IntegrationEcovolterEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

# Key is used to get the value from the API
ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        key="chargedEnergy",
        translation_key="charged_energy",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="chargingCost",
        translation_key="charging_cost",
        icon="mdi:cash",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
    ),
    SensorEntityDescription(
        key="chargingTime",
        translation_key="charging_time",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="remainingBoostTime",
        translation_key="remaining_boost_time",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="actualPower",
        translation_key="actual_power",
        icon="mdi:flash",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="currentL1",
        translation_key="current_l1",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="currentL2",
        translation_key="current_l2",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="currentL3",
        translation_key="current_l3",
        icon="mdi:current-ac",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="voltageL1",
        translation_key="voltage_l1",
        icon="mdi:flash-triangle-outline",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="voltageL2",
        translation_key="voltage_l2",
        icon="mdi:flash-triangle-outline",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="voltageL3",
        translation_key="voltage_l3",
        icon="mdi:flash-triangle-outline",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperatureCurrentLimit",
        translation_key="temperature_current_limit",
        icon="mdi:thermometer-alert",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="adapterMaxCurrent",
        translation_key="adapter_max_current",
        icon="mdi:power-plug",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
    ),
    # All the temperature sensors
    # Internal
    SensorEntityDescription(
        key="temperature_internal",
        translation_key="temperature_internal",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    # Adapter (3 probes)
    SensorEntityDescription(
        key="temperature_adapter1",
        translation_key="temperature_adapter1",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperature_adapter2",
        translation_key="temperature_adapter2",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperature_adapter3",
        translation_key="temperature_adapter3",
        icon="mdi:thermometer-lines",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    # Relay (2 probes)
    SensorEntityDescription(
        key="temperature_relay1",
        translation_key="temperature_relay1",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="temperature_relay2",
        translation_key="temperature_relay2",
        icon="mdi:thermometer-low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
    ),
    # Some diagnostic sensors
    SensorEntityDescription(
        key="totalChargedEnergy",
        translation_key="total_charged_energy",
        icon="mdi:lightning-bolt-circle",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=3,
    ),
    SensorEntityDescription(
        key="totalChargingCount",
        translation_key="total_charging_count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="totalChargingTime",
        translation_key="total_charging_time",
        icon="mdi:timer-sand-complete",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
    ),
    SensorEntityDescription(
        key="chargingPower",
        translation_key="max_charging_power",
        icon="mdi:flash-outline",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
    ),
)

TEMPERATURE_KEYS = {
    "temperature_internal",
    "temperature_adapter1",
    "temperature_adapter2",
    "temperature_adapter3",
    "temperature_relay1",
    "temperature_relay2",
}
DIAGNOSTIC_KEYS = {"totalChargedEnergy", "totalChargingCount", "totalChargingTime"}
TYPE_INFO_KEYS = {"chargingPower"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    entities: list[SensorEntity] = []

    # 1) generic sensors
    entities.extend(
        IntegrationEcovolterSensor(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )

    # 2) charger type sensor
    entities.append(
        EcovolterChargerTypeSensor(
            entry.runtime_data.coordinator,
            SensorEntityDescription(
                key="chargerType",
                translation_key="charger_type",
                icon="mdi:ev-plug-type2",
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        )
    )

    async_add_entities(entities)


class IntegrationEcovolterSensor(IntegrationEcovolterEntity, SensorEntity):
    """ecovolter sensor class."""

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return camel_to_snake(self.entity_description.key)

    def _native_value_status(self, key) -> float | None:
        """Return the native value of the status sensor."""
        status = get_status(self.coordinator)

        # Special handling for temperature sensors (nested under status["temperatures"])
        if key in TEMPERATURE_KEYS:
            return extract_temperature(status, key)
        return as_float(status.get(key))

    def _native_value_diagnostics(self, key) -> float | None:
        """Return the native value of the diagnostics sensor."""
        diagnostics = get_diagnostics(self.coordinator)
        return as_float(diagnostics.get(key))

    def _native_value_type(self, key) -> float | None:
        """Return the native value of the diagnostics sensor."""
        type_info = get_type_info(self.coordinator)
        return as_float(type_info.get(key))

    @property
    def native_value(self) -> float | None:
        """Return the native value of the sensor."""
        key = self.entity_description.key

        if key in DIAGNOSTIC_KEYS:
            return self._native_value_diagnostics(key)
        elif key in TYPE_INFO_KEYS:
            return self._native_value_type(key)

        return self._native_value_status(key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return unit of measurement for the entity."""
        if self.entity_description.key == "kwhPrice":
            currency_raw = get_settings(self.coordinator).get("currency")
            currency_id = cast(
                int | None, currency_raw if isinstance(currency_raw, int) else None
            )
            iso = CURRENCY_MAP.get(currency_id or -1, "EUR")
            return f"{iso}/{UnitOfEnergy.KILO_WATT_HOUR}"
        elif self.entity_description.key == "chargingCost":
            currency_raw = get_settings(self.coordinator).get("currency")
            currency_id = cast(
                int | None, currency_raw if isinstance(currency_raw, int) else None
            )
            iso = CURRENCY_MAP.get(currency_id or -1, "EUR")
            return iso
        return self.entity_description.native_unit_of_measurement


class EcovolterChargerTypeSensor(IntegrationEcovolterEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self,
        coordinator,
        entity_description: SensorEntityDescription,
    ):
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"
        self._attr_options = [label for _, label in sorted(CHARGER_TYPE_LABELS.items())]

    @property
    def suggested_object_id(self) -> str:
        """This is used to generate the entity_id."""
        return camel_to_snake(self.entity_description.key)

    @property
    def native_value(self) -> str | None:
        type_info = get_type_info(self.coordinator)
        raw = type_info.get("chargerType")
        if isinstance(raw, int):
            return CHARGER_TYPE_LABELS[raw]

        return None
