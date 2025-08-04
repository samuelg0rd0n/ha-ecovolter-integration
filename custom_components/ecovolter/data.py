"""Custom types for ecovolter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import IntegrationEcovolterApiClient
    from .coordinator import EcovolterDataUpdateCoordinator


type IntegrationEcovolterConfigEntry = ConfigEntry[IntegrationEcovolterData]


@dataclass
class IntegrationEcovolterData:
    """Data for the Ecovolter integration."""

    client: IntegrationEcovolterApiClient
    coordinator: EcovolterDataUpdateCoordinator
    integration: Integration
