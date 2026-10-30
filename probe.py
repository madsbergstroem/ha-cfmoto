#!/usr/bin/env python3
"""CFMoto 450MT cloud API probe.

Validates the whole chain against a real account/VIN:
    login -> vehicle list -> telemetry detail

Zero dependencies (stdlib only). Mirrors the open-cfmoto cloud client
(https://github.com/Asiern/open-cfmoto, packages/cloud-client).

Usage:
    CFMOTO_EMAIL='you@example.com' CFMOTO_PASSWORD='secret' python3 probe.py
    CFMOTO_EMAIL=... CFMOTO_PASSWORD=... python3 probe.py --json   # raw payloads

WARNING: CFMoto allows only ONE active login session. Running this logs the
CFMoto Ride phone app out. For a permanent HA setup share the bike to a
dedicated second account and use that one here.

The plaintext password is never stored; only its MD5 is sent, exactly like the app.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

APP_ID = "rRrIs3ID"
APP_SECRET = "6c1936f85ecb23508c02ceb7a6e3fd0e33eb8bd2"
BASE_URL = "https://tapi.cfmoto-oversea.com/v1.0"
SIGN_TYPE = "0"
VIRTUAL_TOKEN = "cfmoto_virtual_vehicle_token"

# Same shape the app sends; the server does not appear to validate it strictly.
USER_AGENT = (
    "MOBILE|Android|35|CFMOTO_INTERNATIONAL_APP|2.2.5|Dalvik/2.1.0 "
    "(Linux; U; Android 15; sdk_gphone64_x86_64 Build/BE31.1-preview4)"
    "|1080x2400|cfmoto-probe|WIFI|Android"
)

# APK SecureRandom draws from 0-9, A-Y, a-y (no Z/z).
NONCE_CHARS = string.digits + string.ascii_uppercase[:25] + string.ascii_lowercase[:25]

ENDPOINTS = {
    "login": "/fuel-user/serveruser/app/auth/user/login_by_idcard",
    "vehicles": "/fuel-vehicle/servervehicle/app/vehicle/mine",
    "vehicle": "/fuel-vehicle/servervehicle/app/vehicle",
}


# --------------------------------------------------------------------------- #
# signing
# --------------------------------------------------------------------------- #
def make_nonce(length: int = 16) -> str:
    return "".join(random.choice(NONCE_CHARS) for _ in range(length))


def _encode(value: str) -> str:
    # mirror JS encodeURIComponent (keeps -_.!~*'()) then %20 -> '+'
    return urllib.parse.quote(str(value), safe="-_.!~*'()").replace("%20", "+")


def serialize_query(params: dict) -> str:
    return "&".join(f"{k}={_encode(v)}" for k, v in sorted(params.items()))


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def normalize_password(password: str) -> str:
    password = password.strip()
    if len(password) == 32 and all(c in "0123456789abcdefABCDEF" for c in password):
        return password.lower()
    return md5_hex(password)


def compute_signature(payload: str, nonce: str, timestamp: str) -> str:
    params = f"appId={APP_ID}&nonce={nonce}&timestamp={timestamp}"
    raw = payload + params + APP_SECRET
    sha1 = hashlib.sha1(raw.encode()).hexdigest()
    return hashlib.md5(sha1.encode()).hexdigest()


def signed_headers(payload: str) -> dict:
    nonce = make_nonce()
    timestamp = str(int(time.time() * 1000))
    signature = compute_signature(payload, nonce, timestamp)
    params = f"appId={APP_ID}&nonce={nonce}&timestamp={timestamp}"
    return {
        "appId": APP_ID,
        "nonce": nonce,
        "timestamp": timestamp,
        "sign": signature,
        "signature": signature,
        "Cfmoto-X-Param": params,
        "Cfmoto-X-Sign": signature,
        "Cfmoto-X-Sign-Type": SIGN_TYPE,
    }


# --------------------------------------------------------------------------- #
# http
# --------------------------------------------------------------------------- #
def request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    query: dict | None = None,
    token: str | None = None,
    user_id: str = "",
    virtual_auth: bool = False,
) -> dict:
    if query is not None:
        sign_payload = serialize_query(query)
        url = BASE_URL + path + "?" + serialize_query(query)
    elif body is not None:
        sign_payload = json.dumps(body, separators=(",", ":"))
        url = BASE_URL + path
    else:
        sign_payload = ""
        url = BASE_URL + path

    headers = signed_headers(sign_payload)
    headers["Content-Type"] = "application/json; charset=UTF-8"
    headers["User-Agent"] = USER_AGENT
    headers["X-App-Info"] = USER_AGENT
    headers["lang"] = "en_US"
    headers["ZoneId"] = "Europe/Berlin"

    if virtual_auth:
        headers["Authorization"] = f"Bearer {VIRTUAL_TOKEN}"
        headers["user_id"] = ""
    else:
        headers["Authorization"] = f"Bearer {token}"
        headers["user_id"] = user_id

    data = sign_payload.encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        print(f"[HTTP {exc.code}] {path}", file=sys.stderr)
        print(raw, file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"[network] {path}: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(f"[invalid JSON] {path}: {raw[:500]}", file=sys.stderr)
        sys.exit(1)

    code = payload.get("code")
    ok = code in (0, "0", 200, "200") and payload.get("success") is not False
    if not ok:
        msg = payload.get("msg") or payload.get("message") or "unknown error"
        print(f"[API error] {path}: code={code} msg={msg}", file=sys.stderr)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)

    return payload


# --------------------------------------------------------------------------- #
# API calls
# --------------------------------------------------------------------------- #
def login(email: str, password: str, area_no: str) -> tuple[str, str, dict]:
    body = {
        "idcard": email,
        "idcardType": "email" if "@" in email else "phone",
        "password": normalize_password(password),
        "thirdpartyId": "",
        "thirdpartyType": "",
        "areaCode": "",
        "areaNo": area_no,
        "emailMarketingAlarm": False,
        "verifyCode": "",
    }
    payload = request("POST", ENDPOINTS["login"], body=body, virtual_auth=True)
    data = payload.get("data") or {}
    token_info = data.get("tokenInfo") or {}
    token = token_info.get("accessToken") or data.get("token")
    if not token:
        print("[login] response has no access token", file=sys.stderr)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    return token, str(data.get("userId") or ""), data


def get_vehicles(token: str) -> list[dict]:
    payload = request(
        "GET", ENDPOINTS["vehicles"], query={"position": "2"}, token=token
    )
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("data") or []
    return []


def get_vehicle_detail(token: str, user_id: str, vehicle_id: str) -> dict:
    payload = request(
        "GET",
        ENDPOINTS["vehicle"],
        query={"vehicleId": vehicle_id},
        token=token,
        user_id=user_id,
    )
    return payload.get("data") or {}


# --------------------------------------------------------------------------- #
# output
# --------------------------------------------------------------------------- #
def _fmt(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def print_vehicle_detail(detail: dict) -> None:
    geo = detail.get("geoLocation") or {}
    enc = detail.get("encryptInfo") or {}
    print("  identity:")
    for key in ("vehicleId", "vin", "btMac"):
        print(f"    {key:<16} {_fmt(detail.get(key))}")
    print("  connectivity:")
    for key in ("isOnline", "deviceState", "vehicleState", "tboxIsActive", "supportRemoteUnlock"):
        print(f"    {key:<16} {_fmt(detail.get(key))}")
    print("  telemetry:")
    for key in ("speed", "remainingOil", "remainingOilStr", "totalRideMile", "rideMileageMonth", "kl"):
        print(f"    {key:<16} {_fmt(detail.get(key))}")
    print("  locks:")
    for key in ("headLockState", "seatLockState", "oilLockState", "batteryLockState", "vcuLockState"):
        print(f"    {key:<16} {_fmt(detail.get(key))}")
    print("  location:")
    for key in ("lat", "lon", "speed", "altitude"):
        print(f"    {key:<16} {_fmt(geo.get(key))}")
    print("  ble keys (encryptInfo):")
    for key in ("encryptValue", "key", "iv"):
        present = "yes" if enc.get(key) else "no"
        print(f"    {key:<16} {present}")


def main() -> None:
    email = os.environ.get("CFMOTO_EMAIL", "").strip()
    password = os.environ.get("CFMOTO_PASSWORD", "")
    area_no = os.environ.get("CFMOTO_AREA", "DE").strip().upper()
    dump_json = "--json" in sys.argv

    if not email or not password:
        print(
            "Set CFMOTO_EMAIL and CFMOTO_PASSWORD (optionally CFMOTO_AREA, default DE).\n"
            "Example:\n"
            "  CFMOTO_EMAIL='you@example.com' CFMOTO_PASSWORD='secret' python3 probe.py",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"login as {email} (area {area_no}) ...")
    token, user_id, login_data = login(email, password, area_no)
    print(f"  ok  userId={_fmt(user_id)}  region={_fmt(login_data.get('region'))}")
    print(f"  token={token[:8]}… (len {len(token)})")

    print("fetch vehicle list ...")
    vehicles = get_vehicles(token)
    if not vehicles:
        print("  no vehicles on this account", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(vehicles)} vehicle(s):")
    for v in vehicles:
        print(
            f"    vehicleId={_fmt(v.get('vehicleId'))} "
            f"name={_fmt(v.get('vehicleName'))} "
            f"vin={_fmt(v.get('vin'))} "
            f"virtual={_fmt(v.get('virtualFlag'))}"
        )

    if dump_json:
        print("\n=== raw vehicle list ===")
        print(json.dumps(vehicles, ensure_ascii=False, indent=2))

    real = [v for v in vehicles if str(v.get("virtualFlag")) not in ("1", "True", "true")]
    targets = real or vehicles

    for v in targets:
        vid = str(v.get("vehicleId"))
        print(f"\nfetch telemetry for vehicleId={vid} ...")
        detail = get_vehicle_detail(token, user_id, vid)
        print_vehicle_detail(detail)
        if dump_json:
            print("\n=== raw detail ===")
            print(json.dumps(detail, ensure_ascii=False, indent=2))

    print("\ndone.")


if __name__ == "__main__":
    main()
