"""Constants for the CFMoto integration."""

from __future__ import annotations

DOMAIN = "cfmoto"

# CFMoto cloud (reverse-engineered by open-cfmoto).
APP_ID = "rRrIs3ID"
APP_SECRET = "6c1936f85ecb23508c02ceb7a6e3fd0e33eb8bd2"
BASE_URL = "https://tapi.cfmoto-oversea.com/v1.0"
SIGN_TYPE = "0"
VIRTUAL_TOKEN = "cfmoto_virtual_vehicle_token"
NONCE_LENGTH = 16

ENDPOINT_LOGIN = "/fuel-user/serveruser/app/auth/user/login_by_idcard"
ENDPOINT_VEHICLES = "/fuel-vehicle/servervehicle/app/vehicle/mine"
ENDPOINT_VEHICLE = "/fuel-vehicle/servervehicle/app/vehicle"

# Same shape the Android app sends (open-cfmoto cloud-auth.md capture).
USER_AGENT = (
    "MOBILE|Android|35|CFMOTO_INTERNATIONAL_APP|2.2.5|Dalvik/2.1.0 "
    "(Linux; U; Android 15; sdk_gphone64_x86_64 Build/BE31.1-preview4)"
    "|1080x2400|cfmoto-ha|WIFI|Android"
)

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_AREA = "area"
CONF_POLL_INTERVAL = "poll_interval"
CONF_ENABLE_BLE = "enable_ble"

DEFAULT_AREA = "DE"
DEFAULT_POLL_INTERVAL = 60  # seconds

PLATFORMS = ["sensor", "binary_sensor", "device_tracker"]

LOGGER_NAME = __name__
