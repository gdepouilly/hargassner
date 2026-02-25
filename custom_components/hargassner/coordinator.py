"""DataUpdateCoordinator for the Hargassner integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HargassnerApiClient, HargassnerApiError, HargassnerAuthError
from .const import CONF_INSTALLATION_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HargassnerCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches widget data from the Hargassner API on a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        api: HargassnerApiClient,
        session,
    ) -> None:
        """Set up the coordinator with API client and session."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.session = session
        self._access_token: str | None = None  # in-memory only, never persisted

    async def _async_update_data(self) -> dict:
        """Fetch data from API, re-authenticating on token expiry."""
        if not self._access_token:
            await self._authenticate()

        try:
            raw = await self.api.get_widgets(
                self.session,
                self._access_token,
                self.config_entry.data[CONF_INSTALLATION_ID],
            )
        except HargassnerAuthError:
            # Token expired: re-authenticate once and retry.
            await self._authenticate()
            try:
                raw = await self.api.get_widgets(
                    self.session,
                    self._access_token,
                    self.config_entry.data[CONF_INSTALLATION_ID],
                )
            except HargassnerAuthError as err:
                raise ConfigEntryAuthFailed("Authentication failed") from err
        except HargassnerApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return _parse_widgets(raw["data"])

    async def _authenticate(self) -> None:
        """Log in and store the access token in memory."""
        try:
            token_data = await self.api.login(
                self.session,
                self.config_entry.data[CONF_EMAIL],
                self.config_entry.data[CONF_PASSWORD],
            )
            self._access_token = token_data["access_token"]
        except HargassnerAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except HargassnerApiError as err:
            raise UpdateFailed(f"Cannot connect to Hargassner: {err}") from err


def _parse_widgets(data: list) -> dict:
    """Transform the API widget list into a dict keyed by widget type.

    Multi-instance widgets (those with a "number" field) get a suffixed key,
    e.g. "HEATING_CIRCUIT_FLOOR_1".

    Example output:
      {
        "HEATER": {"outdoor_temperature": 11.7, ...},
        "BUFFER": {"buffer_temperature_top": 70.8},
        "HEATING_CIRCUIT_FLOOR_1": {"room_temperature_current": 19.2},
      }
    """
    result = {}
    for widget in data:
        key = widget["widget"]
        if "number" in widget:
            key = f"{key}_{widget['number']}"
        result[key] = widget.get("values", {})
    return result
