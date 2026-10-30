"""Shared fixtures for Hargassner integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner.const import CONF_INSTALLATION_ID, DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

FIXTURES = Path(__file__).parent / "fixtures"
INSTALLATION_ID = 12345

MOCK_CONFIG_DATA = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret",
    CONF_INSTALLATION_ID: INSTALLATION_ID,
}


def load_fixture(name: str) -> Any:
    """Load a captured (anonymised) API response."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations for all tests in this package."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for installation 12345."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id=str(INSTALLATION_ID),
        data=MOCK_CONFIG_DATA,
    )


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Patch the API client everywhere it is constructed."""
    with (
        patch(
            "custom_components.hargassner.HargassnerApiClient", autospec=True
        ) as client_cls,
        patch(
            "custom_components.hargassner.config_flow.HargassnerApiClient",
            new=client_cls,
        ),
    ):
        api = client_cls.return_value
        api.async_get_installations.return_value = load_fixture("installations.json")[
            "data"
        ]
        api.async_get_widgets.return_value = load_fixture("widgets.json")
        api.async_get_event_counts.return_value = load_fixture("events_counts.json")[
            "data"
        ]
        yield api


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> MockConfigEntry:
    """Set up the integration with the captured payloads."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
