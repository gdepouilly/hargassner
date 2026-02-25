"""Tests for Hargassner integration setup and teardown."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.hargassner.api import HargassnerApiError, HargassnerAuthError
from custom_components.hargassner.coordinator import HargassnerCoordinator

from homeassistant.config_entries import ConfigEntryState

from .conftest import MOCK_CONFIG_DATA, MOCK_TOKEN_DATA, MOCK_WIDGETS_RESPONSE


@pytest.fixture
def setup_patches():
    """Patch API client and session for integration setup tests."""
    with (
        patch(
            "custom_components.hargassner.async_get_clientsession"
        ),
        patch(
            "custom_components.hargassner.HargassnerApiClient"
        ) as MockApi,
    ):
        instance = MockApi.return_value
        instance.login = AsyncMock(return_value=MOCK_TOKEN_DATA)
        instance.get_widgets = AsyncMock(return_value=MOCK_WIDGETS_RESPONSE)
        yield instance


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    async def test_setup_stores_coordinator(self, hass, setup_patches, mock_config_entry):
        """A successful setup stores the coordinator in entry.runtime_data."""
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert isinstance(mock_config_entry.runtime_data, HargassnerCoordinator)

    async def test_setup_fails_on_auth_error(self, hass, mock_config_entry):
        """ConfigEntryAuthFailed during first refresh marks entry as failed."""
        with (
            patch("custom_components.hargassner.async_get_clientsession"),
            patch("custom_components.hargassner.HargassnerApiClient") as MockApi,
        ):
            instance = MockApi.return_value
            instance.login = AsyncMock(side_effect=HargassnerAuthError)

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR

    async def test_setup_retries_on_api_error(self, hass, mock_config_entry):
        """UpdateFailed during first refresh results in ConfigEntryNotReady."""
        with (
            patch("custom_components.hargassner.async_get_clientsession"),
            patch("custom_components.hargassner.HargassnerApiClient") as MockApi,
        ):
            instance = MockApi.return_value
            instance.login = AsyncMock(return_value=MOCK_TOKEN_DATA)
            instance.get_widgets = AsyncMock(side_effect=HargassnerApiError)

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


class TestAsyncUnloadEntry:
    """Tests for async_unload_entry."""

    async def test_unload_removes_coordinator(self, hass, setup_patches, mock_config_entry):
        """Unloading an entry transitions the entry to unloaded state."""
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
