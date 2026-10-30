"""Tests for the Hargassner config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner.api import HargassnerApiError, HargassnerAuthError
from custom_components.hargassner.const import CONF_INSTALLATION_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import INSTALLATION_ID, MOCK_CONFIG_DATA

CREDENTIALS = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}


async def test_single_installation_creates_entry(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """With one installation the entry is created right after login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == MOCK_CONFIG_DATA
    assert result["result"].unique_id == str(INSTALLATION_ID)


async def test_multiple_installations_asks_which(
    hass: HomeAssistant, mock_api: AsyncMock
) -> None:
    """With several installations the user picks one."""
    mock_api.async_get_installations.return_value = [
        {"id": 1, "name": "Cabin"},
        {"id": 2, "name": "House"},
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "installation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_INSTALLATION_ID: "2"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "House"
    assert result["data"][CONF_INSTALLATION_ID] == 2


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (HargassnerAuthError, "invalid_auth"),
        (HargassnerApiError, "cannot_connect"),
    ],
)
async def test_login_errors(
    hass: HomeAssistant, mock_api: AsyncMock, side_effect: type, error: str
) -> None:
    """Login failures are shown on the form, and the user can retry."""
    mock_api.async_login.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["errors"] == {"base": error}

    mock_api.async_login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_no_installations(hass: HomeAssistant, mock_api: AsyncMock) -> None:
    """An account without installations cannot be added."""
    mock_api.async_get_installations.return_value = []
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["errors"] == {"base": "no_installations"}


async def test_already_configured(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The same installation cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth stores the new password."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CREDENTIALS, CONF_PASSWORD: "new-secret"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"


async def test_reauth_installation_missing(
    hass: HomeAssistant, mock_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth with an account that cannot see the installation is refused."""
    mock_config_entry.add_to_hass(hass)
    mock_api.async_get_installations.return_value = [{"id": 999, "name": "Other"}]
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CREDENTIALS
    )
    assert result["errors"] == {"base": "installation_not_found"}
