# Hargassner web portal API (web.hargassner.at)

Captured 2026-10-30 from portal v2.7.18 and its JS bundle (`/build/assets/app-*.js`).
Base URL: `https://web.hargassner.at/api`. Every call except login/refresh takes `Authorization: Bearer <access_token>`.
Sample responses (anonymised) are in `payloads/`.

## Auth
| Call | Body | Notes |
|---|---|---|
| `POST /auth/login` | `{email, password, client_id: "1", client_secret}` | Returns `{access_token, refresh_token, token_type: "Bearer", expires_in: 10800}` |
| `POST /auth/refresh` | `{refresh_token, client_id: "1", client_secret}` | Same response as login |

The `client_secret` is a fixed 40-character value in the JS bundle, unchanged from hargassner-ha.

## Reads
| Call | Use |
|---|---|
| `GET /installations?sort=name&pageSize=36&page=1` | Lists installations: `data[].id`, `name`, `devices[].type`, `series`, `software.version_product` |
| `GET /installations/{id}/widgets` | All live values. `data[]` = `{widget, number?, values{}, parameters{}, actions{}?}`; `meta` = `{refresh: 300, online_state, current_timestamp}` |
| `GET /installations/{id}/events-counts` | `{data: {TYPE_ERROR: {active, history}, TYPE_WARNING: {...}, TYPE_EVENT: {...}}}` |

## Writes
- **Parameters:** `PATCH <parameters.X.resource>` with body `{"value": <new value>}`. `resource` is relative to the base URL, e.g. `/installations/{id}/widgets/heating-circuits/1/parameters/mode`.
- **Actions:** `POST <actions.X.resource>` with no body, e.g. `force_charging` or `start_heating`. Not used by the integration.

## Widget values (this installation)
- **HEATER**
  - `state` (STATE_*, see below), `program` (PROGRAM_*)
  - `smoke_temperature`, `heater_temperature_current`, `heater_temperature_target`, `outdoor_temperature`, `outdoor_temperature_average` (°C)
  - `efficiency` (%), `fuel_stock` (kg), `heater_exhaust_guard` (bool)
  - `name`, `device_type`
- **BUFFER**
  - `state`
  - `buffer_charge` (%), `capacity` (L)
  - `buffer_temperature_top`, `buffer_temperature_center`, `buffer_temperature_bottom`, `max_requirement` (°C)
  - `pump_active` (bool)
- **HEATING_CIRCUIT_FLOOR** (number 1, "PLANCHER")
  - `state`
  - `flow_temperature_current`, `flow_temperature_target`, `room_temperature_current`, `room_temperature_target`, `outdoor_temperature`, `outdoor_temperature_average` (°C)
  - `pump_active`, `active` (bool)
  - `name`
  - **Current mode** comes from `parameters.mode.value`, with the allowed values in `parameters.mode.options`.

## Heating circuit modes (portal labels)
| API value | FR | EN |
|---|---|---|
| MODE_OFF | Arrêt | off |
| MODE_AUTOMATIC | Auto | auto |
| MODE_HEATING | Confort | heating |
| MODE_REDUCTION | Réduit | lowering |
| MODE_BRIDGE_REDUCTION | **1x Confort** | 1x heating |
| MODE_BRIDGE_HEATING | **1x Réduit** | 1x lowering |

The "bridge" names are the opposite of what they look like: MODE_BRIDGE_REDUCTION skips the next reduced period, so it is a one-time comfort period, and MODE_BRIDGE_HEATING is a one-time reduced period. The portal's icons and labels confirm this.

## State / program values
- **HEATER state:** off, ignition, ignition_wait, efficiency_fire, throttle_efficiency_fire, burn_out, embers_keeping, residual_heating, overheating, deashing, filling, overheat_protection, manual, door_open, door_closed, block_protection, ash_drawer_open, burn_assistant, backup_mode_logs.
- **HEATER program:** automatic, boiler, chimney_sweeper, manual, off, pellets_disabled, stop_firing.
- **BUFFER state:** charging, ignore_request, manual, off, on, residual_heating.
- **Heating circuit state:** off, heating, cooling, reduction, reduction_transition, daily_nightly_deactivation, summer_deactivation, freeze_protection, screed_heating, manual, residual_heating, solar_heating, boiler_charging.

The API sends these as `STATE_<UPPER>` / `PROGRAM_<UPPER>`. The FR/EN labels are in `custom_components/hargassner/translations/`.
