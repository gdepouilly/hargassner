"""Base entity for the Hargassner integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HargassnerCoordinator


class HargassnerEntity(CoordinatorEntity[HargassnerCoordinator]):
    """Entity bound to one widget (or to the installation when key is None)."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HargassnerCoordinator, key: str | None, entity_key: str
    ) -> None:
        """Set unique id and device from the widget key."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = (
            f"{coordinator.installation_id}_{key or 'INSTALLATION'}_{entity_key}"
        )
        self._attr_device_info = coordinator.device_info(key)

    @property
    def widget(self) -> dict[str, Any]:
        """Raw widget dict, empty when the widget disappeared."""
        if self._key is None:
            return {}
        return self.coordinator.data.widgets.get(self._key, {})

    @property
    def values(self) -> dict[str, Any]:
        """The widget's `values` dict."""
        return self.widget.get("values", {})

    @property
    def available(self) -> bool:
        """Unavailable when the widget is no longer reported."""
        return super().available and (self._key is None or bool(self.widget))


def widget_kind(widget: dict[str, Any]) -> str | None:
    """Group raw widget types: HEATER, BUFFER or HEATING_CIRCUIT."""
    widget_type = widget.get("widget", "")
    if widget_type.startswith("HEATING_CIRCUIT"):
        return "HEATING_CIRCUIT"
    if widget_type in ("HEATER", "BUFFER"):
        return widget_type
    return None
