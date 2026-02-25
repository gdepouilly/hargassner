"""Config flow for the Hargassner integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HargassnerApiClient, HargassnerApiError, HargassnerAuthError
from .const import CONF_INSTALLATION_ID, CONF_REFRESH_TOKEN, DOMAIN


class HargassnerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hargassner."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step shown to the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            api = HargassnerApiClient()
            try:
                token_data = await api.login(
                    session,
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                )
                await api.get_widgets(
                    session,
                    token_data["access_token"],
                    user_input[CONF_INSTALLATION_ID],
                )
            except HargassnerAuthError:
                errors["base"] = "invalid_auth"
            except HargassnerApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(str(user_input[CONF_INSTALLATION_ID]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hargassner {user_input[CONF_INSTALLATION_ID]}",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_INSTALLATION_ID: user_input[CONF_INSTALLATION_ID],
                        CONF_REFRESH_TOKEN: token_data["refresh_token"],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(CONF_INSTALLATION_ID): int,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )
