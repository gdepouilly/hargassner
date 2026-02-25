"""The Hargassner integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HargassnerApiClient
from .coordinator import HargassnerCoordinator

_PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hargassner from a config entry."""
    session = async_get_clientsession(hass)
    api = HargassnerApiClient()
    coordinator = HargassnerCoordinator(hass, entry, api, session)

    # Raises ConfigEntryNotReady (from UpdateFailed) or starts reauth flow
    # (from ConfigEntryAuthFailed) — both handled automatically by HA.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hargassner config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
