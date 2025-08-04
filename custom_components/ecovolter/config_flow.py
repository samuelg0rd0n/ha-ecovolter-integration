"""Adds config flow for Ecovolter."""

from __future__ import annotations

from slugify import slugify
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import DOMAIN, SECRET_KEY, SERIAL_NUMBER


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
            # try:
            #     await self._test_credentials(
            #         secret_key=user_input[SECRET_KEY],
            #         serial_number=user_input[SERIAL_NUMBER],
            #     )
            # except IntegrationEcovolterApiClientAuthenticationError as exception:
            #     LOGGER.warning(exception)
            #     _errors["base"] = "auth"
            # except IntegrationEcovolterApiClientCommunicationError as exception:
            #     LOGGER.error(exception)
            #     _errors["base"] = "connection"
            # except IntegrationEcovolterApiClientError as exception:
            #     LOGGER.exception(exception)
            #     _errors["base"] = "unknown"
            # else:
            await self.async_set_unique_id(
                ## Do NOT use this in production code
                ## The unique_id should never be something that can change
                ## https://developers.home-assistant.io/docs/config_entries_config_flow_handler#unique-ids
                unique_id=slugify(user_input[SERIAL_NUMBER])
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
        # client = IntegrationEcovolterApiClient(
        #    serial_number=serial_number,
        #    secret_key=secret_key,
        #    session=async_create_clientsession(self.hass),
        # )
        # await client.async_get_data()
