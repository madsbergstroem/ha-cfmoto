"""Offline unit tests for the BLE probe's frame/proto/AES code.

Pins the wire format from open-cfmoto (docs/protocol.md §frame, meter.proto,
auth-protocol.md) with hand-computed vectors — no bike or BLE radio needed.
Run:  .venv/bin/python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent))

from ble_probe import (  # noqa: E402
    CTRL_LOCK_CONTROL,
    aes_ecb_pkcs7_decrypt,
    build_frame,
    decode_codec,
    parse_fields,
    parse_frame,
    proto_auth_package,
    proto_find_car,
    proto_heartbeat,
    proto_kl15,
    proto_lock,
    proto_random_num,
)


class FrameTests(unittest.TestCase):
    def test_build_frame_lock_power_on_vector(self):
        # Lock{type=7, state=3} -> 08 07 10 03
        # CRC = sum(67 04 00 08 07 10 03) = 103+4+8+7+16+3 = 141 = 0x8D (byte addition)
        frame = build_frame(CTRL_LOCK_CONTROL, proto_lock("power_on"))
        self.assertEqual(frame, bytes.fromhex("ABCD670400080710038DCF"))

    def test_build_frame_heartbeat_vector(self):
        # Heartbeat{ping=1} -> 08 01 ; CRC = 0x67+0x02+0x00+0x08+0x01 = 0x72
        frame = build_frame(CTRL_LOCK_CONTROL, proto_heartbeat())
        self.assertEqual(frame, bytes.fromhex("ABCD670200080172CF"))

    def test_parse_frame_roundtrip(self):
        frame = build_frame(0x5A, proto_auth_package(bytes.fromhex("A1B2C3")))
        parsed = parse_frame(frame)
        self.assertIsNotNone(parsed)
        control, payload = parsed
        self.assertEqual(control, 0x5A)
        self.assertEqual(payload, bytes.fromhex("0A03A1B2C3"))

    def test_parse_frame_rejects_corrupt_crc(self):
        frame = bytearray(build_frame(CTRL_LOCK_CONTROL, proto_heartbeat()))
        frame[-2] ^= 0xFF  # flip CRC byte
        self.assertIsNone(parse_frame(bytes(frame)))

    def test_parse_frame_rejects_bad_header(self):
        frame = bytearray(build_frame(CTRL_LOCK_CONTROL, proto_heartbeat()))
        frame[0] = 0x00
        self.assertIsNone(parse_frame(bytes(frame)))

    def test_parse_frame_rejects_short(self):
        self.assertIsNone(parse_frame(b"ABCD"))


class ProtoTests(unittest.TestCase):
    def test_lock_payloads(self):
        # Lock.Type.MOTORCYCLE=1 for lock/unlock, POWER_ON_OFF=7 for power
        self.assertEqual(proto_lock("unlock"), bytes.fromhex("08011001"))
        self.assertEqual(proto_lock("lock"), bytes.fromhex("08011002"))
        self.assertEqual(proto_lock("power_on"), bytes.fromhex("08071003"))
        self.assertEqual(proto_lock("power_off"), bytes.fromhex("08071004"))

    def test_kl15_payload(self):
        self.assertEqual(proto_kl15(1), bytes.fromhex("0801"))
        self.assertEqual(proto_kl15(2), bytes.fromhex("0802"))

    def test_random_num_payload(self):
        self.assertEqual(proto_random_num("hi"), bytes.fromhex("0A026869"))

    def test_find_car_horn(self):
        # loudspeakerStatus=true (field 3) -> 18 01
        self.assertEqual(proto_find_car(False, False, True), bytes.fromhex("1801"))

    def test_parse_fields_generic(self):
        fields = parse_fields(bytes.fromhex("08071003"))
        self.assertEqual(fields, [(1, 0, 7), (2, 0, 3)])


class AesTests(unittest.TestCase):
    def test_decrypt_roundtrip_256(self):
        # Cross-check: encrypt here, decrypt through the probe's function.
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        key = "0123456789abcdef0123456789abcdef"  # 32 bytes -> AES-256
        padder = PKCS7(128).padder()
        padded = padder.update(b"test1234") + padder.finalize()
        encryptor = Cipher(algorithms.AES(key.encode()), modes.ECB()).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        self.assertEqual(aes_ecb_pkcs7_decrypt(ciphertext, key), "test1234")

    def test_key_size_128(self):
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        key = "0123456789abcdef"  # 16 bytes -> AES-128
        padder = PKCS7(128).padder()
        padded = padder.update(b"abc") + padder.finalize()
        encryptor = Cipher(algorithms.AES(key.encode()), modes.ECB()).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        self.assertEqual(aes_ecb_pkcs7_decrypt(ciphertext, key), "abc")

    def test_bad_key_length_raises(self):
        with self.assertRaises(ValueError):
            aes_ecb_pkcs7_decrypt(b"\x00" * 16, "tooshort")


class CodecModeTests(unittest.TestCase):
    def test_hex_mode(self):
        self.assertEqual(decode_codec(b"a1b2c3", "hex"), bytes.fromhex("a1b2c3"))

    def test_raw_mode(self):
        raw = b"\x00\x01\x02"
        self.assertEqual(decode_codec(raw, "raw"), raw)

    def test_auto_prefers_hex(self):
        self.assertEqual(decode_codec(b"deadbeef", "auto"), bytes.fromhex("deadbeef"))

    def test_auto_falls_back_to_raw_for_binary(self):
        raw = b"\x00\xff\x10"
        self.assertEqual(decode_codec(raw, "auto"), raw)


if __name__ == "__main__":
    unittest.main()
