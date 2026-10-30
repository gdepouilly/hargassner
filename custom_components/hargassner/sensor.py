"""Sensor platform for the Hargassner integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfMass,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HargassnerConfigEntry, HargassnerCoordinator, HargassnerData
from .entity import HargassnerEntity, widget_kind

_LOGGER = logging.getLogger(__name__)

HEATER_STATES = [
    "off",
    "ignition",
    "ignition_wait",
    "efficiency_fire",
    "throttle_efficiency_fire",
    "burn_out",
    "embers_keeping",
    "residual_heating",
    "overheating",
    "deashing",
    "filling",
    "overheat_protection",
    "manual",
    "door_open",
    "door_closed",
    "block_protection",
    "ash_drawer_open",
    "burn_assistant",
    "backup_mode_logs",
]
HEATER_PROGRAMS = [
    "automatic",
    "boiler",
    "chimney_sweeper",
    "manual",
    "off",
    "pellets_disabled",
    "stop_firing",
]
BUFFER_STATES = ["charging", "ignore_request", "manual", "off", "on", "residual_heating"]
CIRCUIT_STATES = [
    "off",
    "heating",
    "cooling",
    "reduction",
    "reduction_transition",
    "daily_nightly_deactivation",
    "summer_deactivation",
    "freeze_protection",
    "screed_heating",
    "manual",
    "residual_heating",
    "solar_heating",
    "boiler_charging",
]


@dataclass(frozen=True, kw_only=True)
class HargassnerSensorEntityDescription(SensorEntityDescription):
    """Sensor reading `values[value_key]` of a widget."""

    value_key: str
    # For enum sensors: API prefix stripped before matching `options`.
    enum_prefix: str | None = None


def _temperature(
    key: str, value_key: str | None = None, **kwargs: Any
) -> HargassnerSensorEntityDescription:
    return HargassnerSensorEntityDescription(
        key=key,
        translation_key=key,
        value_key=value_key or key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        **kwargs,
    )


def _enum(
    key: str, value_key: str, prefix: str, options: list[str]
) -> HargassnerSensorEntityDescription:
    return HargassnerSensorEntityDescription(
        key=key,
        translation_key=key,
        value_key=value_key,
        enum_prefix=prefix,
        device_class=SensorDeviceClass.ENUM,
        options=options,
    )


SENSORS: dict[str, tuple[HargassnerSensorEntityDescription, ...]] = {
    "HEATER": (
        _enum("heater_state", "state", "STATE_", HEATER_STATES),
        _enum("heater_program", "program", "PROGRAM_", HEATER_PROGRAMS),
        _temperature("heater_temperature_current"),
        _temperature("heater_temperature_target"),
        _temperature("smoke_temperature"),
        _temperature("outdoor_temperature"),
        _temperature("outdoor_temperature_average"),
        HargassnerSensorEntityDescription(
            key="efficiency",
            translation_key="efficiency",
            value_key="efficiency",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        HargassnerSensorEntityDescription(
            key="fuel_stock",
            translation_key="fuel_stock",
            value_key="fuel_stock",
            device_class=SensorDeviceClass.WEIGHT,
            native_unit_of_measurement=UnitOfMass.KILOGRAMS,
            state_class=SensorStateClass.MEASUREMENT,
        ),
    ),
    "BUFFER": (
        _enum("buffer_state", "state", "STATE_", BUFFER_STATES),
        HargassnerSensorEntityDescription(
            key="buffer_charge",
            translation_key="buffer_charge",
            value_key="buffer_charge",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        ),
        _temperature("buffer_temperature_top"),
        _temperature("buffer_temperature_center"),
        _temperature("buffer_temperature_bottom"),
        _temperature("max_requirement"),
        HargassnerSensorEntityDescription(
            key="capacity",
            translation_key="capacity",
            value_key="capacity",
            device_class=SensorDeviceClass.VOLUME_STORAGE,
            native_unit_of_measurement=UnitOfVolume.LITERS,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
    ),
    "HEATING_CIRCUIT": (
        _enum("circuit_state", "state", "STATE_", CIRCUIT_STATES),
        _temperature("flow_temperature_current"),
        _temperature("flow_temperature_target"),
        _temperature("room_temperature_current"),
        _temperature("room_temperature_target"),
    ),
}


@dataclass(frozen=True, kw_only=True)
class HargassnerEventSensorEntityDescription(SensorEntityDescription):
    """Sensor computed from installation-level data."""

    value_fn: Callable[[HargassnerData], StateType]


def _active_events(event_type: str) -> Callable[[HargassnerData], StateType]:
    def value(data: HargassnerData) -> StateType:
        if data.event_counts is None:
            return None
        return data.event_counts.get(event_type, {}).get("active")

    return value


EVENT_SENSORS: tuple[HargassnerEventSensorEntityDescription, ...] = (
    HargassnerEventSensorEntityDescription(
        key="active_errors",
        translation_key="active_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_active_events("TYPE_ERROR"),
    ),
    HargassnerEventSensorEntityDescription(
        key="active_warnings",
        translation_key="active_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_active_events("TYPE_WARNING"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HargassnerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create sensors for every known value present in the widgets."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        HargassnerEventSensor(coordinator, description)
        for description in EVENT_SENSORS
    ]
    for key, widget in coordinator.data.widgets.items():
        values = widget.get("values", {})
        entities.extend(
            HargassnerSensor(coordinator, key, description)
            for description in SENSORS.get(widget_kind(widget) or "", ())
            if description.value_key in values
        )
    async_add_entities(entities)


class HargassnerSensor(HargassnerEntity, SensorEntity):
    """A value of a widget."""

    entity_description: HargassnerSensorEntityDescription

    def __init__(
        self,
        coordinator: HargassnerCoordinator,
        key: str,
        description: HargassnerSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, key, description.key)
        self.entity_description = description
        self._unknown_logged: set[str] = set()

    @property
    def native_value(self) -> StateType:
        """Return the value, mapping enum codes to option keys."""
        raw = self.values.get(self.entity_description.value_key)
        prefix = self.entity_description.enum_prefix
        if prefix is None or raw is None:
            return raw
        option = str(raw).removeprefix(prefix).lower()
        if option in (self.entity_description.options or ()):
            return option
        if raw not in self._unknown_logged:
            self._unknown_logged.add(raw)
            _LOGGER.warning(
                "Unknown value %s for %s; please report it", raw, self.entity_id
            )
        return None


class HargassnerEventSensor(HargassnerEntity, SensorEntity):
    """Number of active errors/warnings of the installation."""

    entity_description: HargassnerEventSensorEntityDescription

    def __init__(
        self,
        coordinator: HargassnerCoordinator,
        description: HargassnerEventSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, None, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the active event count."""
        return self.entity_description.value_fn(self.coordinator.data)
