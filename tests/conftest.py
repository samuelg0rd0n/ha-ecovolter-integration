from __future__ import annotations

from typing import Any

import pytest
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import DATA_INSTANCES
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.ecovolter.const import (
    DOMAIN,
    CONF_SERIAL_NUMBER,
    CONF_SECRET_KEY,
    CONF_UPDATE_INTERVAL,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


class FakeEcovolterClient:
    """In-memory stand-in for EcovolterApiClient.

    GETs return copies of the controllable section dicts (or raise ``fail_exc``);
    PATCH records the call and, when ``apply_writes`` is True, folds the written
    keys into ``settings`` so the next poll confirms the write.
    """

    def __init__(self) -> None:
        self.settings: dict[str, Any] = {
            "isThreePhaseModeEnable": False,
            "isChargingEnable": False,
            "isBoostModeEnable": False,
            "isLocalPanelEnable": False,
            "targetCurrent": 10,
            "boostCurrent": 10,
            "maxCurrent": 32,
            "boostTime": 0,
            "kwhPrice": 5.0,
            "currency": 1,  # CZK
        }
        self.status: dict[str, Any] = {
            "actualPower": 1000,
            "temperatures": {
                "internal": 30.0,
                "adapter": [30.0, 30.0, 30.0],
                "relay": [30.0, 30.0, 30.0],
            },
        }
        self.diagnostics: dict[str, Any] = {}
        self.type_info: dict[str, Any] = {"chargerType": 1}

        # Test controls.
        self.fail_exc: Exception | None = None
        self.apply_writes: bool = True
        self.set_calls: list[dict[str, Any]] = []
        self.poll_count: int = 0

    async def async_get_status(self) -> Any:
        if self.fail_exc is not None:
            raise self.fail_exc
        self.poll_count += 1
        return dict(self.status)

    async def async_get_settings(self) -> Any:
        if self.fail_exc is not None:
            raise self.fail_exc
        return dict(self.settings)

    async def async_get_diagnostics(self) -> Any:
        if self.fail_exc is not None:
            raise self.fail_exc
        return dict(self.diagnostics)

    async def async_get_type(self) -> Any:
        if self.fail_exc is not None:
            raise self.fail_exc
        return dict(self.type_info)

    async def async_set_settings(self, data: dict) -> Any:
        self.set_calls.append(dict(data))
        if self.apply_writes:
            applied = dict(data)
            applied.pop("timestamp", None)
            self.settings.update(applied)
        return {}


@pytest.fixture(name="fake_client")
def fake_client_fixture() -> FakeEcovolterClient:
    """A fresh fake API client."""
    return FakeEcovolterClient()


@pytest.fixture(name="setup_integration")
async def setup_integration_fixture(hass: HomeAssistant, fake_client: FakeEcovolterClient):
    """Set up the integration end-to-end against the fake client.

    Yields the config entry; unloads on teardown so no coordinator/debounce
    timers linger into verify_cleanup.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_NUMBER: "abc",
            CONF_SECRET_KEY: "secret",
            CONF_UPDATE_INTERVAL: 15,
        },
        unique_id="abc",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.ecovolter.EcovolterApiClient",
        return_value=fake_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    yield entry

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def get_entity_by_key(hass: HomeAssistant, domain: str, key: str) -> Any:
    """Return the live entity object for a platform key (e.g. switch/isChargingEnable)."""
    component = hass.data[DATA_INSTANCES][domain]
    for entity in component.entities:
        if getattr(entity.entity_description, "key", None) == key:
            return entity
    raise AssertionError(f"No {domain} entity with key {key!r}")


def state_of(hass: HomeAssistant, entity_id: str) -> str:
    """Return the string state of an entity, asserting it exists."""
    state = hass.states.get(entity_id)
    assert state is not None, f"State for {entity_id} is missing"
    return state.state
