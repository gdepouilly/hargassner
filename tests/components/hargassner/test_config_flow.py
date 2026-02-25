"""Tests for the Hargassner config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hargassner.api import HargassnerApiError, HargassnerAuthError
from custom_components.hargassner.const import (
    CONF_INSTALLATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_TOKEN_DATA, MOCK_WIDGETS_RESPONSE

VALID_USER_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
    CONF_INSTALLATION_ID: 12345,
}


@pytest.fixture
def flow_patch():
    """Patch HargassnerApiClient in config_flow with a working mock."""
    with (
        patch(
            "custom_components.hargassner.config_flow.async_get_clientsession"
        ),
        patch(
            "custom_components.hargassner.config_flow.HargassnerApiClient"
        ) as MockApi,
    ):
        instance = MockApi.return_value
        instance.login = AsyncMock(return_value=MOCK_TOKEN_DATA)
        instance.get_widgets = AsyncMock(return_value=MOCK_WIDGETS_RESPONSE)
        yield instance


async def _init_flow(hass):
    """Helper: initialise a user config flow and return the result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    return result


class TestHargassnerConfigFlow:
    """Tests for the user-facing config flow step."""

    async def test_valid_credentials_creates_entry(self, hass, flow_patch):
        """A successful login and widget fetch creates a config entry."""
        await _init_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"] if False else (await _init_flow(hass))["flow_id"],
            user_input=VALID_USER_INPUT,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == f"Hargassner {VALID_USER_INPUT[CONF_INSTALLATION_ID]}"
        data = result["data"]
        assert data[CONF_EMAIL] == VALID_USER_INPUT[CONF_EMAIL]
        assert data[CONF_INSTALLATION_ID] == VALID_USER_INPUT[CONF_INSTALLATION_ID]
        assert data[CONF_REFRESH_TOKEN] == MOCK_TOKEN_DATA["refresh_token"]

    async def test_invalid_auth_shows_error(self, hass):
        """A 401 from the API sets the invalid_auth error on the form."""
        with (
            patch(
                "custom_components.hargassner.config_flow.async_get_clientsession"
            ),
            patch(
                "custom_components.hargassner.config_flow.HargassnerApiClient"
            ) as MockApi,
        ):
            instance = MockApi.return_value
            instance.login = AsyncMock(side_effect=HargassnerAuthError)

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_USER_INPUT
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_cannot_connect_shows_error(self, hass):
        """A network error sets the cannot_connect error on the form."""
        with (
            patch(
                "custom_components.hargassner.config_flow.async_get_clientsession"
            ),
            patch(
                "custom_components.hargassner.config_flow.HargassnerApiClient"
            ) as MockApi,
        ):
            instance = MockApi.return_value
            instance.login = AsyncMock(side_effect=HargassnerApiError)

            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "user"}
            )
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=VALID_USER_INPUT
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_duplicate_installation_aborts(self, hass, flow_patch):
        """Attempting to add the same installation ID twice is aborted."""
        # First entry succeeds.
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_USER_INPUT
        )

        # Second attempt for the same installation_id should abort.
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], user_input=VALID_USER_INPUT
        )
        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"
