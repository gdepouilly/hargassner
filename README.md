# Hargassner Home Assistant Integration

A custom Home Assistant integration for monitoring Hargassner heating systems via the Hargassner cloud API (`web.hargassner.at`).

Exposes temperatures, buffer state, and heating circuit data as Home Assistant sensor entities that update every 5 minutes.

---

## Prerequisites

- Home Assistant 2024.1 or newer
- A Hargassner account at [web.hargassner.at](https://web.hargassner.at)
- Your numeric **Installation ID** (see below)

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant → **Integrations** → three-dot menu → **Custom repositories**
2. Add `https://github.com/your-org/hargassner-ha` as category **Integration**
3. Search for **Hargassner** and click **Download**
4. Restart Home Assistant

### Manual install

1. Copy the `custom_components/hargassner/` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

### Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Hargassner** and click it
3. Fill in the form:
   - **Email address** — your Hargassner web portal login email
   - **Password** — your Hargassner web portal password
   - **Installation ID** — numeric ID from the portal URL (see below)
4. Click **Submit**

#### Finding your Installation ID

Log in at [web.hargassner.at](https://web.hargassner.at). The URL of your dashboard looks like:

```
https://web.hargassner.at/installations/53745/dashboard
                                        ^^^^^
                                        This is your Installation ID
```

---

## Removal

1. Go to **Settings → Devices & Services**
2. Find the **Hargassner** integration card
3. Click the three-dot menu → **Delete**

---

## Service Actions

This integration is sensor-only. No service actions are currently available.

---

## Exposed Entities

All entities belong to a single device named after your heating unit.

| Entity | Unit | Description |
|---|---|---|
| Outdoor Temperature | °C | Outside air temperature measured by the heater |
| Heater Temperature | °C | Current boiler/heater temperature |
| Heater Temperature Target | °C | Target boiler temperature |
| Smoke Temperature | °C | Flue gas / exhaust temperature |
| Heater State | — | Operating state (e.g. `STATE_OFF`, `STATE_ON`) |
| Room Temperature | °C | Current room temperature (heating circuit 1) |
| Room Temperature Target | °C | Target room temperature (heating circuit 1) |
| Flow Temperature | °C | Current flow temperature (heating circuit 1) |
| Flow Temperature Target | °C | Target flow temperature (heating circuit 1) |
| Buffer Charge | % | Hot water buffer charge level |

Data refreshes every **5 minutes** (300 seconds).
