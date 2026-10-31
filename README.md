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

## Not supported (by design)

- **Remote ignition / keyless start** — the cloud API has no ignition command
  (only a read-only KL15 state). Ignition control exists only in the BLE
  protocol, which is phone-to-bike and still unverified. This is tracked
  separately, not in this integration.

## Development

- `probe.py` — standalone stdlib probe (login → vehicle list → telemetry), used
  to validate the API against a real VIN. No dependencies.
- `tests/test_signing.py` — pins the signing algorithm against vectors produced
  by the reference JS client. Run with `python3 -m unittest discover -s tests`.

```bash
CFMOTO_EMAIL='you@example.com' CFMOTO_PASSWORD='secret' python3 probe.py --json
```
