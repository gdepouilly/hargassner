"""Binary sensor platform for the Hargassner integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HargassnerConfigEntry, HargassnerCoordinator
from .entity import HargassnerEntity, widget_kind


@dataclass(frozen=True, kw_only=True)
class HargassnerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor reading `values[value_key]` of a widget."""

    value_key: str


PUMP = HargassnerBinarySensorEntityDescription(
    key="pump_active",
    translation_key="pump_active",
    value_key="pump_active",
    device_class=BinarySensorDeviceClass.RUNNING,
)

BINARY_SENSORS: dict[str, tuple[HargassnerBinarySensorEntityDescription, ...]] = {
    "HEATER": (
        HargassnerBinarySensorEntityDescription(
            key="heater_exhaust_guard",
            translation_key="heater_exhaust_guard",
            value_key="heater_exhaust_guard",
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    "BUFFER": (PUMP,),
    "HEATING_CIRCUIT": (
        PUMP,
        HargassnerBinarySensorEntityDescription(
            key="circuit_active",
            translation_key="circuit_active",
            value_key="active",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HargassnerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create binary sensors for every known flag present in the widgets."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = [HargassnerOnlineSensor(coordinator)]
    for key, widget in coordinator.data.widgets.items():
        values = widget.get("values", {})
        entities.extend(
            HargassnerBinarySensor(coordinator, key, description)
            for description in BINARY_SENSORS.get(widget_kind(widget) or "", ())
            if description.value_key in values
        )
    async_add_entities(entities)


class HargassnerBinarySensor(HargassnerEntity, BinarySensorEntity):
    """A boolean value of a widget."""

    entity_description: HargassnerBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HargassnerCoordinator,
        key: str,
        description: HargassnerBinarySensorEntityDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, key, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the flag."""
        value = self.values.get(self.entity_description.value_key)
        return None if value is None else bool(value)


class HargassnerOnlineSensor(HargassnerEntity, BinarySensorEntity):
    """Whether the boiler is connected to the portal (meta.online_state)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "online"

    def __init__(self, coordinator: HargassnerCoordinator) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, None, "online")

    @property
    def is_on(self) -> bool | None:
        """Return the portal connection state."""
        return self.coordinator.data.online
