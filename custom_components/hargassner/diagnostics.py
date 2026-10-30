"""Diagnostics support for the Hargassner integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import HargassnerConfigEntry

TO_REDACT = {CONF_EMAIL, CONF_PASSWORD, "name", "creator", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HargassnerConfigEntry
) -> dict[str, Any]:
    """Return redacted entry data and the latest API snapshot."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "data": async_redact_data(asdict(coordinator.data), TO_REDACT),
    }
