"""Offline tests for the integration's BLE module (custom_components/cfmoto/ble.py).

The auth state machine and command/ACK logic run against a scripted stub
client — no HA runtime, no bike, no radio. Wire-format vectors are pinned
against open-cfmoto's protocol documentation.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Load ble.py directly — importing the package would drag in homeassistant.
_spec = importlib.util.spec_from_file_location(
    "cfmoto_ble", REPO / "custom_components/cfmoto/ble.py"
)
ble = importlib.util.module_from_spec(_spec)
sys.modules["cfmoto_ble"] = ble
_spec.loader.exec_module(ble)

KEY32 = "0123456789abcdef0123456789abcdef"  # 32 bytes -> AES-256


def encrypt_hex(plain: str, key: str = KEY32) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    padder = PKCS7(128).padder()
    padded = padder.update(plain.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key.encode()), modes.ECB()).encryptor()
    return (encryptor.update(padded) + encryptor.finalize()).hex()


class StubClient:
    """Fake BleakClientWrapper: records writes, replays scripted bike frames."""

    def __init__(self, script: list[tuple[int, bytes]]) -> None:
        self.script = list(script)
        self.written: list[bytes] = []
        self.is_connected = True
        self._cb = None

    async def start_notify(self, _char, cb) -> None:
        self._cb = cb

    async def write_gatt_char(self, _char, data, response=True) -> None:
        self.written.append(bytes(data))
        if self.script:
            control, payload = self.script.pop(0)
            frame = ble.build_frame(control, payload)
            self._cb(None, bytearray(frame))

    async def request_mtu(self, size: int) -> int:
        return size

    async def disconnect(self) -> None:
        self.is_connected = False


class WireFormatTests(unittest.TestCase):
    def test_frame_lock_power_on_vector(self):
        frame = ble.build_frame(ble.CTRL_LOCK_CONTROL, ble.proto_lock("power_on"))
        # Lock{type=7,state=3} -> 08 07 10 03 ; CRC(67 04 00 08 07 10 03)=0x8D
        self.assertEqual(frame, bytes.fromhex("ABCD670400080710038DCF"))

    def test_frame_heartbeat_vector(self):
        frame = ble.build_frame(ble.CTRL_LOCK_CONTROL, ble.proto_heartbeat())
        self.assertEqual(frame, bytes.fromhex("ABCD670200080172CF"))

    def test_parse_rejects_corrupt_crc(self):
        frame = bytearray(ble.build_frame(ble.CTRL_LOCK_CONTROL, ble.proto_heartbeat()))
        frame[-2] ^= 0xFF
        self.assertIsNone(ble.parse_frame(bytes(frame)))

    def test_parse_rejects_bad_header(self):
        frame = bytearray(ble.build_frame(ble.CTRL_LOCK_CONTROL, ble.proto_heartbeat()))
        frame[0] = 0x00
        self.assertIsNone(ble.parse_frame(bytes(frame)))

    def test_aes_roundtrip(self):
        ciphertext = bytes.fromhex(encrypt_hex("test1234"))
        self.assertEqual(ble._aes_ecb_pkcs7_decrypt(ciphertext, KEY32), "test1234")

    def test_aes_bad_key_length(self):
        with self.assertRaises(ble.BleError):
            ble._aes_ecb_pkcs7_decrypt(b"\x00" * 16, "short")

    def test_decode_codec_hex(self):
        self.assertEqual(ble.decode_codec(b"deadbeef"), bytes.fromhex("deadbeef"))

    def test_decode_codec_non_hex_raises(self):
        with self.assertRaises(ble.BleError):
            ble.decode_codec(b"\x00\x01\x02\x04")


class AuthFlowTests(unittest.IsolatedAsyncioTestCase):
    def make_ble(self, script) -> ble.CfMotoBle:
        session = ble.CfMotoBle(
            hass=None, mac="03:FF:01:07:80:39",
            encrypt_value="A1B2C3", key=KEY32,
        )
        session.client = StubClient(script)
        return session

    async def start_notify(self, session) -> None:
        await session.client.start_notify(ble.CHAR_NOTIFY, session._on_notify)

    async def test_auth_success(self):
        codec = encrypt_hex("hello")
        session = self.make_ble([
            (ble.CTRL_TBOX_RANDOM_NUM, ble._field_str(1, codec)),
            (ble.CTRL_TBOX_AUTH_RESULT, ble._field_varint(1, 0)),
        ])
        await self.start_notify(session)
        await session._authenticate()
        self.assertTrue(session._auth_done)
        sent_controls = [ble.parse_frame(f)[0] for f in session.client.written]
        self.assertEqual(sent_controls, [ble.CTRL_AUTH_PACKAGE, ble.CTRL_RANDOM_NUM])

    async def test_auth_rejected(self):
        session = self.make_ble([
            (ble.CTRL_TBOX_RANDOM_NUM, ble._field_str(1, encrypt_hex("hello"))),
            (ble.CTRL_TBOX_AUTH_RESULT, ble._field_varint(1, 2)),
        ])
        await self.start_notify(session)
        with self.assertRaises(ble.BleError):
            await session._authenticate()

    async def test_auth_timeout_on_random(self):
        session = self.make_ble([])
        await self.start_notify(session)
        with self.assertRaises(ble.BleError):
            await session._authenticate()

    async def test_command_ack(self):
        session = self.make_ble([
            (ble.CTRL_TBOX_RANDOM_NUM, ble._field_str(1, encrypt_hex("hello"))),
            (ble.CTRL_TBOX_AUTH_RESULT, ble._field_varint(1, 0)),
            (ble.CTRL_LOCK_RESULT, ble._field_varint(1, 0) + ble._field_varint(2, 32)),
        ])
        await self.start_notify(session)
        await session._authenticate()
        ack = await session.command(
            ble.CTRL_LOCK_CONTROL, ble.proto_lock("power_on"), ack_timeout=2.0
        )
        self.assertEqual(ack, {"result": 0, "errRes": 32})

    async def test_command_without_auth_raises(self):
        session = self.make_ble([])
        with self.assertRaises(ble.BleError):
            await session.command(ble.CTRL_LOCK_CONTROL, ble.proto_lock("lock"))

    async def test_run_command_test_kind(self):
        # run_command drives connect() which needs HA — bypass by pre-setting
        # the client on a session we control via subclass-free monkeypatch:
        created: dict = {}

        class ProbeBle(ble.CfMotoBle):
            async def connect(self):
                self.client = StubClient([])
                self._auth_done = True

        orig = ble.CfMotoBle
        ble.CfMotoBle = ProbeBle
        try:
            result = await ble.run_command(None, "AA:BB:CC:DD:EE:FF", "E1", KEY32, "test")
        finally:
            ble.CfMotoBle = orig
        self.assertEqual(result, {"auth": "ok"})


if __name__ == "__main__":
    unittest.main()
