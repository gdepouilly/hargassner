"""DataUpdateCoordinator for the Hargassner integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HargassnerApiClient, HargassnerApiError, HargassnerAuthError
from .const import CONF_INSTALLATION_ID, DEFAULT_SCAN_INTERVAL, DOMAIN, PORTAL_URL

_LOGGER = logging.getLogger(__name__)

type HargassnerConfigEntry = ConfigEntry[HargassnerCoordinator]


@dataclass
class HargassnerData:
    """Snapshot of one installation."""

    # Raw widget dicts keyed by type, suffixed with the number when present:
    # "HEATER", "BUFFER", "HEATING_CIRCUIT_FLOOR_1", ...
    widgets: dict[str, dict[str, Any]] = field(default_factory=dict)
    online: bool | None = None
    # {"TYPE_ERROR": {"active": 0, "history": 10}, ...}; None if unavailable.
    event_counts: dict[str, dict[str, int]] | None = None


def widget_key(widget: dict[str, Any]) -> str:
    """Return the coordinator key of a raw widget."""
    if widget.get("number") is not None:
        return f"{widget['widget']}_{widget['number']}"
    return widget["widget"]


class HargassnerCoordinator(DataUpdateCoordinator[HargassnerData]):
    """Polls widgets and event counts of one installation."""

    config_entry: HargassnerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HargassnerConfigEntry,
        api: HargassnerApiClient,
    ) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.installation_id: int = config_entry.data[CONF_INSTALLATION_ID]
        self.installation: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        """Load installation metadata once, for device info."""
        try:
            installations = await self.api.async_get_installations()
        except HargassnerAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except HargassnerApiError as err:
            raise UpdateFailed(f"Error fetching installations: {err}") from err
        self.installation = next(
            (i for i in installations if i.get("id") == self.installation_id), {}
        )

    async def _async_update_data(self) -> HargassnerData:
        """Fetch the latest data."""
        try:
            raw = await self.api.async_get_widgets(self.installation_id)
            event_counts = await self._async_get_event_counts()
        except HargassnerAuthError as err:
            raise ConfigEntryAuthFailed("Authentication failed") from err
        except HargassnerApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

        return HargassnerData(
            widgets={widget_key(w): w for w in raw.get("data", [])},
            online=raw.get("meta", {}).get("online_state"),
            event_counts=event_counts,
        )

    async def _async_get_event_counts(self) -> dict[str, dict[str, int]] | None:
        """Event counts are secondary: a failure must not fail the update."""
        try:
            return await self.api.async_get_event_counts(self.installation_id)
        except HargassnerApiError as err:
            _LOGGER.debug("Could not fetch event counts: %s", err)
            return None

    async def async_set_parameter(
        self, key: str, parameter: str, api_value: Any
    ) -> None:
        """Write a widget parameter, update local state, then refresh."""
        param = self.data.widgets[key]["parameters"][parameter]
        try:
            await self.api.async_set_parameter(param["resource"], api_value)
        except HargassnerAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HargassnerApiError("Authentication failed") from err
        # The boiler applies the change asynchronously; reflect it right away.
        param["value"] = api_value
        self.async_update_listeners()
        await self.async_request_refresh()

    @property
    def heater_device_identifier(self) -> tuple[str, str]:
        """Identifier of the main (heater) device."""
        return (DOMAIN, str(self.installation_id))

    def device_info(self, key: str | None) -> DeviceInfo:
        """Device for a widget; the heater device also hosts installation-level entities."""
        configuration_url = (
            f"{PORTAL_URL}/installations/{self.installation_id}/dashboard"
        )
        widget = self.data.widgets.get(key or "", {}) if self.data else {}
        values = widget.get("values", {})

        if key is None or widget.get("widget") == "HEATER":
            heater = self.data.widgets.get("HEATER", {}).get("values", {})
            device = (self.installation.get("devices") or [{}])[0]
            software = device.get("software") or {}
            return DeviceInfo(
                identifiers={self.heater_device_identifier},
                name=heater.get("name")
                or self.installation.get("name")
                or f"Hargassner {self.installation_id}",
                manufacturer="Hargassner",
                model=heater.get("device_type") or device.get("type"),
                sw_version=software.get("version_product"),
                configuration_url=configuration_url,
            )

        custom_name = (
            widget.get("parameters", {}).get("name", {}).get("value")
            or values.get("name")
        )
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.installation_id}_{key}")},
            name=custom_name or _default_device_name(widget),
            manufacturer="Hargassner",
            model=widget.get("widget", "").replace("_", " ").title(),
            via_device=self.heater_device_identifier,
            configuration_url=configuration_url,
        )


def _default_device_name(widget: dict[str, Any]) -> str:
    """Fallback device name, e.g. "Buffer" or "Heating circuit 1"."""
    if widget.get("widget", "").startswith("HEATING_CIRCUIT"):
        name = "Heating circuit"
    else:
        name = widget.get("widget", "").replace("_", " ").capitalize()
    if widget.get("number") is not None:
        name = f"{name} {widget['number']}"
    return name
