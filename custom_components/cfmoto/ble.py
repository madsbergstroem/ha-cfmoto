"""BLE client for the CFMoto 450MT T-Box (control-only channel).

Wire format, proto field numbers and the 4-step auth flow are documented in
open-cfmoto (docs/protocol.md, docs/auth-protocol.md, meter.proto). Nothing in
this module has ever run against a real bike — treat every result as evidence,
not as proof.

Only the cloud-read telemetry integration is safe to enable by default. BLE
commands switch real hardware (ignition, locks, horn) and are therefore only
reachable through explicit button presses.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# --- protocol constants (open-cfmoto docs/protocol.md, uuids.ts, codec.ts) ---
SERVICE_MAIN = "0000b354-d6d8-c7ec-bdf0-eab1bfc6bcbc"
CHAR_WRITE = "0000b356-d6d8-c7ec-bdf0-eab1bfc6bcbc"
CHAR_NOTIFY = "0000b357-d6d8-c7ec-bdf0-eab1bfc6bcbc"

HEADER_0, HEADER_1, FRAME_END = 0xAB, 0xCD, 0xCF

CTRL_AUTH_PACKAGE = 0x5A       # app -> bike, auth step 1
CTRL_TBOX_RANDOM_NUM = 0x5B    # bike -> app, auth step 2
CTRL_RANDOM_NUM = 0x5C         # app -> bike, auth step 3
CTRL_TBOX_AUTH_RESULT = 0x5D   # bike -> app, auth step 4
CTRL_LOCK_CONTROL = 0x67       # app -> bike, lock/unlock/power + heartbeat
CTRL_FIND_CAR = 0x6A           # app -> bike, horn/flash/headlight
CTRL_LOCK_RESULT = 0xE7        # bike -> app, lock/unlock/power ACK
CTRL_KEEP_ALIVE_RESULT = 0xEC  # bike -> app, heartbeat ACK (candidate)

CTRL_NAMES = {
    CTRL_AUTH_PACKAGE: "AUTH_PACKAGE",
    CTRL_TBOX_RANDOM_NUM: "TBOX_RANDOM_NUM",
    CTRL_RANDOM_NUM: "RANDOM_NUM",
    CTRL_TBOX_AUTH_RESULT: "TBOX_AUTH_RESULT",
    CTRL_LOCK_CONTROL: "LOCK_CONTROL",
    CTRL_FIND_CAR: "FIND_CAR",
    CTRL_LOCK_RESULT: "LOCK_RESULT",
    CTRL_KEEP_ALIVE_RESULT: "KEEP_ALIVE_RESULT",
}

LOCK_TYPE = {"unlock": 1, "lock": 1, "power_on": 7, "power_off": 7}  # Type.MOTORCYCLE=1, POWER_ON_OFF=7
LOCK_STATE = {"unlock": 1, "lock": 2, "power_on": 3, "power_off": 4}


class BleError(Exception):
    """A BLE exchange failed in a way worth showing to the user."""


# --- minimal protobuf codec (meter.proto field numbers only) ---
def _varint(n: int) -> bytes:
    out = bytearray()
    n &= 0xFFFFFFFFFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _field_bytes(field: int, data: bytes) -> bytes:
    return bytes([(field << 3) | 2]) + _varint(len(data)) + data


def _field_varint(field: int, n: int) -> bytes:
    return bytes([(field << 3) | 0]) + _varint(n)


def _field_str(field: int, s: str) -> bytes:
    return _field_bytes(field, s.encode("utf-8"))


def proto_auth_package(raw: bytes) -> bytes:
    return _field_bytes(1, raw)


def proto_random_num(sn: str) -> bytes:
    return _field_str(1, sn)


def proto_heartbeat() -> bytes:
    return _field_varint(1, 1)


def proto_lock(kind: str) -> bytes:
    return _field_varint(1, LOCK_TYPE[kind]) + _field_varint(2, LOCK_STATE[kind])


def proto_find_car(head: bool, flash: bool, horn: bool) -> bytes:
    # only true fields are encoded — mirrors protobuf-es fromPartial in the JS client
    out = bytearray()
    for field, value in ((1, head), (2, flash), (3, horn)):
        if value:
            out += _field_varint(field, 1)
    return bytes(out)


def parse_fields(payload: bytes) -> list[tuple[int, int, object]]:
    """Return [(field_no, wire_type, value)] — value int or bytes."""
    fields = []
    i = 0
    while i < len(payload):
        tag = payload[i]
        i += 1
        fnum, wire = tag >> 3, tag & 7
        if wire == 0:
            v = 0
            shift = 0
            while True:
                b = payload[i]
                i += 1
                v |= (b & 0x7F) << shift
                if not b & 0x80:
                    break
                shift += 7
            fields.append((fnum, wire, v))
        elif wire == 2:
            ln = 0
            shift = 0
            while True:
                b = payload[i]
                i += 1
                ln |= (b & 0x7F) << shift
                if not b & 0x80:
                    break
                shift += 7
            fields.append((fnum, wire, payload[i : i + ln]))
            i += ln
        else:
            raise ValueError(f"wire type {wire} nicht unterstützt")
    return fields


def describe_payload(payload: bytes) -> str:
    try:
        parts = []
        for fnum, wire, value in parse_fields(payload):
            if wire == 0:
                parts.append(f"f{fnum}={value}")
            else:
                parts.append(f"f{fnum}={value.hex()}")
        return "{" + ", ".join(parts) + "}"
    except Exception:  # noqa: BLE001
        return payload.hex()


# --- frame codec (codec.ts) ---
def build_frame(control: int, payload: bytes) -> bytes:
    n = len(payload)
    frame = bytearray(7 + n)
    frame[0], frame[1], frame[2] = HEADER_0, HEADER_1, control & 0xFF
    frame[3], frame[4] = n & 0xFF, (n >> 8) & 0xFF
    frame[5 : 5 + n] = payload
    frame[5 + n] = sum(frame[2 : 5 + n]) & 0xFF  # byte addition, NOT xor
    frame[6 + n] = FRAME_END
    return bytes(frame)


def parse_frame(data: bytes) -> tuple[int, bytes] | None:
    if len(data) < 7 or data[0] != HEADER_0 or data[1] != HEADER_1 or data[-1] != FRAME_END:
        return None
    control = data[2]
    n = data[3] | (data[4] << 8)
    if len(data) != 7 + n:
        return None
    if data[5 + n] != sum(data[2 : 5 + n]) & 0xFF:
        return None
    return control, bytes(data[5 : 5 + n])


# --- AES (mirrors AES256EncryptionUtil.decrypt + crypto-js auto key size) ---
def _aes_ecb_pkcs7_decrypt(ciphertext: bytes, key_utf8: str) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    key = key_utf8.encode("utf-8")
    if len(key) not in (16, 24, 32):
        raise BleError(
            f"AES-Key aus encryptInfo.key hat {len(key)} Bytes (UTF-8) — erwartet 16/24/32"
        )
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    try:
        return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise BleError(f"AES-Entschlüsselung des Bike-Challenge fehlgeschlagen: {exc}") from exc


def decode_codec(codec: bytes) -> bytes:
    """TboxRandomNum.codec -> ciphertext bytes (hex string per APK analysis)."""
    text = codec.decode("utf-8", errors="replace")
    if all(c in "0123456789abcdefABCDEF" for c in text):
        return bytes.fromhex(text)
    raise BleError(f"codec ist kein Hex-String: {codec[:64].hex()}")


class CfMotoBle:
    """One authenticated command session against the T-Box."""

    def __init__(
        self,
        hass: Any,
        mac: str,
        encrypt_value: str,
        key: str,
        logger: logging.Logger = _LOGGER,
    ) -> None:
        self.hass = hass
        self.mac = mac
        self.encrypt_value = encrypt_value
        self.key = key
        self.log = logger
        self.client: BleakClientWrapper | None = None
        self._notify_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()
        self._auth_done = False
        self._heartbeat_task: asyncio.Task | None = None

    # --- internals ----------------------------------------------------------
    def _on_notify(self, _char, data: bytearray) -> None:
        parsed = parse_frame(bytes(data))
        if parsed is None:
            self.log.debug("BLE-Rohdaten ohne Frame: %s", bytes(data).hex())
            return
        control, payload = parsed
        self.log.debug(
            "<<< %s %s", CTRL_NAMES.get(control, hex(control)), describe_payload(payload)
        )
        self._notify_queue.put_nowait((control, payload))

    async def _write_frame(self, control: int, payload: bytes) -> None:
        assert self.client is not None
        frame = build_frame(control, payload)
        self.log.debug(
            ">>> %s (%d bytes) %s",
            CTRL_NAMES.get(control, hex(control)),
            len(frame),
            describe_payload(payload),
        )
        try:
            await self.client.write_gatt_char(CHAR_WRITE, frame, response=True)
        except Exception as exc:  # noqa: BLE001 — some stacks reject write-with-response
            self.log.debug("write mit response fehlgeschlagen (%s) — ohne response", exc)
            await self.client.write_gatt_char(CHAR_WRITE, frame, response=False)

    async def _wait_for(self, control: int, timeout: float) -> bytes:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise BleError(
                    f"kein Frame {CTRL_NAMES.get(control, hex(control))} in {timeout:.0f}s"
                )
            try:
                got, payload = await asyncio.wait_for(self._notify_queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                raise BleError(
                    f"kein Frame {CTRL_NAMES.get(control, hex(control))} in {timeout:.0f}s"
                ) from None
            if got == control:
                return payload

    async def _authenticate(self) -> None:
        """Auth 0x5A -> 0x5B -> 0x5C -> 0x5D, timings per BleModel.java."""
        assert self.client is not None
        if not self.encrypt_value or not self.key:
            raise BleError("encryptInfo (encryptValue/key) fehlt in den Cloud-Daten")

        raw = bytes.fromhex(self.encrypt_value)
        self.log.info("BLE-Auth Schritt 1/4: AuthPackage (%d Bytes)", len(raw))
        await self._write_frame(CTRL_AUTH_PACKAGE, proto_auth_package(raw))

        payload = await self._wait_for(CTRL_TBOX_RANDOM_NUM, 5.0)
        codec = next((v for f, w, v in parse_fields(payload) if f == 1 and w == 2), b"")
        ciphertext = decode_codec(codec)
        self.log.info("BLE-Auth Schritt 2/4: Challenge (%d Bytes Chiffretext)", len(ciphertext))

        sn = _aes_ecb_pkcs7_decrypt(ciphertext, self.key)
        self.log.info("BLE-Auth Schritt 3/4: RandomNum antworten")
        await self._write_frame(CTRL_RANDOM_NUM, proto_random_num(sn))

        result = await self._wait_for(CTRL_TBOX_AUTH_RESULT, 5.0)
        code = next((v for f, w, v in parse_fields(result) if f == 1 and w == 0), None)
        if code != 0:
            raise BleError(f"Auth vom Bike abgelehnt: result={code}")
        self._auth_done = True
        self.log.info("BLE-Auth Schritt 4/4: OK (result=0)")

    async def _heartbeat_loop(self) -> None:
        assert self.client is not None
        try:
            while self.client.is_connected:
                await self._write_frame(CTRL_LOCK_CONTROL, proto_heartbeat())
                await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.log.debug("Heartbeat beendet: %s", exc)

    # --- public API ----------------------------------------------------------
    async def connect(self) -> None:
        """Connect and authenticate. Raises BleError with a readable message."""
        # HA 2026.10: device lookup lives in bluetooth.api, the old
        # BleakClientWrapper is gone — connections go through bleak's
        # BleakClient via bleak_retry_connector.establish_connection.
        from bleak import BleakClient
        from bleak_retry_connector import establish_connection
        from homeassistant.components.bluetooth.api import (
            async_ble_device_from_address,
            async_get_scanner,
        )

        ble_device = async_ble_device_from_address(
            self.hass, self.mac.upper(), connectable=True
        )
        if ble_device is None:
            # fall back to an address-only device — connection will trigger discovery
            ble_device = async_ble_device_from_address(
                self.hass, self.mac.upper(), connectable=False
            )
        if ble_device is None:
            # HA has never seen the T-Box: run one active scan on the shared
            # scanner and take the device from the scan result directly.
            self.log.info("T-Box unbekannt — aktiver BLE-Scan (10 s) über den HA-Adapter")
            scanner = async_get_scanner(self.hass)
            try:
                found = await asyncio.wait_for(
                    scanner.discover(timeout=10.0, return_adv=True), timeout=20.0
                )
                # bleak 3.x: discover(return_adv=True) -> dict[BLEDevice, AdvertisementData]
                devices = [device for device in found] if isinstance(found, dict) else list(found)
                adv_map = found if isinstance(found, dict) else {}
            except Exception as exc:  # noqa: BLE001
                self.log.debug("aktiver Scan fehlgeschlagen: %s", exc)
                devices = []
                adv_map = {}
            for device in devices:
                adv = adv_map.get(device)
                uuids = ",".join(getattr(adv, "service_uuids", []) or []) if adv else ""
                self.log.info(
                    "Scan-Gerät: %s (%s) uuids=%s rssi=%s",
                    getattr(device, "name", "?"),
                    device.address,
                    uuids or "-",
                    getattr(adv, "rssi", None) if adv else None,
                )
                if device.address.upper() == self.mac.upper():
                    ble_device = device
                    self.log.info("T-Box im aktiven Scan gefunden (%s)", device.address)
                    break
            self.log.info("aktiver Scan beendet: %d Geräte", len(devices))
        if ble_device is None:
            raise BleError(
                f"T-Box {self.mac} wurde nicht gefunden — Bike in BLE-Reichweite "
                "bringen, warten, ggf. einmal die CFMoto-App am Bike öffnen"
            )

        self.log.info("BLE-Verbindung zu %s …", self.mac)
        self.client = await establish_connection(
            BleakClient, ble_device, self.mac.upper()
        )
        await self.client.start_notify(CHAR_NOTIFY, self._on_notify)
        await asyncio.sleep(0.05)  # BleModel.java: 50 ms

        # bleak 3.x negotiates MTU itself; the app requests 185, frames are small.
        await asyncio.sleep(2.0)  # BleModel.java: 2000 ms vor Auth
        await self._authenticate()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def command(
        self,
        control: int,
        payload: bytes,
        ack_control: int | None = CTRL_LOCK_RESULT,
        ack_timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Send one command and wait for its ACK. Returns decoded ACK fields."""
        if not self._auth_done:
            raise BleError("nicht authentifiziert — erst connect()")
        await self._write_frame(control, payload)
        if ack_control is None:
            return {"sent": True}
        ack = await self._wait_for(ack_control, ack_timeout)
        fields = parse_fields(ack)
        result = next((v for f, w, v in fields if f == 1 and w == 0), None)
        err_res = next((v for f, w, v in fields if f == 2 and w == 0), None)
        return {"result": result, "errRes": err_res}

    async def disconnect(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None
        self._auth_done = False


# --- high-level command helpers (used by the button platform) ---
async def run_command(
    hass: Any,
    mac: str,
    encrypt_value: str,
    key: str,
    kind: str,  # unlock | lock | power_on | power_off | horn | flash | test
    logger: logging.Logger = _LOGGER,
) -> dict[str, Any]:
    """One-shot session: connect, auth, command, ACK, disconnect."""
    ble = CfMotoBle(hass, mac, encrypt_value, key, logger)
    try:
        await ble.connect()
        if kind == "test":
            return {"auth": "ok"}
        if kind in ("unlock", "lock", "power_on", "power_off"):
            ack = await ble.command(CTRL_LOCK_CONTROL, proto_lock(kind))
        elif kind == "horn":
            ack = await ble.command(CTRL_FIND_CAR, proto_find_car(False, False, True))
        elif kind == "flash":
            ack = await ble.command(CTRL_FIND_CAR, proto_find_car(False, True, False))
        else:
            raise BleError(f"unbekannter Befehl: {kind}")
        logger.info("BLE-Befehl %s: ACK %s", kind, ack)
        return ack
    finally:
        await ble.disconnect()
