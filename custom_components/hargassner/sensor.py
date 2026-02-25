"""Sensor platform for the Hargassner integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_INSTALLATION_ID, DOMAIN  # DOMAIN used for DeviceInfo identifiers
from .coordinator import HargassnerCoordinator


@dataclass(frozen=True, kw_only=True)
class HargassnerSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with Hargassner-specific fields."""

    widget: str = ""      # Key in coordinator.data (e.g. "HEATER").
    value_key: str = ""   # Key inside the widget values dict.


SENSOR_DESCRIPTIONS: tuple[HargassnerSensorEntityDescription, ...] = (
    HargassnerSensorEntityDescription(
        key="outdoor_temperature",
        widget="HEATER",
        value_key="outdoor_temperature",
        name="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="heater_temperature_current",
        widget="HEATER",
        value_key="heater_temperature_current",
        name="Heater Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="room_temperature_current",
        widget="HEATING_CIRCUIT_FLOOR_1",
        value_key="room_temperature_current",
        name="Room Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="heater_temperature_target",
        widget="HEATER",
        value_key="heater_temperature_target",
        name="Heater Temperature Target",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="smoke_temperature",
        widget="HEATER",
        value_key="smoke_temperature",
        name="Smoke Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="buffer_charge",
        widget="BUFFER",
        value_key="buffer_charge",
        name="Buffer Charge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HargassnerSensorEntityDescription(
        key="flow_temperature_current",
        widget="HEATING_CIRCUIT_FLOOR_1",
        value_key="flow_temperature_current",
        name="Flow Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="flow_temperature_target",
        widget="HEATING_CIRCUIT_FLOOR_1",
        value_key="flow_temperature_target",
        name="Flow Temperature Target",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HargassnerSensorEntityDescription(
        key="heater_state",
        widget="HEATER",
        value_key="state",
        name="Heater State",
    ),
)


class HargassnerSensorEntity(
    CoordinatorEntity[HargassnerCoordinator], SensorEntity
):
    """A temperature sensor fed by the Hargassner coordinator."""

    entity_description: HargassnerSensorEntityDescription
    has_entity_name = True

    def __init__(
        self,
        coordinator: HargassnerCoordinator,
        description: HargassnerSensorEntityDescription,
    ) -> None:
        """Initialise the sensor and set up device info."""
        super().__init__(coordinator)
        self.entity_description = description
        installation_id = coordinator.config_entry.data[CONF_INSTALLATION_ID]
        self._attr_unique_id = f"{installation_id}_{description.key}"

        heater_data = (coordinator.data or {}).get("HEATER", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(installation_id))},
            name=heater_data.get("name", f"Hargassner {installation_id}"),
            manufacturer="Hargassner",
            model=heater_data.get("device_type"),
            configuration_url=(
                f"https://web.hargassner.at/installations/{installation_id}/dashboard"
            ),
        )

    @property
    def native_value(self) -> float | None:
        """Return the current sensor value from coordinator data."""
        widget_data = (self.coordinator.data or {}).get(
            self.entity_description.widget, {}
        )
        return widget_data.get(self.entity_description.value_key)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hargassner sensors from a config entry."""
    coordinator: HargassnerCoordinator = config_entry.runtime_data
    async_add_entities(
        HargassnerSensorEntity(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )
