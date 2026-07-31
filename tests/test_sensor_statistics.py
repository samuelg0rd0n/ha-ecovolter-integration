"""Lifetime energy sensor state-class tests.

``totalChargedEnergy`` is a never-resetting lifetime total, so it must use
``SensorStateClass.TOTAL`` rather than ``TOTAL_INCREASING`` — see
docs/plans/2026-07-29-001-fix-no-op-write-suppression-plan.md (R7).
"""

from __future__ import annotations

import pytest
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from .conftest import FakeEcovolterClient, get_entity_by_key, state_of


@pytest.mark.asyncio
async def test_total_charged_energy_state_class_is_total(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sensor = get_entity_by_key(hass, "sensor", "totalChargedEnergy")

    assert sensor.entity_description.state_class == SensorStateClass.TOTAL

    state = hass.states.get(sensor.entity_id)
    assert state is not None
    assert state.attributes["state_class"] == "total"


@pytest.mark.asyncio
async def test_total_charged_energy_accepts_decreasing_value(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A device-side dip is reported verbatim, without raising."""
    coordinator = setup_integration.runtime_data.coordinator
    sensor = get_entity_by_key(hass, "sensor", "totalChargedEnergy")

    fake_client.diagnostics["totalChargedEnergy"] = 1905.34
    await coordinator.async_refresh()
    assert state_of(hass, sensor.entity_id) == "1905.34"

    fake_client.diagnostics["totalChargedEnergy"] = 1905.27  # observed dip
    await coordinator.async_refresh()
    assert state_of(hass, sensor.entity_id) == "1905.27"


@pytest.mark.asyncio
async def test_total_charged_energy_device_class_and_unit_unchanged(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sensor = get_entity_by_key(hass, "sensor", "totalChargedEnergy")

    assert sensor.entity_description.device_class == SensorDeviceClass.ENERGY
    assert (
        sensor.entity_description.native_unit_of_measurement
        == UnitOfEnergy.KILO_WATT_HOUR
    )
