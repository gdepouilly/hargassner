"""Tests for Hargassner sensor entities."""

from __future__ import annotations

import pytest

from custom_components.hargassner.const import CONF_INSTALLATION_ID, DOMAIN
from custom_components.hargassner.sensor import (
    SENSOR_DESCRIPTIONS,
    HargassnerSensorEntity,
)

from .conftest import MOCK_PARSED_DATA


class TestHargassnerSensorEntity:
    """Tests for HargassnerSensorEntity."""

    def _make_entity(self, mock_coordinator, description):
        """Helper: build a sensor entity from coordinator + description."""
        return HargassnerSensorEntity(mock_coordinator, description)

    def test_unique_id_format(self, mock_coordinator):
        """Unique ID is composed of installation_id and sensor key."""
        description = SENSOR_DESCRIPTIONS[0]  # outdoor_temperature
        entity = self._make_entity(mock_coordinator, description)
        installation_id = mock_coordinator.config_entry.data[CONF_INSTALLATION_ID]
        assert entity.unique_id == f"{installation_id}_{description.key}"

    def test_outdoor_temperature_value(self, mock_coordinator):
        """Outdoor temperature sensor reads from HEATER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "outdoor_temperature"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(11.7)

    def test_heater_temperature_value(self, mock_coordinator):
        """Heater temperature sensor reads from HEATER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "heater_temperature_current"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(69.9)

    def test_room_temperature_value(self, mock_coordinator):
        """Room temperature sensor reads from HEATING_CIRCUIT_FLOOR_1 widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "room_temperature_current"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(19.2)

    def test_missing_widget_returns_none(self, mock_coordinator):
        """native_value returns None when the widget key is absent from data."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "room_temperature_current"
        )
        mock_coordinator.data = {}  # simulate empty coordinator data
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value is None

    def test_device_info_identifiers(self, mock_coordinator):
        """Device info identifiers use DOMAIN and installation_id."""
        entity = self._make_entity(mock_coordinator, SENSOR_DESCRIPTIONS[0])
        installation_id = mock_coordinator.config_entry.data[CONF_INSTALLATION_ID]
        assert (DOMAIN, str(installation_id)) in entity.device_info["identifiers"]

    def test_device_info_name_from_api(self, mock_coordinator):
        """Device name is taken from HEATER.name returned by the API."""
        entity = self._make_entity(mock_coordinator, SENSOR_DESCRIPTIONS[0])
        assert entity.device_info["name"] == "Test Heater"

    def test_device_info_model_from_api(self, mock_coordinator):
        """Device model is taken from HEATER.device_type returned by the API."""
        entity = self._make_entity(mock_coordinator, SENSOR_DESCRIPTIONS[0])
        assert entity.device_info["model"] == "Nano.2(.3) 15"

    def test_device_info_manufacturer(self, mock_coordinator):
        """Device manufacturer is always 'Hargassner'."""
        entity = self._make_entity(mock_coordinator, SENSOR_DESCRIPTIONS[0])
        assert entity.device_info["manufacturer"] == "Hargassner"

    def test_has_entity_name(self, mock_coordinator):
        """has_entity_name must be True for correct HA naming."""
        entity = self._make_entity(mock_coordinator, SENSOR_DESCRIPTIONS[0])
        assert entity.has_entity_name is True

    def test_heater_temperature_target_value(self, mock_coordinator):
        """Heater target temperature sensor reads from HEATER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "heater_temperature_target"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(75.0)

    def test_smoke_temperature_value(self, mock_coordinator):
        """Smoke temperature sensor reads from HEATER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "smoke_temperature"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(142.5)

    def test_buffer_charge_value(self, mock_coordinator):
        """Buffer charge sensor reads from BUFFER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "buffer_charge"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == 45

    def test_flow_temperature_current_value(self, mock_coordinator):
        """Flow temperature (current) sensor reads from HEATING_CIRCUIT_FLOOR_1 widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "flow_temperature_current"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(24.6)

    def test_flow_temperature_target_value(self, mock_coordinator):
        """Flow temperature (target) sensor reads from HEATING_CIRCUIT_FLOOR_1 widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "flow_temperature_target"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == pytest.approx(24.0)

    def test_heater_state_value(self, mock_coordinator):
        """Heater state sensor reads the 'state' key from the HEATER widget."""
        description = next(
            d for d in SENSOR_DESCRIPTIONS if d.key == "heater_state"
        )
        entity = self._make_entity(mock_coordinator, description)
        assert entity.native_value == "STATE_OFF"


class TestParseWidgets:
    """Tests for the _parse_widgets helper function."""

    def test_basic_parsing(self):
        """Widget list is correctly transformed into a keyed dict."""
        from custom_components.hargassner.coordinator import _parse_widgets

        result = _parse_widgets(
            [
                {"widget": "HEATER", "values": {"outdoor_temperature": 10.0}},
                {"widget": "BUFFER", "values": {"buffer_temperature_top": 50.0}},
            ]
        )
        assert result["HEATER"] == {"outdoor_temperature": 10.0}
        assert result["BUFFER"] == {"buffer_temperature_top": 50.0}

    def test_numbered_widget_suffix(self):
        """Widgets with a 'number' field get a suffixed key."""
        from custom_components.hargassner.coordinator import _parse_widgets

        result = _parse_widgets(
            [
                {
                    "widget": "HEATING_CIRCUIT_FLOOR",
                    "number": "1",
                    "values": {"room_temperature_current": 20.0},
                }
            ]
        )
        assert "HEATING_CIRCUIT_FLOOR_1" in result
        assert result["HEATING_CIRCUIT_FLOOR_1"]["room_temperature_current"] == 20.0

    def test_missing_values_key_defaults_to_empty_dict(self):
        """A widget without a 'values' key maps to an empty dict."""
        from custom_components.hargassner.coordinator import _parse_widgets

        result = _parse_widgets([{"widget": "HEATER"}])
        assert result["HEATER"] == {}
