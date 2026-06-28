"""Optimistic-update and debounced-refresh tests (full integration setup)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped]
    async_fire_time_changed,
)

from custom_components.ecovolter.api import EcovolterApiClientCommunicationError
from custom_components.ecovolter.const import MAX_CONSECUTIVE_FAILURES

from .conftest import FakeEcovolterClient, get_entity_by_key, state_of


async def _flush_debounce(
    hass: HomeAssistant, freezer, seconds: float = 3.0
) -> None:
    """Advance past the write-refresh cooldown and fire the pending poll."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _turn_on(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )


# --- Phase 2: debounce --------------------------------------------------------


@pytest.mark.asyncio
async def test_write_burst_coalesces_to_one_refresh(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """N refresh requests within the cooldown produce exactly one poll."""
    coordinator = setup_integration.runtime_data.coordinator
    base = fake_client.poll_count

    for _ in range(5):
        await coordinator.async_request_refresh()
    await hass.async_block_till_done()

    # Still inside the cooldown window — no extra poll yet.
    assert fake_client.poll_count == base

    await _flush_debounce(hass, freezer)
    assert fake_client.poll_count == base + 1


# --- Phase 3: optimistic happy path ------------------------------------------


@pytest.mark.asyncio
async def test_switch_optimistic_immediate_then_confirmed(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """Switch shows new state instantly, then clears optimistic on confirmation."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")
    assert state_of(hass, sw.entity_id) == "off"

    await _turn_on(hass, sw.entity_id)

    # Immediate, before any poll.
    assert state_of(hass, sw.entity_id) == "on"
    assert sw._optimistic_set is True

    # Debounced confirming poll (device applied the write).
    await _flush_debounce(hass, freezer)
    assert state_of(hass, sw.entity_id) == "on"
    assert sw._optimistic_set is False


@pytest.mark.asyncio
async def test_applied_write_never_flashes_back(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A write the device DID apply never reverts before confirmation."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")
    await _turn_on(hass, sw.entity_id)
    assert state_of(hass, sw.entity_id) == "on"

    # Throughout the debounce window and the confirming poll it stays on.
    await _flush_debounce(hass, freezer)
    assert state_of(hass, sw.entity_id) == "on"


# --- Phase 3: stale-poll race -------------------------------------------------


@pytest.mark.asyncio
async def test_stale_poll_does_not_flip_back(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """An old value from a lagging poll must not override the optimistic value."""
    coordinator = setup_integration.runtime_data.coordinator
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    fake_client.apply_writes = False  # device lags: poll still returns old value
    await _turn_on(hass, sw.entity_id)
    assert state_of(hass, sw.entity_id) == "on"

    # First post-write poll returns the OLD value (off) — must hold.
    await _flush_debounce(hass, freezer)
    assert state_of(hass, sw.entity_id) == "on"
    assert sw._optimistic_set is True

    # Device catches up; next poll confirms and clears.
    fake_client.settings["isChargingEnable"] = True
    await coordinator.async_refresh()
    assert state_of(hass, sw.entity_id) == "on"
    assert sw._optimistic_set is False


# --- Phase 3: clamp -----------------------------------------------------------


@pytest.mark.asyncio
async def test_number_optimistic_uses_clamped_value(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A request above the max shows the clamped value, never the raw request."""
    num = get_entity_by_key(hass, "number", "targetCurrent")

    # The HA number service rejects out-of-range requests before they reach the
    # entity, so call the entity method directly to exercise the clamp path
    # (max is 32 for chargerType 1).
    await num.async_set_native_value(40)

    assert num._optimistic_value == 32
    assert state_of(hass, num.entity_id) == "32.0"
    assert fake_client.set_calls[-1]["targetCurrent"] == 32


# --- Phase 3: select cross-type ----------------------------------------------


@pytest.mark.asyncio
async def test_select_optimistic_cross_type(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """Currency select shows the new ISO immediately and confirms int↔int."""
    sel = get_entity_by_key(hass, "select", "currency")
    assert state_of(hass, sel.entity_id) == "CZK"

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": sel.entity_id, "option": "USD"},
        blocking=True,
    )

    assert state_of(hass, sel.entity_id) == "USD"
    assert sel._optimistic_value == 2  # raw device int

    await _flush_debounce(hass, freezer)
    assert state_of(hass, sel.entity_id) == "USD"
    assert sel._optimistic_set is False  # confirmed, no spurious full-timeout hold


# --- Phase 3: second write overwrites value + expiry --------------------------


@pytest.mark.asyncio
async def test_second_write_overwrites_value_and_expiry(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A second write before confirmation wins for both value and expiry."""
    num = get_entity_by_key(hass, "number", "targetCurrent")

    await hass.services.async_call(
        "number", "set_value", {"entity_id": num.entity_id, "value": 12}, blocking=True
    )
    first_expiry = num._optimistic_expiry
    assert num._optimistic_value == 12

    await hass.services.async_call(
        "number", "set_value", {"entity_id": num.entity_id, "value": 20}, blocking=True
    )
    assert num._optimistic_value == 20
    assert num._optimistic_expiry >= first_expiry
    assert state_of(hass, num.entity_id) == "20.0"


# --- Phase 3: silently-ignored write reverts after timeout --------------------


@pytest.mark.asyncio
async def test_silently_ignored_write_reverts_after_timeout(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A write the device never applies reverts only after the timeout."""
    coordinator = setup_integration.runtime_data.coordinator
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    fake_client.apply_writes = False  # device ignores the write entirely
    await _turn_on(hass, sw.entity_id)
    assert state_of(hass, sw.entity_id) == "on"

    # Within the timeout the optimistic value is held despite a contradicting poll.
    await _flush_debounce(hass, freezer)
    assert state_of(hass, sw.entity_id) == "on"
    assert sw._optimistic_set is True

    # Past OPTIMISTIC_TIMEOUT_SECONDS, a fresh contradicting poll reverts to truth.
    freezer.tick(timedelta(seconds=12))
    await coordinator.async_refresh()
    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "off"


# --- Phase 3: failure-window timeout interaction (AC5) ------------------------


@pytest.mark.asyncio
async def test_optimistic_survives_timeout_during_tolerated_failures(
    hass: HomeAssistant, freezer, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """An elapsed timeout must NOT clear optimistic while data is tolerated-stale."""
    coordinator = setup_integration.runtime_data.coordinator
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    fake_client.apply_writes = False
    await _turn_on(hass, sw.entity_id)
    assert sw._optimistic_set is True

    # Enter tolerated-failure mode: available stays True, data_is_fresh goes False.
    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data_is_fresh is False

    # Let the optimistic timeout elapse, then poll again (still failing/tolerated).
    freezer.tick(timedelta(seconds=15))
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert sw._optimistic_set is True  # NOT cleared against stale data
    assert state_of(hass, sw.entity_id) == "on"

    # A fresh confirming poll finally clears it.
    fake_client.fail_exc = None
    fake_client.settings["isChargingEnable"] = True
    await coordinator.async_refresh()
    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "on"


# --- Phase 3: unavailable transition (AC6) -----------------------------------


@pytest.mark.asyncio
async def test_optimistic_cleared_on_unavailable_no_resurrect(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """On going unavailable the optimistic value is dropped and never resurrects."""
    coordinator = setup_integration.runtime_data.coordinator
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    fake_client.apply_writes = False
    await _turn_on(hass, sw.entity_id)
    assert sw._optimistic_set is True

    # 4 consecutive failures → unavailable.
    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
    for _ in range(MAX_CONSECUTIVE_FAILURES + 1):
        await coordinator.async_refresh()

    assert coordinator.last_update_success is False
    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "unavailable"

    # Recovery shows fresh polled data (still off), not a resurrected optimistic on.
    fake_client.fail_exc = None
    await coordinator.async_refresh()
    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "off"


# --- Phase 3: PATCH failure → no optimistic, error propagates -----------------


@pytest.mark.asyncio
async def test_patch_failure_sets_no_optimistic(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A failed PATCH propagates and leaves the entity on coordinator truth."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    async def _boom(data):
        raise EcovolterApiClientCommunicationError("write failed")

    fake_client.async_set_settings = _boom  # type: ignore[method-assign]

    with pytest.raises(EcovolterApiClientCommunicationError):
        await _turn_on(hass, sw.entity_id)

    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "off"
