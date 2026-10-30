# Hargassner for Home Assistant

A custom integration (installable through HACS) for Hargassner pellet boilers connected to the cloud portal [web.hargassner.at](https://web.hargassner.at). It reads the same data as the portal dashboard every 5 minutes, and lets you change the operating mode of your heating circuits.

## Installation
1. In HACS, go to ⋮ → *Custom repositories*, add this repository and choose the category *Integration*.
2. Install **Hargassner**, then restart Home Assistant.
3. Go to *Settings → Devices & services → Add integration → Hargassner*.
4. Sign in with your portal account. If the account has several installations, pick the one to add.

## Entities
**Boiler** (main device):
- Sensors: state, program, boiler temperature and target, flue gas temperature, outdoor temperature (current and average), output %, fuel stock, active errors and active warnings.
- Binary sensors: exhaust guard, portal connection.

**Buffer** (sub-device):
- Sensors: state, charge %, top/middle/bottom temperatures, maximum requirement, capacity.
- Binary sensor: pump.

**Each heating circuit** (sub-device, named as in the portal, e.g. "PLANCHER"):
- Sensors: state, flow temperature and target, room temperature and target.
- Binary sensors: pump, active.
- **Mode** select with the same six choices as the portal: Off, Auto, Comfort, 1x Comfort, Reduced, 1x Reduced.

A sensor is only created when the portal actually reports that value. States are translated (EN/FR) using the portal's own labels.

## Notes
- The portal refreshes its data every 300 s, so the integration polls at the same rate.
- Setting a mode sends `PATCH …/heating-circuits/<n>/parameters/mode`, the same request the portal makes.
- Diagnostics are redacted (email, password, names).
- API notes: [research/api.md](research/api.md).

## Development
```sh
uv sync
uv run pytest
```
