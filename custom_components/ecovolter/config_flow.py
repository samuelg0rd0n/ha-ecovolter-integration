"""Adds config flow for Ecovolter."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    EcovolterApiClient,
    EcovolterApiClientAuthenticationError,
    EcovolterApiClientCommunicationError,
    EcovolterApiClientError,
)

from .const import (
    DOMAIN,
    LOGGER,
    CONF_SECRET_KEY,
    CONF_SERIAL_NUMBER,
    CONF_BASE_URI,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    MIN_UPDATE_INTERVAL_SECONDS,
)


class EcovolterFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ecovolter."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors: dict[str, str] = {}
        if user_input is not None:
            # Normalize inputs
            serial = str(user_input.get(CONF_SERIAL_NUMBER, "")).strip().lower()
            secret = str(user_input.get(CONF_SECRET_KEY, "")).strip().lower()
            
            base_uri = user_input.get(CONF_BASE_URI)
            if isinstance(base_uri, str) and base_uri.strip():
                base_uri = base_uri.strip().rstrip("/")
            else:
                base_uri = None            

            # Update interval (optional)
            try:
                interval = int(user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS))
            except (TypeError, ValueError):
                interval = DEFAULT_UPDATE_INTERVAL_SECONDS
            if interval < MIN_UPDATE_INTERVAL_SECONDS:
                interval = MIN_UPDATE_INTERVAL_SECONDS

            # Validate credentials by calling API
            try:
                await self._test_credentials(
                    serial_number=serial,
                    secret_key=secret,
                    base_uri=base_uri,
                )
            except EcovolterApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except EcovolterApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except EcovolterApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                ## https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                # Ensure unique ID is the normalized serial
                await self.async_set_unique_id(unique_id=serial)
                self._abort_if_unique_id_configured()
                
                data: dict[str, Any] = {
                    CONF_SERIAL_NUMBER: serial,
                    CONF_SECRET_KEY: secret,
                    CONF_UPDATE_INTERVAL: interval,
                }
                if base_uri:
                    data[CONF_BASE_URI] = base_uri

                return self.async_create_entry(
                    title=serial,
                    data=data,
                )

        defaults = user_input or {}    

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERIAL_NUMBER,
                        default=defaults.get(CONF_SERIAL_NUMBER, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_SECRET_KEY,
                        default=defaults.get(CONF_SECRET_KEY, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_BASE_URI,
                        default=defaults.get(CONF_BASE_URI, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=defaults.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_SECONDS),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_UPDATE_INTERVAL_SECONDS,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="s",
                        )
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(
        self, serial_number: str, secret_key: str, base_uri: str | None = None
    ) -> None:
        """Validate credentials."""
        client = EcovolterApiClient(
           serial_number=serial_number,
           secret_key=secret_key,
           base_uri=base_uri,
           session=async_create_clientsession(self.hass),
        )
        await client.async_get_status()
