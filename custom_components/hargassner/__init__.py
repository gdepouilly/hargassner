"""The Hargassner integration."""

from __future__ import annotations

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HargassnerApiClient
from .coordinator import HargassnerConfigEntry, HargassnerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HargassnerConfigEntry) -> bool:
    """Set up Hargassner from a config entry."""
    api = HargassnerApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = HargassnerCoordinator(hass, entry, api)

    # Raises ConfigEntryNotReady (from UpdateFailed) or starts reauth
    # (from ConfigEntryAuthFailed) — both handled by Home Assistant.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HargassnerConfigEntry) -> bool:
    """Unload a Hargassner config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
