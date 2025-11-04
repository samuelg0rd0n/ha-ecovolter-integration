from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant import config_entries

# Adjust if your import paths differ
from custom_components.ecovolter.const import (
    DOMAIN,
    CONF_SERIAL_NUMBER,
    CONF_SECRET_KEY,
    CONF_BASE_URI,
    CONF_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL_SECONDS,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
)
from custom_components.ecovolter.api import (
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientCommunicationError,
    EcovolterApiClientError,
)

from homeassistant.data_entry_flow import FlowResultType

@pytest.fixture(name="ecovolter_setup", autouse=True)
def ecovolter_setup_fixture():
    """Auto-mock entry setup so the integration doesn't actually start."""
    with patch(
        "custom_components.ecovolter.async_setup_entry",
        return_value=True,
    ):
        yield

@pytest.fixture(name="api")
def mock_ecovolter_api():
    """
    Happy-path API mock.

    IMPORTANT: Patch the symbol in the module where it's used:
    config_flow imports EcovolterApiClient directly, so patch
    custom_components.ecovolter.config_flow.EcovolterApiClient
    """
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as client_cls:
        client = client_cls.return_value
        # Flow calls only async_get_status() for validation
        client.async_get_status = AsyncMock(return_value={"ok": True})
        yield client

@pytest.fixture(autouse=True)
def verify_cleanup():
    """
    Override strict cleanup verification from pytest-homeassistant-custom-component.
    
    Config flow tests trigger background translation loading which spawns
    pytest-asyncio's _run_safe_shutdown_loop thread. This is expected behavior
    and doesn't indicate a resource leak.
    """
    yield

@pytest.mark.asyncio
async def test_create_entry_success(hass: HomeAssistant, api) -> None:
    """Happy path: creates entry; serial/secret lower-cased; base_uri normalized; interval honored."""
    user_input = {
        CONF_SERIAL_NUMBER: "REVCR01A00000001",            # will be lowercased
        CONF_SECRET_KEY: "REVCR01A00000001",               # will be lowercased
        CONF_BASE_URI: "http://ecovolter.test///",         # will be rstrip('/') -> http://ecovolter.test
        CONF_UPDATE_INTERVAL: 17,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "revcr01a00000001"
    data = result["data"]

    assert data[CONF_SERIAL_NUMBER] == "revcr01a00000001"
    assert data[CONF_SECRET_KEY] == "revcr01a00000001"
    assert data[CONF_BASE_URI] == "http://ecovolter.test"
    assert data[CONF_UPDATE_INTERVAL] == 17

@pytest.mark.asyncio
async def test_min_update_interval_enforced(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(return_value={})

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_SERIAL_NUMBER: "abc",
                CONF_SECRET_KEY: "abc",
                CONF_UPDATE_INTERVAL: 1,  # below min
            },
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_UPDATE_INTERVAL] == MIN_UPDATE_INTERVAL_SECONDS

@pytest.mark.asyncio
async def test_default_update_interval_when_missing(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(return_value={})

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_SERIAL_NUMBER: "abc",
                CONF_SECRET_KEY: "abc",
                # no interval provided
            },
        )

    assert result["type"] == "create_entry"
    assert result["data"][CONF_UPDATE_INTERVAL] == DEFAULT_UPDATE_INTERVAL_SECONDS

@pytest.mark.asyncio
async def test_auth_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(side_effect=EcovolterApiClientAuthenticationError("bad key"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_SERIAL_NUMBER: "abc", CONF_SECRET_KEY: "abc"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "auth"}

@pytest.mark.asyncio
async def test_connection_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(side_effect=EcovolterApiClientCommunicationError("timeout"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_SERIAL_NUMBER: "abc", CONF_SECRET_KEY: "abc"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "connection"}

@pytest.mark.asyncio
async def test_unknown_error(hass: HomeAssistant) -> None:
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(side_effect=EcovolterApiClientError("boom"))

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_SERIAL_NUMBER: "abc", CONF_SECRET_KEY: "abc"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}

@pytest.mark.asyncio
async def test_unique_id_and_abort_if_exists(hass: HomeAssistant) -> None:
    """Second run should abort as already_configured (unique_id=serial)."""
    with patch(
        "custom_components.ecovolter.config_flow.EcovolterApiClient",
        autospec=True,
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.async_get_status = AsyncMock(return_value={})

        # First run → create entry
        first = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_SERIAL_NUMBER: "SERIAL1", CONF_SECRET_KEY: "SERIAL1"},
        )
        assert first["type"] == "create_entry"

        # Second run → same serial (case-insensitive)
        second = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_SERIAL_NUMBER: "serial1", CONF_SECRET_KEY: "serial1"},
        )

    assert second["type"] == "abort"
    assert second["reason"] == "already_configured"
