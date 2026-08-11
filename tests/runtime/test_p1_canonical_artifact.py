from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from canonical_artifact import CanonicalArtifactError, canonical_bytes, canonical_sha256


class P1CanonicalArtifactTests(unittest.TestCase):
    def test_rfc8785_order_and_format_are_stable(self) -> None:
        self.assertEqual(canonical_bytes({"b": 2, "a": 1}), b'{"a":1,"b":2}')
        self.assertEqual(canonical_sha256({"a": 1, "b": 2}), canonical_sha256({"b": 2, "a": 1}))

    def test_all_strings_are_normalized_to_nfc(self) -> None:
        self.assertEqual(canonical_sha256({"value": "e\u0301"}), canonical_sha256({"value": "é"}))

    def test_nfc_key_collision_is_rejected(self) -> None:
        with self.assertRaises(CanonicalArtifactError):
            canonical_bytes({"e\u0301": 1, "é": 2})

    def test_float_and_unsafe_integer_are_rejected(self) -> None:
        with self.assertRaises(CanonicalArtifactError):
            canonical_bytes({"value": 1.0})
        with self.assertRaises(CanonicalArtifactError):
            canonical_bytes({"value": 9_007_199_254_740_992})


if __name__ == "__main__":
    unittest.main()
