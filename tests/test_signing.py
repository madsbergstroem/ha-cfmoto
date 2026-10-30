"""Signing vectors pinned against the reference JS client (open-cfmoto).

The expected values were produced by running the exact TS logic with Node
(`JSON.stringify` for POST bodies, `encodeURIComponent` + `+` for query
values, `crypto.createHash('sha1'|'md5')`), so they are independent of this
Python implementation.

Run: python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import probe  # noqa: E402

NONCE = "a1B2c3D4e5F6g7H8"
TIMESTAMP = "1710000000000"

LOGIN_BODY = {
    "idcard": "demo@example.com",
    "idcardType": "email",
    "password": "5f4dcc3b5aa765d61d8327deb882cf99",
    "thirdpartyId": "",
    "thirdpartyType": "",
    "areaCode": "",
    "areaNo": "DE",
    "emailMarketingAlarm": False,
    "verifyCode": "",
}


class SigningTest(unittest.TestCase):
    def test_post_body_payload_matches_json_stringify(self) -> None:
        self.assertEqual(
            json.dumps(LOGIN_BODY, separators=(",", ":")),
            '{"idcard":"demo@example.com","idcardType":"email",'
            '"password":"5f4dcc3b5aa765d61d8327deb882cf99","thirdpartyId":"",'
            '"thirdpartyType":"","areaCode":"","areaNo":"DE",'
            '"emailMarketingAlarm":false,"verifyCode":""}',
        )

    def test_post_signature_vector(self) -> None:
        payload = json.dumps(LOGIN_BODY, separators=(",", ":"))
        self.assertEqual(
            probe.compute_signature(payload, NONCE, TIMESTAMP),
            "cded79d6dc4c0fe952397f75ba3cd50e",
        )

    def test_get_query_sorts_and_encodes_spaces_as_plus(self) -> None:
        query = {"vehicleId": "abc 123", "z": "zzz", "a": "111"}
        self.assertEqual(probe.serialize_query(query), "a=111&vehicleId=abc+123&z=zzz")
        self.assertEqual(
            probe.compute_signature(
                probe.serialize_query(query), NONCE, TIMESTAMP
            ),
            "a9300847f04ee71e115aafba45abf263",
        )

    def test_vehicle_list_query_vector(self) -> None:
        query = {"vehicleId": "-1", "position": "2"}
        self.assertEqual(probe.serialize_query(query), "position=2&vehicleId=-1")
        self.assertEqual(
            probe.compute_signature(
                probe.serialize_query(query), NONCE, TIMESTAMP
            ),
            "e5e3219ed435ade6bec7059d0d341de5",
        )

    def test_nonce_shape_matches_apk_alphabet(self) -> None:
        allowed = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYabcdefghijklmnopqrstuvwxy")
        for _ in range(50):
            nonce = probe.make_nonce()
            self.assertEqual(len(nonce), 16)
            self.assertTrue(set(nonce) <= allowed, nonce)

    def test_password_already_hashed_is_not_hashed_twice(self) -> None:
        hashed = "5f4dcc3b5aa765d61d8327deb882cf99"
        self.assertEqual(probe.normalize_password(hashed), hashed)
        self.assertEqual(
            probe.normalize_password("  " + hashed.upper() + "  "), hashed
        )

    def test_password_plaintext_is_md5(self) -> None:
        self.assertEqual(
            probe.normalize_password("password"),
            "5f4dcc3b5aa765d61d8327deb882cf99",
        )


if __name__ == "__main__":
    unittest.main()
