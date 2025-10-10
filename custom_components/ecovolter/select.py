from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription
)

from homeassistant.helpers.entity import EntityCategory

from .const import KEY_SETTINGS, CURRENCY_MAP, CURRENCY_INV_MAP
from .entity import IntegrationEcovolterEntity
from .utils import camel_to_snake

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from .coordinator import EcovolterDataUpdateCoordinator
    from .data import EcovolterConfigEntry

ENTITY_DESCRIPTIONS: tuple[SelectEntityDescription, ...] = (
    SelectEntityDescription(
        key="currency",
        translation_key="currency",
        icon="mdi:cash-multiple",
        entity_category=EntityCategory.CONFIG,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: EcovolterConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        EcovolterCurrencySelect(
            coordinator=entry.runtime_data.coordinator,
            entity_description=entity_description,
        )
        for entity_description in ENTITY_DESCRIPTIONS
    )

class EcovolterCurrencySelect(IntegrationEcovolterEntity, SelectEntity):
    """Currency selection."""

    _options = list(CURRENCY_INV_MAP.keys())

    def __init__(
        self,
        coordinator: EcovolterDataUpdateCoordinator,
        entity_description: SelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{camel_to_snake(entity_description.key)}"
        )

    @property
    def suggested_object_id(self) -> str:
        return camel_to_snake(self.entity_description.key)

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        """Map device int → ISO code."""
        raw = self.coordinator.data.get(KEY_SETTINGS, {}).get("currency")
        if isinstance(raw, int) and raw in CURRENCY_MAP:
            return CURRENCY_MAP[raw]
        return None  # unknown until we have valid data

    async def async_select_option(self, option: str) -> None:
        """Map ISO code → device int and write."""
        value = CURRENCY_INV_MAP.get(option)
        if value is None:
            raise ValueError(f"Unsupported currency option: {option}")
        await self.coordinator.config_entry.runtime_data.client.async_set_settings(
            {"currency": value}
        )
        await self.coordinator.async_request_refresh()