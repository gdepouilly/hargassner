"""Config flow for the Hargassner integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import HargassnerApiClient, HargassnerApiError, HargassnerAuthError
from .const import CONF_INSTALLATION_ID, DOMAIN

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD, autocomplete="current-password"
            )
        ),
    }
)


class HargassnerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hargassner."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow state."""
        self._credentials: dict[str, str] = {}
        self._installations: dict[int, str] = {}

    async def _async_fetch_installations(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[int, str], dict[str, str]]:
        """Log in and list installations; return (installations, errors)."""
        api = HargassnerApiClient(
            async_get_clientsession(self.hass),
            user_input[CONF_EMAIL],
            user_input[CONF_PASSWORD],
        )
        try:
            await api.async_login()
            installations = await api.async_get_installations()
        except HargassnerAuthError:
            return {}, {"base": "invalid_auth"}
        except HargassnerApiError:
            return {}, {"base": "cannot_connect"}
        found = {
            int(i["id"]): i.get("name") or f"Hargassner {i['id']}"
            for i in installations
        }
        if not found:
            return {}, {"base": "no_installations"}
        return found, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the portal credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._installations, errors = await self._async_fetch_installations(
                user_input
            )
            if not errors:
                self._credentials = user_input
                if len(self._installations) == 1:
                    return await self._async_create(next(iter(self._installations)))
                return await self.async_step_installation()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the installation when the account has several."""
        if user_input is not None:
            return await self._async_create(int(user_input[CONF_INSTALLATION_ID]))

        options = [
            SelectOptionDict(value=str(installation_id), label=name)
            for installation_id, name in self._installations.items()
        ]
        return self.async_show_form(
            step_id="installation",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_INSTALLATION_ID): SelectSelector(
                        SelectSelectorConfig(options=options)
                    )
                }
            ),
        )

    async def _async_create(self, installation_id: int) -> ConfigFlowResult:
        """Create the entry for one installation."""
        await self.async_set_unique_id(str(installation_id))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=self._installations[installation_id],
            data={**self._credentials, CONF_INSTALLATION_ID: installation_id},
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start re-authentication when the credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials; the installation must still be visible."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            installations, errors = await self._async_fetch_installations(user_input)
            if not errors and reauth_entry.data[CONF_INSTALLATION_ID] not in installations:
                errors["base"] = "installation_not_found"
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS_SCHEMA,
                user_input or {CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            ),
            errors=errors,
        )
