# Hargassner Home Assistant Integration — Architecture Reference

> Generated: 2026-02-25 | Version: 0.1.1

---

## 1. Project Overview

| Property | Value |
|---|---|
| **Type** | Home Assistant Custom Integration (Hub, Cloud Polling) |
| **Domain** | `hargassner` |
| **Python** | >= 3.12 |
| **IoT Class** | `cloud_polling` — fetches data every 300 s |
| **Config Flow** | Yes — user-friendly setup wizard |

Monitors a Hargassner heating system via the Hargassner cloud API (`web.hargassner.at`). Exposes temperatures, buffer state, and heating circuit data as Home Assistant sensor entities.

---

## 2. Directory Structure

```
hargassner-ha/
├── custom_components/hargassner/   # Integration root
│   ├── __init__.py                 # Setup/teardown entry points
│   ├── api.py                      # Pure async HTTP client (no HA deps)
│   ├── config_flow.py              # UI setup wizard
│   ├── const.py                    # API URLs, credentials, defaults
│   ├── coordinator.py              # DataUpdateCoordinator + widget parser
│   ├── sensor.py                   # SensorEntity definitions (10 sensors)
│   ├── manifest.json               # Integration metadata
│   ├── strings.json                # UI strings (source)
│   └── translations/en.json        # English translations
├── tests/components/hargassner/
│   ├── conftest.py                 # Shared fixtures + mock data
│   ├── test_init.py                # Setup/unload tests
│   ├── test_config_flow.py         # Config flow tests
│   └── test_sensor.py              # Sensor entity + widget parser tests
├── payloads/widgets.json           # Real API response example
└── pyproject.toml                  # Project config (uv, pytest)
```

---

## 3. File-by-File Reference

### `const.py`
Central constants. **First place to look** for API endpoints, OAuth credentials, and config keys.

```python
API_CLIENT_ID     = "1"
API_CLIENT_SECRET = "aSYsAYj7Gsl5v9tPEDdS1hhXTUezgJk1NhOZ1bHR"
API_LOGIN_URL     = "https://web.hargassner.at/api/auth/login"
API_WIDGETS_URL   = "https://web.hargassner.at/api/installations/{installation_id}/widgets"
CONF_INSTALLATION_ID = "installation_id"
CONF_REFRESH_TOKEN   = "refresh_token"
DEFAULT_SCAN_INTERVAL = 300   # seconds
DOMAIN = "hargassner"
```

### `api.py`
**Pure async HTTP client — zero Home Assistant imports.** Can be tested in isolation.

| Class/Exception | Purpose |
|---|---|
| `HargassnerAuthError` | Raised on HTTP 401 |
| `HargassnerApiError` | Raised on any other HTTP error or network failure |
| `HargassnerApiClient.login()` | POST to `API_LOGIN_URL` with email/password + OAuth creds → returns `{access_token, refresh_token, expires_in}` |
| `HargassnerApiClient.get_widgets()` | GET `API_WIDGETS_URL` with Bearer token → returns raw widget list |

Authentication payload sent:
```json
{
  "email": "<email>",
  "password": "<password>",
  "client_id": "1",
  "client_secret": "..."
}
```

### `coordinator.py`
Bridges the API client with Home Assistant's update scheduling.

| Symbol | Purpose |
|---|---|
| `HargassnerCoordinator` | Extends `DataUpdateCoordinator`, 300-second interval |
| `_async_update_data()` | Fetches widgets; re-authenticates on 401 then retries once |
| `_authenticate()` | Calls `api.login()`, stores token **in-memory only** |
| `_parse_widgets(data)` | Module-level function: converts widget list → keyed dict |

`_parse_widgets` transformation:
```
Input (API):  [{"widget": "HEATING_CIRCUIT_FLOOR", "number": "1", "values": {...}}, ...]
Output (HA):  {"HEATING_CIRCUIT_FLOOR_1": {...}, "HEATER": {...}, ...}
```
Widgets **without** a `number` field use the widget type as-is. Widgets **with** a number get `_{number}` appended.

**Token lifecycle:** access_token lives only in `coordinator._access_token` (RAM). refresh_token is persisted to config entry but currently unused — re-login is used on expiry instead.

### `config_flow.py`
Two flows are implemented:

**Initial setup (`async_step_user`)** collects:
- `email` (str)
- `password` (str)
- `installation_id` (int)

Validation sequence:
1. Call `api.login()` → auth error → show `invalid_auth`
2. Call `api.get_widgets()` → network error → show `cannot_connect`
3. `async_set_unique_id(installation_id)` → duplicate → abort `already_configured`
4. Success → create entry with `{email, password, installation_id, refresh_token}`

**Re-authentication (`async_step_reauth` → `async_step_reauth_confirm`)** triggered by `ConfigEntryAuthFailed`:
- Prompts for `email` (pre-filled from existing entry) and `password`
- Calls `api.login()` only — no `get_widgets` call
- On success: calls `async_update_reload_and_abort()` to update `email`, `password`, `refresh_token` in the existing entry and reload it

### `__init__.py`
`async_setup_entry()`:
1. Gets shared `aiohttp.ClientSession` via `async_get_clientsession(hass)`
2. Creates `HargassnerApiClient`
3. Creates `HargassnerCoordinator`
4. Calls `async_config_entry_first_refresh()` (first data fetch; raises `ConfigEntryNotReady` if unreachable)
5. Stores coordinator at `entry.runtime_data`
6. Forwards setup to `["sensor"]` platform

`async_unload_entry()`: unloads sensor platform (no manual cleanup needed — `runtime_data` is managed by HA).

### `sensor.py`
| Symbol | Purpose |
|---|---|
| `HargassnerSensorEntityDescription` | Frozen dataclass extending `SensorEntityDescription`; adds `widget` and `value_key` fields |
| `SENSOR_DESCRIPTIONS` | Tuple of 9 sensor descriptors (see table below) |
| `HargassnerSensorEntity` | `CoordinatorEntity` + `SensorEntity`; reads from `coordinator.data[widget][value_key]` |

`native_value` lookup path:
```python
coordinator.data[description.widget][description.value_key]  # None if missing
```

Device info is read from `coordinator.data["HEATER"]`:
- `name` → device name
- `device_type` → model
- Manufacturer hardcoded: `"Hargassner"`
- Config URL: `https://web.hargassner.at/installations/{id}/dashboard`

---

## 4. Defined Sensors

| `key` | `widget` | `value_key` | Unit | Device Class | State Class |
|---|---|---|---|---|---|
| `outdoor_temperature` | `HEATER` | `outdoor_temperature` | °C | temperature | measurement |
| `heater_temperature_current` | `HEATER` | `heater_temperature_current` | °C | temperature | measurement |
| `heater_temperature_target` | `HEATER` | `heater_temperature_target` | °C | temperature | measurement |
| `smoke_temperature` | `HEATER` | `smoke_temperature` | °C | temperature | measurement |
| `heater_state` | `HEATER` | `state` | — | — | — |
| `room_temperature_current` | `HEATING_CIRCUIT_FLOOR_1` | `room_temperature_current` | °C | temperature | measurement |
| `flow_temperature_current` | `HEATING_CIRCUIT_FLOOR_1` | `flow_temperature_current` | °C | temperature | measurement |
| `flow_temperature_target` | `HEATING_CIRCUIT_FLOOR_1` | `flow_temperature_target` | °C | temperature | measurement |
| `buffer_charge` | `BUFFER` | `buffer_charge` | % | — | measurement |

Unique ID format: `{installation_id}_{key}` (e.g. `53745_outdoor_temperature`)

---

## 5. API Data Model

### Login Response
```json
{
  "access_token": "eyJ...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 10800
}
```

### Widgets Response (`GET /api/installations/{id}/widgets`)
```json
{
  "data": [
    {
      "widget": "HEATER",
      "values": {
        "name": "Depouilly",
        "device_type": "Nano.2(.3) 15",
        "state": "STATE_OFF",
        "smoke_temperature": 57.4,
        "heater_temperature_target": null,
        "heater_temperature_current": 52.1,
        "outdoor_temperature": 10.2,
        "outdoor_temperature_average": 10.7,
        "efficiency": 0,
        "program": "PROGRAM_AUTOMATIC",
        "fuel_stock": 0
      },
      "parameters": { "fuel_stock": { "value": 0, "min": 0, "max": 32000, "step": 1 } }
    },
    {
      "widget": "BUFFER",
      "values": {
        "state": "STATE_ON",
        "buffer_charge": 45,
        "capacity": 300,
        "buffer_temperature_top": 65.9,
        "buffer_temperature_center": 32.4,
        "buffer_temperature_bottom": 25.8,
        "pump_active": false
      }
    },
    {
      "widget": "HEATING_CIRCUIT_FLOOR",
      "number": "1",
      "values": {
        "name": "PLANCHER",
        "state": "STATE_REDUCTION",
        "flow_temperature_target": 24,
        "flow_temperature_current": 24.6,
        "room_temperature_target": 19.3,
        "room_temperature_current": 19.7,
        "pump_active": true
      }
    }
  ],
  "meta": {
    "refresh": 300,
    "current_timestamp": "2026-02-25T20:42:12+01:00",
    "online_state": true
  }
}
```

Known widget types: `HEATER`, `BUFFER`, `HEATING_CIRCUIT_FLOOR` (numbered).

---

## 6. Data Flow

```
──────────────────────────────────────────────────────────────────
SETUP (once)
──────────────────────────────────────────────────────────────────
User fills config form
  → config_flow validates (login + get_widgets)
  → ConfigEntry created {email, password, installation_id, refresh_token}

async_setup_entry()
  → HargassnerApiClient created
  → HargassnerCoordinator created
  → first_refresh() → _authenticate() + _async_update_data()
  → coordinator stored in entry.runtime_data
  → 9 × HargassnerSensorEntity created, each holding a ref to coordinator

──────────────────────────────────────────────────────────────────
PERIODIC UPDATE (every 300 s)
──────────────────────────────────────────────────────────────────
DataUpdateCoordinator scheduler fires
  → _async_update_data()
      ├─ no token? → _authenticate() → POST /api/auth/login
      ├─ GET /api/installations/{id}/widgets  (Bearer token)
      ├─ HTTP 401? → _authenticate() → retry once
      └─ success → _parse_widgets() → coordinator.data updated

HargassnerSensorEntity.native_value (polled by HA)
  → reads coordinator.data[widget][value_key]
  → returns float / str / None

──────────────────────────────────────────────────────────────────
ERRORS
──────────────────────────────────────────────────────────────────
HargassnerAuthError  → ConfigEntryAuthFailed → HA triggers reauth UI
HargassnerApiError   → UpdateFailed → coordinator retries with backoff
aiohttp.ClientError  → wrapped as HargassnerApiError
```

---

## 7. Error Handling Map

| Situation | Exception raised | HA handling |
|---|---|---|
| HTTP 401 (login) | `HargassnerAuthError` | `ConfigEntryAuthFailed` → reauth flow |
| HTTP 401 (widgets) | `HargassnerAuthError` | re-authenticate once, then `UpdateFailed` |
| HTTP 4xx/5xx | `HargassnerApiError` | `UpdateFailed` → backoff + retry |
| Network error | `aiohttp.ClientError` → `HargassnerApiError` | same as above |
| First refresh fails | `ConfigEntryNotReady` | HA retries setup |

---

## 8. Configuration Entry Storage

Stored in HA's encrypted `.storage/core.config_entries`:

```python
{
    "email": str,             # Hargassner account email
    "password": str,          # Hargassner account password
    "installation_id": int,   # Numeric installation ID (also used as unique_id)
    "refresh_token": str,     # Token from login (stored but currently unused)
}
```

Access in code: `entry.data["email"]`, `entry.data[CONF_INSTALLATION_ID]`, etc.

---

## 9. Coordinator Storage

The integration uses the modern `entry.runtime_data` pattern (not `hass.data`):

```python
# __init__.py — setup
entry.runtime_data = coordinator  # type: HargassnerCoordinator

# sensor.py — reading it back
coordinator: HargassnerCoordinator = config_entry.runtime_data
```

Sensor entities then access the coordinator via the `coordinator` property inherited from `CoordinatorEntity`.

---

## 10. Test Suite

| File | What it tests |
|---|---|
| `conftest.py` | Shared fixtures: `mock_hargassner_api`, `mock_config_entry`, `mock_coordinator`; canned `MOCK_TOKEN_DATA`, `MOCK_WIDGETS_RESPONSE`, `MOCK_PARSED_DATA`, `MOCK_CONFIG_DATA` |
| `test_init.py` | `async_setup_entry` success/auth-failure/api-failure; `async_unload_entry` cleanup |
| `test_config_flow.py` | Valid flow → entry created; auth error; network error; duplicate abort |
| `test_sensor.py` | `native_value` for each sensor; missing widget → `None`; `unique_id` format; device info; `_parse_widgets` edge cases |

Run: `uv run pytest` or `pytest` from project root.

---

## 11. Known Limitations & Extension Points

### Current Limitations
- **Refresh token unused** — full re-login on every token expiry
- **Only numbered circuit `_1`** — `HEATING_CIRCUIT_FLOOR_2..N` not dynamically created
- **No write support** — `parameters` and `actions` from API are ignored
- **10 sensors only** — many available values (buffer temps, efficiency, fuel stock…) not exposed

### Extension Opportunities
| Feature | Platform | Data source |
|---|---|---|
| Buffer top/center/bottom temps | `sensor` | `BUFFER.buffer_temperature_*` |
| Pump active states | `binary_sensor` | `BUFFER.pump_active`, `HEATING_CIRCUIT_FLOOR_1.pump_active` |
| Heating mode | `select` | `HEATER.program` |
| Fuel stock | `number` | `HEATER.parameters.fuel_stock` |
| Force charging | `button` / `switch` | `BUFFER.force_charging_active` |
| Climate control | `climate` | `HEATING_CIRCUIT_FLOOR_1.room_temperature_*` |
| Dynamic circuits | `sensor` (dynamic) | Any `HEATING_CIRCUIT_FLOOR_N` |
