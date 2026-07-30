"""Write-path error-type tests.

A failed settings write must surface as a Home Assistant error type — see
docs/plans/2026-07-29-001-fix-no-op-write-suppression-plan.md (R4-R6).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import translation

from custom_components.ecovolter.api import (
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientCommunicationError,
)
from custom_components.ecovolter.const import DOMAIN

from .conftest import FakeEcovolterClient, get_entity_by_key, state_of


async def _turn_on(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )


@pytest.mark.asyncio
async def test_communication_failure_raises_home_assistant_error(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """A failed PATCH raises HomeAssistantError and leaves no optimistic state."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    async def _boom(data):
        raise EcovolterApiClientCommunicationError("write failed")

    fake_client.async_set_settings = _boom  # type: ignore[method-assign]

    with pytest.raises(HomeAssistantError) as exc_info:
        await _turn_on(hass, sw.entity_id)

    assert not isinstance(exc_info.value, ConfigEntryAuthFailed)
    assert sw._optimistic_set is False
    assert state_of(hass, sw.entity_id) == "off"


@pytest.mark.asyncio
async def test_authentication_failure_raises_config_entry_auth_failed(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """An auth failure during a write starts reauthentication."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    async def _boom(data):
        raise EcovolterApiClientAuthenticationError("bad secret")

    fake_client.async_set_settings = _boom  # type: ignore[method-assign]

    with pytest.raises(ConfigEntryAuthFailed):
        await _turn_on(hass, sw.entity_id)

    assert sw._optimistic_set is False


@pytest.mark.asyncio
async def test_write_failure_message_resolves_through_translation_catalogue(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    """The raised error's message is translated, not an untranslated key."""
    sw = get_entity_by_key(hass, "switch", "isChargingEnable")

    async def _boom(data):
        raise EcovolterApiClientCommunicationError("write failed")

    fake_client.async_set_settings = _boom  # type: ignore[method-assign]

    await translation.async_get_translations(
        hass, "en", "exceptions", integrations={DOMAIN}
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _turn_on(hass, sw.entity_id)

    message = str(exc_info.value)
    assert message != "write_failed"  # not the raw, untranslated key
    assert "write_failed" not in message


@pytest.mark.asyncio
async def test_unsupported_currency_raises_service_validation_error(
    hass: HomeAssistant, fake_client: FakeEcovolterClient, setup_integration
) -> None:
    sel = get_entity_by_key(hass, "select", "currency")

    with pytest.raises(ServiceValidationError):
        await sel.async_select_option("NOT_A_CURRENCY")


def test_exception_translation_keys_match_across_catalogues() -> None:
    """Every exceptions key in strings.json also exists in en.json and cs.json."""
    base = Path(__file__).resolve().parent.parent / "custom_components" / "ecovolter"
    strings = json.loads((base / "strings.json").read_text())
    en = json.loads((base / "translations" / "en.json").read_text())
    cs = json.loads((base / "translations" / "cs.json").read_text())

    strings_keys = set(strings.get("exceptions", {}).keys())
    assert strings_keys, "expected at least one exceptions key in strings.json"

    for name, catalogue in (("en", en), ("cs", cs)):
        catalogue_keys = set(catalogue.get("exceptions", {}).keys())
        assert catalogue_keys == strings_keys, (
            f"translations/{name}.json exceptions keys {catalogue_keys} "
            f"!= strings.json {strings_keys}"
        )
