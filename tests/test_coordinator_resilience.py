"""Coordinator failure-tolerance and freshness tests."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    MockConfigEntry,
)

from custom_components.ecovolter.api import (
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientCommunicationError,
)
from custom_components.ecovolter.const import (
    DOMAIN,
    LOGGER,
    MAX_CONSECUTIVE_FAILURES,
    CONF_SERIAL_NUMBER,
    CONF_SECRET_KEY,
    CONF_UPDATE_INTERVAL,
)
from custom_components.ecovolter.coordinator import EcovolterDataUpdateCoordinator

from .conftest import FakeEcovolterClient


def _build_coordinator(
    hass: HomeAssistant, client: FakeEcovolterClient
) -> EcovolterDataUpdateCoordinator:
    """Build a bare coordinator wired to a fake client (no platforms, data=None)."""
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
    coordinator = EcovolterDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(seconds=15),
    )
    coordinator.config_entry = entry  # type: ignore[assignment]
    entry.runtime_data = SimpleNamespace(client=client)  # type: ignore[assignment]
    return coordinator


@pytest.mark.asyncio
async def test_tolerates_three_failures_then_unavailable(
    hass: HomeAssistant, fake_client: FakeEcovolterClient
) -> None:
    """Up to 3 consecutive failures keep last-good data; the 4th goes unavailable."""
    coordinator = _build_coordinator(hass, fake_client)

    # Seed one successful poll.
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    seeded = coordinator.data
    assert seeded is not None
    assert coordinator.data_is_fresh is True

    # Failures 1..3 — tolerated, last-good served, entities stay available.
    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
    for expected in range(1, MAX_CONSECUTIVE_FAILURES + 1):
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True
        assert coordinator.data == seeded
        assert coordinator._consecutive_failures == expected
        assert coordinator.data_is_fresh is False

    # 4th consecutive failure → unavailable.
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    assert coordinator._consecutive_failures == MAX_CONSECUTIVE_FAILURES + 1

    # Recovery resets the counter and freshness.
    fake_client.fail_exc = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator._consecutive_failures == 0
    assert coordinator.data_is_fresh is True


@pytest.mark.asyncio
async def test_interleaved_failure_success_never_unavailable(
    hass: HomeAssistant, fake_client: FakeEcovolterClient
) -> None:
    """A failure that is followed by a success before the limit never blips."""
    coordinator = _build_coordinator(hass, fake_client)
    await coordinator.async_refresh()

    for _ in range(5):
        fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True
        fake_client.fail_exc = None
        await coordinator.async_refresh()
        assert coordinator.last_update_success is True
        assert coordinator._consecutive_failures == 0


@pytest.mark.asyncio
async def test_auth_error_raises_immediately_and_untracked(
    hass: HomeAssistant, fake_client: FakeEcovolterClient
) -> None:
    """Auth failures raise and are never counted as tolerated failures."""
    coordinator = _build_coordinator(hass, fake_client)
    await coordinator.async_refresh()  # seed data so it is not None

    fake_client.fail_exc = EcovolterApiClientAuthenticationError("bad key")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()
    assert coordinator._consecutive_failures == 0


@pytest.mark.asyncio
async def test_first_refresh_failure_raises_update_failed(
    hass: HomeAssistant, fake_client: FakeEcovolterClient
) -> None:
    """A comms error with no prior data raises UpdateFailed (→ ConfigEntryNotReady)."""
    coordinator = _build_coordinator(hass, fake_client)
    assert coordinator.data is None

    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_first_refresh_failure_sets_setup_retry(
    hass: HomeAssistant, fake_client: FakeEcovolterClient
) -> None:
    """End-to-end: a failing first poll leaves the entry in SETUP_RETRY."""
    from unittest.mock import patch
    from homeassistant.config_entries import ConfigEntryState

    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
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
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
