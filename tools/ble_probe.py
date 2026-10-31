#!/usr/bin/env python3
"""BLE probe for the CFMoto 450MT T-Box.

Runs the reconstructed BLE protocol (open-cfmoto) against a REAL bike:

    cloud login  ->  encryptInfo (encryptValue, key) + btMac
    BLE connect  ->  auth 0x5A/0x5B/0x5C/0x5D  ->  heartbeat 0x67 every 2 s
    interactive commands: lock / unlock / power-on / power-off / kl15 <n> / horn / flash / light

Every incoming frame is logged (control code, raw payload, decoded fields) so the
open questions from open-cfmoto's hardware-validation checklist get answered:
  - does auth succeed with cloud encryptInfo (HW-01)?
  - heartbeat ACK code: 0xEC or 0xE7?
  - do lock/power commands get ACKed (0xE7 errRes)?
  - what does KL15 (0x79) accept, and does the cloud `kl` flag change?

Usage:
    CFMOTO_EMAIL=... CFMOTO_PASSWORD=... python3 tools/ble_probe.py
    CFMOTO_EMAIL=... CFMOTO_PASSWORD=... python3 tools/ble_probe.py --scan
    ... --device <ble-uuid-or-mac>      # skip discovery, connect directly

Dependencies: bleak >= 0.22, cryptography.  `pip3 install bleak cryptography`
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from probe import (  # noqa: E402  (cloud client, validated against real VIN)
    get_vehicle_detail,
    get_vehicles,
    login,
)

try:
    import bleak
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("fehlt: pip3 install bleak")

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
except ImportError:
    sys.exit("fehlt: pip3 install cryptography")

log = logging.getLogger("ble-probe")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

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
CTRL_KL15 = 0x79               # app -> bike, ignition control (values unknown)
CTRL_LOCK_RESULT = 0xE7        # bike -> app, lock/unlock/power ACK
CTRL_KEEP_ALIVE_RESULT = 0xEC  # bike -> app, heartbeat ACK (candidate)
CTRL_KL15_RESULT = 0xF9        # bike -> app, KL15 result

CTRL_NAMES = {
    CTRL_AUTH_PACKAGE: "AUTH_PACKAGE(0x5A)",
    CTRL_TBOX_RANDOM_NUM: "TBOX_RANDOM_NUM(0x5B)",
    CTRL_RANDOM_NUM: "RANDOM_NUM(0x5C)",
    CTRL_TBOX_AUTH_RESULT: "TBOX_AUTH_RESULT(0x5D)",
    CTRL_LOCK_CONTROL: "LOCK_CONTROL/HEARTBEAT(0x67)",
    CTRL_FIND_CAR: "FIND_CAR(0x6A)",
    CTRL_KL15: "KL15(0x79)",
    CTRL_LOCK_RESULT: "LOCK_RESULT(0xE7)",
    CTRL_KEEP_ALIVE_RESULT: "KEEP_ALIVE_RESULT(0xEC)",
    CTRL_KL15_RESULT: "KL15_RESULT(0xF9)",
}

LOCK_TYPE = {"unlock": 1, "lock": 1, "power_on": 7, "power_off": 7}  # Lock.Type.MOTORCYCLE=1, POWER_ON_OFF=7
LOCK_STATE = {"unlock": 1, "lock": 2, "power_on": 3, "power_off": 4}


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


def proto_kl15(value: int) -> bytes:
    return _field_varint(1, value & 0xFFFFFFFF)


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
            raise ValueError(f"wire type {wire} nicht unterstützt (offset {i})")
    return fields


def describe_payload(control: int, payload: bytes) -> str:
    try:
        fields = parse_fields(payload)
    except Exception as exc:  # noqa: BLE001
        return f"payload={payload.hex()} (decode: {exc})"
    parts = []
    for fnum, wire, value in fields:
        if wire == 0:
            parts.append(f"f{fnum}={value}")
        else:
            data = value
            try:
                text = data.decode("utf-8") if all(32 <= b < 127 or b in (9, 10) for b in data) else None
            except Exception:  # noqa: BLE001
                text = None
            shown = repr(text[:48]) if text is not None else data.hex()
            parts.append(f"f{fnum}={shown}")
    return "{" + ", ".join(parts) + "}"


# --- frame codec (codec.ts) ---
def build_frame(control: int, payload: bytes) -> bytes:
    n = len(payload)
    frame = bytearray(7 + n)
    frame[0], frame[1], frame[2] = HEADER_0, HEADER_1, control & 0xFF
    frame[3], frame[4] = n & 0xFF, (n >> 8) & 0xFF
    frame[5 : 5 + n] = payload
    frame[5 + n] = sum(frame[2 : 5 + n]) & 0xFF  # byte-addition, NOT xor
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
def aes_ecb_pkcs7_decrypt(ciphertext: bytes, key_utf8: str) -> str:
    key = key_utf8.encode("utf-8")
    if len(key) not in (16, 24, 32):
        raise ValueError(
            f"AES-Key aus encryptInfo.key hat {len(key)} Bytes (UTF-8) — erwartet 16/24/32"
        )
    decryptor = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


def decode_codec(codec: bytes, mode: str) -> bytes:
    """TboxRandomNum.codec -> ciphertext bytes. Auto tries hex, base64, raw."""
    attempts: list[tuple[str, bytes]] = []
    try:
        text = codec.decode("utf-8")
        if mode in ("auto", "hex") and all(c in "0123456789abcdefABCDEF" for c in text):
            return bytes.fromhex(text)
        if mode in ("auto", "b64"):
            import base64

            return base64.b64decode(text)
    except Exception as exc:  # noqa: BLE001
        attempts.append((str(exc), b""))
    if mode in ("auto", "raw"):
        return codec
    raise ValueError(f"codec nicht dekodierbar (mode={mode}): {codec.hex()}")


# --- cloud helpers (probe.py, already validated against the real VIN) ---
def cloud_context(args) -> dict:
    email = args.email or os.environ.get("CFMOTO_EMAIL")
    password = args.password or os.environ.get("CFMOTO_PASSWORD")
    if not email or not password:
        sys.exit("CFMOTO_EMAIL / CFMOTO_PASSWORD fehlen (Env oder --email/--password)")
    area = args.area or os.environ.get("CFMOTO_AREA", "DE")
    token, user_id, _ = login(email, password, area)
    vehicles = get_vehicles(token)
    if not vehicles:
        sys.exit("Konto hat keine Fahrzeuge")
    detail = get_vehicle_detail(token, user_id, str(vehicles[0].get("vehicleId")))
    enc = detail.get("encryptInfo") or {}
    mac = detail.get("btMac")
    return {
        "vin": detail.get("vin"),
        "vehicle_id": detail.get("vehicleId"),
        "bt_mac": mac,
        "encrypt_value": enc.get("encryptValue"),
        "key": enc.get("key"),
        "iv": enc.get("iv"),
        "kl_before": detail.get("kl"),
    }


class BikeSession:
    """One authenticated BLE session against the T-Box."""

    def __init__(self, client: BleakClient, ctx: dict, args) -> None:
        self.client = client
        self.ctx = ctx
        self.args = args
        self.queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()
        self.authenticated = False
        self.last_ack: tuple[int, bytes] | None = None
        self.heartbeat_task: asyncio.Task | None = None
        self.write_with_response = True

    def on_notify(self, _char, data: bytearray) -> None:
        parsed = parse_frame(bytes(data))
        if parsed is None:
            log.info("RAW (kein Frame): %s", bytes(data).hex())
            return
        control, payload = parsed
        name = CTRL_NAMES.get(control, f"0x{control:02X}")
        log.info("<<< %s %s", name, describe_payload(control, payload))
        if control == CTRL_LOCK_RESULT or control == CTRL_KEEP_ALIVE_RESULT:
            self.last_ack = (control, payload)
        self.queue.put_nowait((control, payload))

    async def write_frame(self, control: int, payload: bytes) -> None:
        frame = build_frame(control, payload)
        name = CTRL_NAMES.get(control, f"0x{control:02X}")
        log.info(">>> %s (%d bytes) %s", name, len(frame), describe_payload(control, payload))
        try:
            if self.write_with_response:
                await self.client.write_gatt_char(CHAR_WRITE, frame, response=True)
                return
            await self.client.write_gatt_char(CHAR_WRITE, frame, response=False)
        except Exception as exc:  # noqa: BLE001 — some stacks reject write-with-response
            if self.write_with_response:
                log.info("write mit response fehlgeschlagen (%s) — versuche ohne response", exc)
                self.write_with_response = False
                await self.client.write_gatt_char(CHAR_WRITE, frame, response=False)

    async def wait_for(self, control: int, timeout: float) -> bytes:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError(f"kein Frame {CTRL_NAMES.get(control, hex(control))} in {timeout}s")
            try:
                got, payload = await asyncio.wait_for(self.queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"kein Frame {CTRL_NAMES.get(control, hex(control))} in {timeout}s"
                ) from None
            if got == control:
                return payload

    async def authenticate(self) -> None:
        enc_value = self.ctx["encrypt_value"]
        key = self.ctx["key"]
        if not enc_value or not key:
            raise ValueError("encryptInfo unvollständig — BLE-Auth ohne Cloud-Schlüssel unmöglich")
        log.info("Auth Schritt 1: 0x5A AuthPackage (%d Hex-Chars encryptValue)", len(enc_value))
        await self.write_frame(CTRL_AUTH_PACKAGE, proto_auth_package(bytes.fromhex(enc_value)))

        log.info("Auth Schritt 2: warte auf 0x5B TboxRandomNum …")
        payload = await self.wait_for(CTRL_TBOX_RANDOM_NUM, 5.0)
        codec = next((v for f, w, v in parse_fields(payload) if f == 1 and w == 2), b"")
        log.info(
            "codec: %s (len=%d, AES-Key len=%d, iv-len=%d)",
            codec[:64].hex(), len(codec),
            len(key.encode()), len((self.ctx.get("iv") or "").encode()),
        )

        # Open question from open-cfmoto: codec/key encoding. Try the matrix.
        import base64
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        def hex_bytes(s: str) -> bytes | None:
            try:
                if all(c in "0123456789abcdefABCDEF" for c in s) and len(s) % 2 == 0:
                    return bytes.fromhex(s)
            except Exception:  # noqa: BLE001
                pass
            return None

        key_candidates: dict[str, bytes | None] = {
            "key-utf8": key.encode(),
            "key-hex": hex_bytes(key),
            "iv-utf8": (self.ctx.get("iv") or "").encode() or None,
            "iv-hex": hex_bytes(self.ctx.get("iv") or ""),
        }
        text = codec.decode("utf-8", errors="replace")
        codec_candidates: dict[str, bytes] = {
            "hex": hex_bytes(text),
            "raw": codec,
        }
        try:
            codec_candidates["b64"] = base64.b64decode(text)
        except Exception:  # noqa: BLE001
            pass

        def try_aes(kb: bytes, ct: bytes, op: str, ivb: bytes | None = None) -> bytes | None:
            try:
                mode = modes.CBC(ivb) if ivb is not None else modes.ECB()
                if op == "encrypt":
                    padder = PKCS7(128).padder()
                    data = padder.update(ct) + padder.finalize()
                    enc = Cipher(algorithms.AES(kb), mode).encryptor()
                    return enc.update(data) + enc.finalize()
                decryptor = Cipher(algorithms.AES(kb), mode).decryptor()
                padded = decryptor.update(ct) + decryptor.finalize()
                if op == "nopad":
                    return padded
                unpadder = PKCS7(128).unpadder()
                return unpadder.update(padded) + unpadder.finalize()
            except Exception:  # noqa: BLE001
                return None

        iv_utf8 = (self.ctx.get("iv") or "").encode() or None
        iv_hex = hex_bytes(self.ctx.get("iv") or "")
        import hashlib

        key_list: dict[str, bytes] = {
            "key-utf8": key.encode(),
            "key-md5": hashlib.md5(key.encode()).digest(),
            "key-sha256-16": hashlib.sha256(key.encode()).digest()[:16],
            "key-sha256-32": hashlib.sha256(key.encode()).digest(),
        }
        kh = hex_bytes(key)
        if kh:
            key_list["key-hex"] = kh

        def add(out: bytes | str | None, label: str, seen: list[str]) -> None:
            if out is None:
                return
            if isinstance(out, str):
                variants = [out]
            else:
                variants = []
                if all(32 <= b < 127 for b in out):
                    variants.append(out.decode("ascii"))
                variants.append(out.hex())
            for v in variants:
                if v not in seen:
                    seen.append(v)
                    log.info("Kandidat %02d (%s): %s", len(seen), label, v[:40])

        seen: list[str] = []
        add(codec.decode("ascii", "replace"), "echo-codec", seen)
        for kname, kb in key_list.items():
            if len(kb) not in (16, 24, 32):
                continue
            for cname, ct in (("hex", hex_bytes(text)), ("raw", codec)):
                if ct is None or len(ct) % 16:
                    continue
                add(try_aes(kb, ct, "decrypt"), f"{kname}×{cname} decrypt", seen)
                add(try_aes(kb, ct, "nopad"), f"{kname}×{cname} nopad", seen)
                add(try_aes(kb, ct, "encrypt"), f"{kname}×{cname} encrypt", seen)
                for mname, ivb in (("cbc-iv", iv_utf8), ("cbc-iv-hex", iv_hex)):
                    if ivb is None or len(ivb) != 16:
                        continue
                    add(try_aes(kb, ct, "decrypt", ivb), f"{kname}×{cname} {mname} decrypt", seen)
                    add(try_aes(kb, ct, "encrypt", ivb), f"{kname}×{cname} {mname} encrypt", seen)

        # send candidates one by one; watch for 0x5D result=0
        for idx, sn in enumerate(seen, start=1):
            log.info("sende Kandidat %02d/%02d", idx, len(seen))
            try:
                await self.write_frame(CTRL_RANDOM_NUM, proto_random_num(sn))
                try:
                    result = await asyncio.wait_for(
                        self.wait_for(CTRL_TBOX_AUTH_RESULT, 1.2), timeout=1.2
                    )
                except TimeoutError:
                    log.info("Kandidat %02d: keine Antwort", idx)
                    continue
                fields = parse_fields(result)
                code = next((v for f, w, v in fields if f == 1 and w == 0), None)
                if code == 0:
                    self.authenticated = True
                    log.info("AUTH OK ✅ mit Kandidat %02d: sn=%s", idx, sn[:40])
                    return
                log.info("Kandidat %02d abgelehnt (result=%s)", idx, code)
            except Exception as exc:  # noqa: BLE001 — connection dropped
                log.info("Kandidat %02d: Verbindung unterbrochen (%s)", idx, exc)
                raise RuntimeError(f"Auth abgebrochen bei Kandidat {idx}: {exc}") from exc
        raise RuntimeError("alle sn-Kandidaten abgelehnt / ohne Antwort")

    async def heartbeat_loop(self) -> None:
        log.info("Heartbeat alle 2 s (0x67 ping=1) — ACK-Code wird protokolliert")
        while self.client.is_connected:
            try:
                await self.write_frame(CTRL_LOCK_CONTROL, proto_heartbeat())
                await asyncio.sleep(2.0)
            except Exception as exc:  # noqa: BLE001
                log.info("Heartbeat abgebrochen: %s", exc)
                return

    async def run(self) -> None:
        # macOS CoreBluetooth drops flaky connections; retry the whole
        # connect+auth sequence a few times before giving up.
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                if not self.client.is_connected:
                    log.info("BLE connect (Versuch %d/3) …", attempt)
                    await self.client.connect()
                await self.client.start_notify(CHAR_NOTIFY, self.on_notify)
                await asyncio.sleep(0.05)  # confirmed 50 ms in BleModel.java

                request_mtu = getattr(self.client, "request_mtu", None)
                if callable(request_mtu):
                    try:
                        negotiated = await request_mtu(185)
                        log.info("MTU: %s ausgehandelt", negotiated)
                    except Exception as exc:  # noqa: BLE001
                        log.info("MTU-Negotiation fehlgeschlagen (%s) — weiter wie die App", exc)
                else:
                    log.info("bleak-Version ohne request_mtu — weiter ohne (kleine Frames gehen auch)")

                await asyncio.sleep(2.0)  # confirmed 2000 ms in BleModel.java

                if self.args.no_auth:
                    return
                await self.authenticate()
                self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
                return
            except RuntimeError as exc:
                if attempt == 3 or "abgebrochen" not in str(exc):
                    raise
                last_error = exc
                log.info("Versuch %d/3 fehlgeschlagen (%s) — neu verbinden", attempt, exc)
                try:
                    await self.client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                self._notify_queue = asyncio.Queue()
                await asyncio.sleep(1.0)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                log.info("Versuch %d/3: %s — neu verbinden", attempt, exc)
                if attempt == 3:
                    raise
                try:
                    await self.client.disconnect()
                except Exception:  # noqa: BLE001
                    pass
                await asyncio.sleep(1.0)
        if last_error:
            raise last_error


async def discover(args, ctx) -> BleakClient | None:
    """Find the T-Box: MAC filter on Linux, service-UUID scan elsewhere."""
    wanted_mac = args.device or ctx.get("bt_mac")
    log.info("Suche T-Box … (MAC laut Cloud: %s)", ctx.get("bt_mac"))
    devices = await BleakScanner.discover(timeout=args.scan_timeout, service_uuids=[SERVICE_MAIN])
    if not devices:
        log.info("Kein Gerät mit Service %s gefunden — versuche offenen Scan", SERVICE_MAIN)
        devices = await BleakScanner.discover(timeout=args.scan_timeout)
    if not devices:
        return None
    candidates = []
    for d in devices:
        candidates.append((getattr(d, "rssi", None) or -999, d.address, d.name or "?"))
    for rssi, addr, name in sorted(candidates, reverse=True):
        mark = " ◀ MAC-Match" if wanted_mac and addr.replace(":", "").upper() == wanted_mac.replace(":", "").upper() else ""
        log.info("  RSSI %4d dBm  %s  %s%s", rssi, addr, name, mark)
    if wanted_mac:
        for rssi, addr, _name in sorted(candidates, reverse=True):
            if addr.replace(":", "").upper() == wanted_mac.replace(":", "").upper():
                log.info("Verbinde mit %s (RSSI %d)", addr, rssi)
                return BleakClient(addr, timeout=15.0)
    if not candidates:
        return None
    rssi, addr, name = sorted(candidates, reverse=True)[0]
    log.info("Kein MAC-Match — nehme stärkstes Gerät: %s (%s, RSSI %d)", name, addr, rssi)
    return BleakClient(addr, timeout=15.0)


def _print_help() -> None:
    print(
        "Befehle: unlock | lock | power-on | power-off | kl15 <0|1|2> | "
        "horn | flash | light | status | quit"
    )


async def interactive(session: BikeSession) -> None:
    _print_help()
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, input, "cmd> ")
        parts = line.strip().split()
        if not parts:
            continue
        cmd = parts[0].lower()
        try:
            if cmd == "quit":
                return
            if cmd in ("unlock", "lock", "power-on", "power-off"):
                kind = cmd.replace("-", "_")
                await session.write_frame(CTRL_LOCK_CONTROL, proto_lock(kind))
                session.last_ack = None
                try:
                    ack_code, ack = await asyncio.wait_for(
                        session.wait_for(CTRL_LOCK_RESULT, 5.0), timeout=5.0
                    )
                    log.info("ACK: %s %s", CTRL_NAMES.get(ack_code, hex(ack_code)), describe_payload(ack_code, ack))
                except TimeoutError:
                    log.info("kein ACK in 5 s — unklar, ob der Befehl ankam (offene Frage!)")
            elif cmd == "kl15":
                value = int(parts[1]) if len(parts) > 1 else 1
                await session.write_frame(CTRL_KL15, proto_kl15(value))
                session.last_ack = None
                try:
                    ack_code, ack = await asyncio.wait_for(
                        session.wait_for(CTRL_KL15_RESULT, 5.0), timeout=5.0
                    )
                    log.info("ACK: %s %s", CTRL_NAMES.get(ack_code, hex(ack_code)), describe_payload(ack_code, ack))
                except TimeoutError:
                    log.info("kein KL15-ACK in 5 s")
            elif cmd == "horn":
                await session.write_frame(CTRL_FIND_CAR, proto_find_car(False, False, True))
            elif cmd == "flash":
                await session.write_frame(CTRL_FIND_CAR, proto_find_car(False, True, False))
            elif cmd == "light":
                await session.write_frame(CTRL_FIND_CAR, proto_find_car(True, False, False))
            elif cmd == "status":
                print(f"connected={session.client.is_connected} authenticated={session.authenticated}")
            else:
                _print_help()
        except (ValueError, IndexError):
            _print_help()


async def main() -> None:
    parser = argparse.ArgumentParser(description="CFMoto 450MT BLE probe")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--area")
    parser.add_argument("--device", help="BLE-Adresse/-UUID erzwingen (statt MAC-Match)")
    parser.add_argument("--scan", action="store_true", help="nur scannen und beenden")
    parser.add_argument("--scan-timeout", type=float, default=10.0)
    parser.add_argument("--no-auth", action="store_true", help="Auth überspringen (nur Diagnose)")
    parser.add_argument("--codec-mode", choices=("auto", "hex", "b64", "raw"), default="auto")
    args = parser.parse_args()

    ctx = cloud_context(args)
    log.info(
        "Fahrzeug: VIN %s · btMac %s · kl (Cloud, vorher): %s",
        ctx["vin"], ctx["bt_mac"], ctx["kl_before"],
    )
    if not ctx["encrypt_value"] or not ctx["key"]:
        log.info("⚠️ encryptInfo leer — Auth wird nicht möglich sein")

    if args.scan:
        await discover(args, ctx)
        return

    client = await discover(args, ctx)
    if client is None:
        log.info("Nichts gefunden — Bike in Reichweite? (BLE ~10 m, Sichtlinie)")
        return

    session = BikeSession(client, ctx, args)
    try:
        async with client:
            await session.run()
            log.info("Verbunden. Cloud `kl` vorher: %s — nach dem Test per Cloud-Read prüfen!", ctx["kl_before"])
            await interactive(session)
    except TimeoutError as exc:
        log.error("Timeout: %s", exc)
    except Exception as exc:  # noqa: BLE001
        log.exception("Fehler: %s", exc)
    finally:
        if session.heartbeat_task:
            session.heartbeat_task.cancel()
        log.info("Session beendet.")


if __name__ == "__main__":
    asyncio.run(main())
