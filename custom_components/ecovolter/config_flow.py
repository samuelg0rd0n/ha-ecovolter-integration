"""Adds config flow for Ecovolter."""

from __future__ import annotations

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

from .const import DOMAIN, SECRET_KEY, SERIAL_NUMBER, LOGGER


class EcovolterFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Ecovolter."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    secret_key=user_input[SECRET_KEY],
                    serial_number=user_input[SERIAL_NUMBER],
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
                await self.async_set_unique_id(
                    unique_id=user_input[SERIAL_NUMBER]
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[SERIAL_NUMBER],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        SERIAL_NUMBER,
                        default=(user_input or {}).get(SERIAL_NUMBER, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(SECRET_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, serial_number: str, secret_key: str) -> None:
        """Validate credentials."""
        client = EcovolterApiClient(
           serial_number=serial_number,
           secret_key=secret_key,
           session=async_create_clientsession(self.hass),
        )
        await client.async_get_status()
