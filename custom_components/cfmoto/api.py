"""Async CFMoto cloud client.

Port of the open-cfmoto cloud client (https://github.com/Asiern/open-cfmoto)
to an `aiohttp`-based async client for Home Assistant. Signing is
byte-compatible with the reference (verified by tests/test_signing.py).
"""

from __future__ import annotations

import hashlib
import json
import secrets
import string
import time
import urllib.parse
from typing import Any

import aiohttp

from .const import (
    APP_ID,
    APP_SECRET,
    BASE_URL,
    ENDPOINT_LOGIN,
    ENDPOINT_VEHICLE,
    ENDPOINT_VEHICLES,
    NONCE_LENGTH,
    SIGN_TYPE,
    USER_AGENT,
    VIRTUAL_TOKEN,
)

_NONCE_ALPHABET = (
    string.digits + string.ascii_uppercase[:25] + string.ascii_lowercase[:25]
)


class CfMotoError(Exception):
    """A CFMoto API call returned an error payload."""

    def __init__(self, message: str, *, code: Any = None, raw: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.raw = raw


class CfMotoAuthError(CfMotoError):
    """Login or an authenticated call failed (bad credentials / expired session)."""


class CfMotoClient:
    """Minimal CFMoto cloud client: login, vehicle list, telemetry detail."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        area: str,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._area = area
        self._token: str | None = None
        self._user_id = ""

    # ------------------------------------------------------------------ #
    # signing (byte-compatible with open-cfmoto)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _nonce() -> str:
        return "".join(secrets.choice(_NONCE_ALPHABET) for _ in range(NONCE_LENGTH))

    @staticmethod
    def _encode(value: Any) -> str:
        # mirrors JS encodeURIComponent (keeps -_.!~*'()) then %20 -> '+'
        return urllib.parse.quote(str(value), safe="-_.!~*'()").replace("%20", "+")

    @classmethod
    def _serialize_query(cls, params: dict[str, Any]) -> str:
        return "&".join(
            f"{k}={cls._encode(v)}" for k, v in sorted(params.items())
        )

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode()).hexdigest()

    @classmethod
    def _normalize_password(cls, password: str) -> str:
        password = password.strip()
        if len(password) == 32 and all(
            c in "0123456789abcdefABCDEF" for c in password
        ):
            return password.lower()
        return cls._md5(password)

    @staticmethod
    def _sign(payload: str, nonce: str, timestamp: str) -> str:
        params = f"appId={APP_ID}&nonce={nonce}&timestamp={timestamp}"
        sha1 = hashlib.sha1((payload + params + APP_SECRET).encode()).hexdigest()
        return hashlib.md5(sha1.encode()).hexdigest()

    def _headers(
        self, payload: str, *, virtual: bool = False, user_id: str | None = None
    ) -> dict[str, str]:
        nonce = self._nonce()
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(payload, nonce, timestamp)
        params = f"appId={APP_ID}&nonce={nonce}&timestamp={timestamp}"
        headers: dict[str, str] = {
            "appId": APP_ID,
            "nonce": nonce,
            "timestamp": timestamp,
            "sign": signature,
            "signature": signature,
            "Cfmoto-X-Param": params,
            "Cfmoto-X-Sign": signature,
            "Cfmoto-X-Sign-Type": SIGN_TYPE,
            "Content-Type": "application/json; charset=UTF-8",
            "User-Agent": USER_AGENT,
            "X-App-Info": USER_AGENT,
            "lang": "en_US",
            "ZoneId": "Europe/Berlin",
        }
        if virtual:
            headers["Authorization"] = f"Bearer {VIRTUAL_TOKEN}"
            headers["user_id"] = ""
        else:
            headers["Authorization"] = f"Bearer {self._token}"
            headers["user_id"] = self._user_id if user_id is None else user_id
        return headers

    # ------------------------------------------------------------------ #
    # http
    # ------------------------------------------------------------------ #
    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        virtual: bool = False,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if query is not None:
            payload = self._serialize_query(query)
            url = BASE_URL + path + "?" + self._serialize_query(query)
            data = None
        elif body is not None:
            payload = json.dumps(body, separators=(",", ":"))
            url = BASE_URL + path
            data = payload.encode()
        else:
            payload = ""
            url = BASE_URL + path
            data = None

        headers = self._headers(payload, virtual=virtual, user_id=user_id)
        async with self._session.request(
            method, url, headers=headers, data=data
        ) as resp:
            raw = await resp.text()

        try:
            result: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CfMotoError(f"Invalid JSON from {path}: {raw[:200]}") from exc

        code = result.get("code")
        ok = code in (0, "0", 200, "200") and result.get("success") is not False
        if not ok:
            msg = result.get("msg") or result.get("message") or "unknown error"
            raise CfMotoError(f"{path}: code={code} msg={msg}", code=code, raw=result)
        return result

    # ------------------------------------------------------------------ #
    # api
    # ------------------------------------------------------------------ #
    @property
    def token(self) -> str | None:
        return self._token

    async def login(self) -> dict[str, Any]:
        body = {
            "idcard": self._email,
            "idcardType": "email" if "@" in self._email else "phone",
            "password": self._normalize_password(self._password),
            "thirdpartyId": "",
            "thirdpartyType": "",
            "areaCode": "",
            "areaNo": self._area,
            "emailMarketingAlarm": False,
            "verifyCode": "",
        }
        try:
            result = await self._request("POST", ENDPOINT_LOGIN, body=body, virtual=True)
        except CfMotoError as exc:
            raise CfMotoAuthError(str(exc), code=exc.code, raw=exc.raw) from exc

        data = result.get("data") or {}
        token_info = data.get("tokenInfo") or {}
        token = token_info.get("accessToken") or data.get("token")
        if not token:
            raise CfMotoAuthError("login response missing access token", raw=result)
        self._token = token
        self._user_id = str(data.get("userId") or "")
        return data

    async def get_vehicles(self) -> list[dict[str, Any]]:
        if not self._token:
            await self.login()
        result = await self._request(
            "GET", ENDPOINT_VEHICLES, query={"position": "2"}, user_id=""
        )
        data = result.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or []
        return []

    async def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        if not self._token:
            await self.login()
        result = await self._request(
            "GET", ENDPOINT_VEHICLE, query={"vehicleId": str(vehicle_id)}
        )
        return result.get("data") or {}
