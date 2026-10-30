"""Select platform for the Hargassner integration: heating circuit mode."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import HargassnerApiError
from .const import DOMAIN
from .coordinator import HargassnerConfigEntry, HargassnerCoordinator
from .entity import HargassnerEntity, widget_kind

MODE_PREFIX = "MODE_"
# Order of the portal's "Choisir Mode" dialog. Note the API naming:
# MODE_BRIDGE_REDUCTION = "1x Confort", MODE_BRIDGE_HEATING = "1x Réduit".
CIRCUIT_MODES = [
    "off",
    "automatic",
    "heating",
    "bridge_reduction",
    "reduction",
    "bridge_heating",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HargassnerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create a mode select for heating circuits exposing a writable mode."""
    coordinator = entry.runtime_data
    async_add_entities(
        HargassnerCircuitModeSelect(coordinator, key)
        for key, widget in coordinator.data.widgets.items()
        if widget_kind(widget) == "HEATING_CIRCUIT"
        and "resource" in widget.get("parameters", {}).get("mode", {})
    )


class HargassnerCircuitModeSelect(HargassnerEntity, SelectEntity):
    """Operating mode of a heating circuit."""

    _attr_translation_key = "circuit_mode"

    def __init__(self, coordinator: HargassnerCoordinator, key: str) -> None:
        """Initialise the select."""
        super().__init__(coordinator, key, "mode")

    @property
    def _mode(self) -> dict:
        return self.widget.get("parameters", {}).get("mode", {})

    @property
    def options(self) -> list[str]:
        """Modes offered by the API that we have labels for."""
        offered = {
            option.removeprefix(MODE_PREFIX).lower()
            for option in self._mode.get("options", [])
        }
        return [mode for mode in CIRCUIT_MODES if mode in offered]

    @property
    def current_option(self) -> str | None:
        """Return the current mode."""
        value = self._mode.get("value")
        if value is None:
            return None
        option = value.removeprefix(MODE_PREFIX).lower()
        return option if option in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Change the mode on the boiler."""
        try:
            await self.coordinator.async_set_parameter(
                self._key, "mode", f"{MODE_PREFIX}{option.upper()}"
            )
        except HargassnerApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_mode_failed",
                translation_placeholders={"error": str(err)},
            ) from err
