"""Tests for setup, sensors, binary sensors and the mode select."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hargassner.api import HargassnerApiError, HargassnerAuthError
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

MODE_RESOURCE = "/installations/12345/widgets/heating-circuits/1/parameters/mode"
MODE_SELECT = "select.plancher_mode"


@pytest.mark.parametrize(
    ("entity_id", "state"),
    [
        ("sensor.home_state", "efficiency_fire"),
        ("sensor.home_program", "automatic"),
        ("sensor.home_boiler_temperature", "68.6"),
        ("sensor.home_flue_gas_temperature", "156.9"),
        ("sensor.home_outdoor_temperature", "11.4"),
        ("sensor.home_output", "96"),
        ("sensor.home_fuel_stock", "488"),
        ("sensor.home_active_errors", "0"),
        ("sensor.buffer_state", "charging"),
        ("sensor.buffer_charge", "23"),
        ("sensor.buffer_top_temperature", "38"),
        ("sensor.buffer_maximum_requirement", "32"),
        ("sensor.plancher_state", "heating"),
        ("sensor.plancher_flow_temperature", "33.1"),
        ("sensor.plancher_room_temperature", "17.1"),
        ("sensor.plancher_room_temperature_target", "23.9"),
        ("binary_sensor.buffer_pump", "on"),
        ("binary_sensor.plancher_pump", "on"),
        ("binary_sensor.plancher_active", "on"),
        ("binary_sensor.home_portal_connection", "on"),
        (MODE_SELECT, "heating"),
    ],
)
async def test_entity_states(
    hass: HomeAssistant, init_integration: MockConfigEntry, entity_id: str, state: str
) -> None:
    """Values from the captured payload are exposed."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get(entity_id).state == state


async def test_devices(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Heater device plus buffer and circuit sub-devices."""
    heater = device_registry.async_get_device(identifiers={("hargassner", "12345")})
    assert heater.model == "Nano.2(.3) 15"
    assert heater.sw_version == "v14"
    circuit = device_registry.async_get_device(
        identifiers={("hargassner", "12345_HEATING_CIRCUIT_FLOOR_1")}
    )
    assert circuit.name == "PLANCHER"
    assert circuit.via_device_id == heater.id


async def test_only_present_values_create_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """No entity is created for values missing from the payload."""
    entries = er.async_entries_for_config_entry(
        entity_registry, init_integration.entry_id
    )
    unique_ids = {entry.unique_id for entry in entries}
    assert "12345_HEATER_heater_state" in unique_ids
    assert "12345_HEATING_CIRCUIT_FLOOR_1_mode" in unique_ids
    assert not any("BOILER" in uid for uid in unique_ids)


async def test_mode_options(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The six portal modes, in dialog order."""
    assert hass.states.get(MODE_SELECT).attributes[ATTR_OPTIONS] == [
        "off",
        "automatic",
        "heating",
        "bridge_reduction",
        "reduction",
        "bridge_heating",
    ]


@pytest.mark.parametrize(
    ("option", "api_value"),
    [
        ("off", "MODE_OFF"),
        ("automatic", "MODE_AUTOMATIC"),
        ("bridge_reduction", "MODE_BRIDGE_REDUCTION"),
        ("bridge_heating", "MODE_BRIDGE_HEATING"),
    ],
)
async def test_select_mode_writes_parameter(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api: AsyncMock,
    option: str,
    api_value: str,
) -> None:
    """Selecting a mode PATCHes the circuit's mode resource."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: MODE_SELECT, ATTR_OPTION: option},
        blocking=True,
    )
    mock_api.async_set_parameter.assert_awaited_once_with(MODE_RESOURCE, api_value)


async def test_select_mode_error(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """API failures surface as HomeAssistantError and keep the old state."""
    mock_api.async_set_parameter.side_effect = HargassnerApiError("boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: MODE_SELECT, ATTR_OPTION: "off"},
            blocking=True,
        )
    assert hass.states.get(MODE_SELECT).state == "heating"


async def test_unknown_enum_value(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """An unexpected state code yields unknown instead of an error."""
    payload = mock_api.async_get_widgets.return_value
    payload["data"][0]["values"]["state"] = "STATE_SOMETHING_NEW"
    await init_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.home_state").state == STATE_UNKNOWN


async def test_setup_auth_failure_starts_reauth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Rejected credentials put the entry in reauth."""
    mock_api.async_get_installations.side_effect = HargassnerAuthError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_setup_connection_failure_retries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Connection errors make the entry retry later."""
    mock_api.async_get_widgets.side_effect = HargassnerApiError
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The entry unloads cleanly."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
