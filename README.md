# ha-cfmoto

Home Assistant integration for CFMoto motorcycles with a T-Box (4G telematics),
built on the reverse-engineered CFMoto Ride cloud API.

Target vehicle: **CFMoto 450MT** (gas, T-Box). Other T-Box models (700MT, 800MT,
etc.) share the same cloud stack and should work too.

> Status: **probe / validation phase**. The cloud API is cracked and documented
> by [Asiern/open-cfmoto](https://github.com/Asiern/open-cfmoto); this repo turns
> that into a Home Assistant integration. First step is validating the login and
> telemetry endpoints against a real VIN.

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

## Step 1 — validate with the probe

```bash
CFMOTO_EMAIL='you@example.com' CFMOTO_PASSWORD='secret' python3 probe.py
# add --json to dump the raw cloud payloads
```

It prints the vehicle list and the telemetry fields (speed, fuel, GPS, lock
states, online state, BLE key presence). If this returns your bike's live data,
the integration can be built on top.

Environment variables: `CFMOTO_EMAIL`, `CFMOTO_PASSWORD`, `CFMOTO_AREA` (default `DE`).

## Next steps

1. Probe against a real VIN → confirm which fields are populated for the 450MT.
2. Build `custom_components/cfmoto` (config flow + DataUpdateCoordinator + sensors).
3. Optional: MQTT live telemetry (the `getMqttUserInfo` credential blob is still
   undecrypted in open-cfmoto; polling the REST endpoint may be enough).
