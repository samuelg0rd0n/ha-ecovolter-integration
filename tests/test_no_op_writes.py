"""No-op write suppression tests.

A settings write whose requested value already matches the charger's known
value must never reach the client's ``async_set_settings`` — see
docs/plans/2026-07-29-001-fix-no-op-write-suppression-plan.md (R1-R3).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.ecovolter.api import EcovolterApiClientCommunicationError
from custom_components.ecovolter.const import LOGGER

from .conftest import FakeEcovolterClient, get_entity_by_key, state_of


@pytest.mark.asyncio
async def test_number_write_matching_value_records_no_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """Writing the fixture's current value sends nothing and leaves state alone."""
    num = get_entity_by_key(hass, "number", "targetCurrent")
    before = state_of(hass, num.entity_id)

    await num.async_set_native_value(10)  # fixture default

    assert fake_client.set_calls == []
    assert state_of(hass, num.entity_id) == before


@pytest.mark.asyncio
async def test_number_write_changed_value_records_one_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    num = get_entity_by_key(hass, "number", "targetCurrent")

    await num.async_set_native_value(12)

    assert len(fake_client.set_calls) == 1
    assert fake_client.set_calls[0]["targetCurrent"] == 12


@pytest.mark.asyncio
async def test_switch_turn_on_already_on_records_no_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A switch confirmed on by the device does not get a second PATCH."""
    coordinator = setup_integration.runtime_data.coordinator
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": sw.entity_id}, blocking=True
    )
    assert len(fake_client.set_calls) == 1
    await coordinator.async_refresh()  # confirm: optimistic clears, device value is True
    assert sw._optimistic_set is False

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": sw.entity_id}, blocking=True
    )

    assert len(fake_client.set_calls) == 1  # no second call


@pytest.mark.asyncio
async def test_switch_turn_on_when_off_records_one_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": sw.entity_id}, blocking=True
    )

    assert len(fake_client.set_calls) == 1
    assert fake_client.set_calls[0]["isChargingEnable"] is True


@pytest.mark.asyncio
async def test_select_currency_already_active_records_no_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sel = get_entity_by_key(hass, "select", "currency")
    assert state_of(hass, sel.entity_id) == "CZK"  # fixture default currency=1

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": sel.entity_id, "option": "CZK"},
        blocking=True,
    )

    assert fake_client.set_calls == []


@pytest.mark.asyncio
async def test_select_currency_changed_records_one_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sel = get_entity_by_key(hass, "select", "currency")

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": sel.entity_id, "option": "USD"},
        blocking=True,
    )

    assert len(fake_client.set_calls) == 1
    assert fake_client.set_calls[0]["currency"] == 2


@pytest.mark.asyncio
async def test_number_write_within_tolerance_records_no_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    coordinator = setup_integration.runtime_data.coordinator
    num = get_entity_by_key(hass, "number", "kwhPrice")

    fake_client.settings["kwhPrice"] = 5.003
    await coordinator.async_refresh()

    await num.async_set_native_value(5.0)  # |5.0 - 5.003| = 0.003 <= 0.005 tolerance

    assert fake_client.set_calls == []


@pytest.mark.asyncio
async def test_number_write_outside_tolerance_records_one_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    coordinator = setup_integration.runtime_data.coordinator
    num = get_entity_by_key(hass, "number", "kwhPrice")

    fake_client.settings["kwhPrice"] = 5.003
    await coordinator.async_refresh()

    await num.async_set_native_value(5.01)  # |5.01 - 5.003| = 0.007 > 0.005 tolerance

    assert len(fake_client.set_calls) == 1
    assert fake_client.set_calls[0]["kwhPrice"] == 5.01


@pytest.mark.asyncio
async def test_repeat_write_same_value_while_optimistic_pending_records_no_second_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    num = get_entity_by_key(hass, "number", "targetCurrent")

    await num.async_set_native_value(12)
    pending_value = num._optimistic_value
    pending_expiry = num._optimistic_expiry
    assert len(fake_client.set_calls) == 1

    await num.async_set_native_value(12)

    assert len(fake_client.set_calls) == 1  # no second call
    assert num._optimistic_value == pending_value
    assert num._optimistic_expiry == pending_expiry


@pytest.mark.asyncio
async def test_write_different_value_while_optimistic_pending_is_sent(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    num = get_entity_by_key(hass, "number", "targetCurrent")

    await num.async_set_native_value(12)
    first_expiry = num._optimistic_expiry

    await num.async_set_native_value(20)

    assert len(fake_client.set_calls) == 2
    assert num._optimistic_value == 20
    assert num._optimistic_expiry >= first_expiry


@pytest.mark.asyncio
async def test_stale_data_does_not_suppress_matching_write(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """While data_is_fresh is False, a write matching last-known state is still sent."""
    coordinator = setup_integration.runtime_data.coordinator
    num = get_entity_by_key(hass, "number", "targetCurrent")

    fake_client.fail_exc = EcovolterApiClientCommunicationError("timeout")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    assert coordinator.data_is_fresh is False
    fake_client.fail_exc = None

    await num.async_set_native_value(10)  # matches fixture's last-known value

    assert len(fake_client.set_calls) == 1


@pytest.mark.asyncio
async def test_clamped_value_matching_device_value_records_no_call(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """The clamp is applied before the comparison, not after."""
    coordinator = setup_integration.runtime_data.coordinator
    num = get_entity_by_key(hass, "number", "targetCurrent")

    await num.async_set_native_value(32)  # confirmed at the charger-type max
    await coordinator.async_refresh()
    assert num._optimistic_set is False
    assert len(fake_client.set_calls) == 1

    await num.async_set_native_value(100)  # clamps to 32, matches the device value

    assert len(fake_client.set_calls) == 1  # no second call


@pytest.mark.asyncio
async def test_missing_key_is_written_not_suppressed(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    coordinator = setup_integration.runtime_data.coordinator
    num = get_entity_by_key(hass, "number", "boostTime")

    del fake_client.settings["boostTime"]
    await coordinator.async_refresh()

    await num.async_set_native_value(60)

    assert len(fake_client.set_calls) == 1
    assert fake_client.set_calls[0]["boostTime"] == 60


@pytest.mark.asyncio
async def test_suppressed_write_logs_at_debug(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A suppressed write names the entity and the value already in effect.

    ``caplog`` is unusable here: this environment's pytest (9.0.3) and
    pytest-homeassistant-custom-component (0.13.340) disagree over the
    fixture's override mechanics, so the debug record is captured directly
    off the shared LOGGER instead.
    """
    num = get_entity_by_key(hass, "number", "targetCurrent")

    with patch.object(LOGGER, "debug") as mock_debug:
        await num.async_set_native_value(10)

    assert fake_client.set_calls == []
    mock_debug.assert_called_once()
    fmt, *fmt_args = mock_debug.call_args.args
    message = fmt % tuple(fmt_args)
    assert num.entity_id in message
    assert "10" in message
