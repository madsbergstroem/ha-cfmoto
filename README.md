# ha-cfmoto

Home Assistant integration for CFMoto motorcycles with a T-Box (4G telematics),
built on the reverse-engineered CFMoto Ride cloud API.

Target vehicle: **CFMoto 450MT** (gas, T-Box). Other T-Box models (700MT, 800MT,
etc.) share the same cloud stack and should work too.

> Status: **working, validated against a real 450MT VIN.** Login, vehicle list and
> telemetry (fuel, odometer, battery voltage, GPS, lock states) all return live data.

## How it works

The 450MT does **not** stream telemetry over Bluetooth. The T-Box pushes vehicle
state to the CFMoto cloud, and the app reads it back over HTTPS:

```
T-Box (4G) ──► CFMoto cloud ──► CFMoto Ride app / this integration
```

So a sensor integration only needs the cloud REST API — no BLE, no Frida.

- Base URL: `https://tapi.cfmoto-oversea.com/v1.0`
- Login: `POST /fuel-user/serveruser/app/auth/user/login_by_idcard` (password = MD5)
- Vehicles: `GET /fuel-vehicle/servervehicle/app/vehicle/mine?position=2`
- Telemetry: `GET /fuel-vehicle/servervehicle/app/vehicle?vehicleId=<id>`
- Every request is signed: `signature = MD5( SHA1( payload + "appId=…&nonce=…&timestamp=…" + APP_SECRET ) )`
- No certificate pinning → plain HTTPS works.

Credit for the protocol reverse engineering: [open-cfmoto](https://github.com/Asiern/open-cfmoto)
(cloud client + BLE protocol) and the [Home Assistant community thread](https://community.home-assistant.io/t/cfmoto-someone-researched-to-start-an-integration/737285).

## The one catch: single login session

CFMoto allows **one active session per account**. If Home Assistant logs in, the
CFMoto Ride phone app gets logged out. Fix: in the app share the bike to a
**second CFMoto account** and use that account only for Home Assistant.

## Install

### HACS

Add this repository as a custom repository (category *Integration*), then install **CFMoto**.

### Manual

```bash
# clone into your config's custom_components directory
git clone https://github.com/madsbergstroem/ha-cfmoto.git \
  /config/custom_components/cfmoto
```

Then restart Home Assistant and add the integration from **Settings → Devices &
Services → Add Integration → CFMoto**.

## Configuration

| Field | Meaning |
|-------|---------|
| Email | CFMoto Ride account (the one the bike is linked to) |
| Password | CFMoto Ride password (only its MD5 is ever sent) |
| Country/Region | Account region, e.g. `DE` (default) |

## Entities

Per vehicle you get sensors, binary sensors and a device tracker:

- **Sensors**: odometer, speed, range, battery (12 V) voltage, fuel level,
  fuel level display, average speed, monthly mileage/time, GSM signal,
  vehicle/device state, last update
- **Binary sensors**: T-Box online, vehicle online, T-Box active, ignition (KL15),
  steering/seat/fuel/battery lock
- **Device tracker**: GPS position with altitude and last-report time

## Dashboard card

The integration ships its own Lovelace card (no HACS plugin needed) at
`/cfmoto-static/cfmoto-vehicle-card.js`, served from `custom_components/cfmoto/frontend/`:

1. **Settings → Dashboards → ⋮ → Resources → Add resource**
2. URL `/cfmoto-static/cfmoto-vehicle-card.js?v=0.3.0`, type **JavaScript module**
3. Add the card:

```yaml
type: custom:cfmoto-vehicle-card
entity: sensor.450mt_odometer   # any entity of the vehicle device
name: 450MT
image: /cfmoto-static/cfmoto-450mt.png   # optional, bundled by default
image_navigate: /lovelace/450mt-details  # optional
```

The card finds the other entities through the device registry, so renaming the
device or its entities keeps working. It offers a visual editor (entity, title,
image, click target and the switches below). When the BLE control platform
provides `button.*_power_on/_power_off/_unlock/_lock/_horn`, the card adds a
control row (ignition, unlock, lock, horn); without those buttons the row is
omitted.

| Option | Default | Effect |
|---|---|---|
| `tabs` | `true` | Overview/Map/Details tab bar; `false` renders the overview only |
| `map` | `true` | Map tab with the vehicle tracker (`hui-map-card`) |
| `details` | `true` | Details tab: fuel display, riding time, signal, ignition, T-Box, last data |
| `show_background` | `true` | Blurred vehicle image as ambient backdrop |
| `show_metrics` | `true` | Odometer, month mileage, battery voltage, average speed |
| `show_presence` | `true` | Location, T-Box state and age of the last data |
| `image` | bundled PNG | Vehicle image, also used for the backdrop |
| `image_navigate` | – | Path opened by clicking the image (default: more-info) |

Bump the `?v=` query whenever the card file changes — `/cfmoto-static/` is
cached by the browser. Card tests: `node --test tests/test_card.mjs tests/test_card_render.mjs`
(they run against a DOM shim, no browser needed).

## Keyless / ignition research (separate track)

The cloud API cannot switch the ignition on — it only *reads* KL15 state. Ignition
control exists solely in the phone-to-bike BLE protocol (control `0x67`
`Lock{type=POWER_ON_OFF,state=POWER_ON}`, and `0x79` KL15 whose value range is
still unknown). Reconstructed by [open-cfmoto](https://github.com/Asiern/open-cfmoto)
from APK static analysis, but **never tested against a real bike** (their
hardware-validation issues HW-01…04 are all open).

`tools/ble_probe.py` closes that gap. It logs into the cloud, takes the
per-session BLE keys (`encryptInfo`) and the bike MAC, connects, runs the
4-step auth (0x5A→0x5B→0x5C→0x5D), keeps the heartbeat alive and offers
interactive commands (`lock`, `unlock`, `power-on`, `power-off`, `kl15 <n>`,
`horn`, `flash`, `light`). Every incoming frame is logged — that answers the
open questions (heartbeat ACK code, command ACKs, KL15 behaviour) in one
session next to the bike.

```bash
python3 -m venv .venv && .venv/bin/pip install bleak cryptography
cd tools && CFMOTO_EMAIL=… CFMOTO_PASSWORD=… ../.venv/bin/python ble_probe.py
```

Known unknowns, stated honestly:

- Whether auth really succeeds with cloud `encryptInfo` (static analysis says yes).
- Whether `power-on` only switches the electronics (likely) or also enables
  starting — the engine is additionally protected by a **mechanical steering
  lock and an immobilizer transponder in the physical key**. True keyless
  riding is a physical modification decision, not a software one.

## Not supported (by design)

- **Remote ignition / keyless start** — the cloud API has no ignition command
  (only a read-only KL15 state). Ignition control exists only in the BLE
  protocol, which is phone-to-bike and still unverified. This is tracked
  separately, not in this integration.

## BLE control (experimental, needs live validation)

Home Assistant runs the BLE protocol directly against the T-Box (phone-to-bike
channel, ~10 m range) using the `bluetooth` integration — the same radio HA
already uses for other BLE devices. For each vehicle the integration creates
buttons:

| Button | BLE command |
|--------|-------------|
| `button.<device>_power_on` / `_power_off` | `Lock{type=POWER_ON_OFF,state=POWER_ON/OFF}` |
| `button.<device>_unlock` / `_lock` | `Lock{type=MOTORCYCLE,state=UNLOCKED/LOCKED}` |
| `button.<device>_horn` / `_flash_lights` | `FindCar` loudspeaker / double-flash |
| `button.<device>_ble_test` | connect + auth only, no command |

Every press opens a fresh session: connect → 4-step auth (0x5A–0x5D, AES
challenge-response with the cloud-supplied `encryptInfo` keys) → command →
ACK → disconnect. The result (or error) lands in the button's attributes and
the HA log. Disable via option `enable_ble: false` in the config entry.

⚠️ The protocol is reconstructed from APK static analysis and **has never
been validated against a real bike** (open-cfmoto HW-01…04). `power_on`
switches real hardware — use `ble_test` first when the bike is in BLE range.
Whether `power_on` only powers the electronics (likely) or enables starting
is an open question; the engine is additionally protected by a mechanical
steering lock and an immobilizer transponder in the physical key.

## Development

- `probe.py` — standalone stdlib probe (login → vehicle list → telemetry), used
  to validate the API against a real VIN. No dependencies.
- `tools/ble_probe.py` — standalone interactive BLE client for live protocol
  debugging next to the bike (same wire format as `custom_components/cfmoto/ble.py`).
- `tests/` — `test_signing.py` pins the cloud signing; `test_ble_frames.py` and
  `test_ble.py` pin the frame/proto/AES codec and the auth state machine.
  Run with `python3 -m unittest discover -s tests` (venv with `cryptography`).

```bash
CFMOTO_EMAIL='you@example.com' CFMOTO_PASSWORD='secret' python3 probe.py --json
```
