"""Shared fixtures for Hargassner integration tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hargassner.api import HargassnerApiClient
from custom_components.hargassner.const import (
    CONF_INSTALLATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
)
from custom_components.hargassner.coordinator import HargassnerCoordinator

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.config_entries import ConfigEntry

# Canned API responses used across tests.
MOCK_TOKEN_DATA = {
    "access_token": "test-access-token",
    "refresh_token": "test-refresh-token",
    "expires_in": 10800,
}

MOCK_WIDGETS_RESPONSE = {
    "data": [
        {
            "widget": "HEATER",
            "values": {
                "heater_temperature_current": 69.9,
                "heater_temperature_target": 75.0,
                "outdoor_temperature": 11.7,
                "smoke_temperature": 142.5,
                "state": "STATE_OFF",
                "device_type": "Nano.2(.3) 15",
                "name": "Test Heater",
            },
        },
        {
            "widget": "BUFFER",
            "values": {"buffer_temperature_top": 70.8, "buffer_charge": 45},
        },
        {
            "widget": "HEATING_CIRCUIT_FLOOR",
            "number": "1",
            "values": {
                "room_temperature_current": 19.2,
                "flow_temperature_current": 24.6,
                "flow_temperature_target": 24.0,
            },
        },
    ],
    "meta": {"refresh": 300, "online_state": True},
}

MOCK_PARSED_DATA = {
    "HEATER": {
        "heater_temperature_current": 69.9,
        "heater_temperature_target": 75.0,
        "outdoor_temperature": 11.7,
        "smoke_temperature": 142.5,
        "state": "STATE_OFF",
        "device_type": "Nano.2(.3) 15",
        "name": "Test Heater",
    },
    "BUFFER": {"buffer_temperature_top": 70.8, "buffer_charge": 45},
    "HEATING_CIRCUIT_FLOOR_1": {
        "room_temperature_current": 19.2,
        "flow_temperature_current": 24.6,
        "flow_temperature_target": 24.0,
    },
}

MOCK_CONFIG_DATA = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
    CONF_INSTALLATION_ID: 12345,
    CONF_REFRESH_TOKEN: "test-refresh-token",
}


@pytest.fixture
def mock_hargassner_api():
    """Return a mock HargassnerApiClient with successful canned responses."""
    api = MagicMock(spec=HargassnerApiClient)
    api.login = AsyncMock(return_value=MOCK_TOKEN_DATA)
    api.get_widgets = AsyncMock(return_value=MOCK_WIDGETS_RESPONSE)
    return api


@pytest.fixture
def mock_config_entry():
    """Return a mock ConfigEntry with test credentials."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = MOCK_CONFIG_DATA
    return entry


@pytest.fixture
def mock_coordinator(mock_hargassner_api, mock_config_entry):
    """Return a coordinator instance with pre-loaded widget data."""
    session = MagicMock()
    hass = MagicMock()

    coordinator = HargassnerCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        api=mock_hargassner_api,
        session=session,
    )
    # Simulate data already fetched by async_config_entry_first_refresh.
    coordinator.data = MOCK_PARSED_DATA
    coordinator._access_token = "test-access-token"
    return coordinator
