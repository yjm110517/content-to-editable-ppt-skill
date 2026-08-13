from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "content-to-editable-ppt" / "scripts"))

from build_tabler_icon_index import build_index
from search_tabler_icons import rank


VENDOR = ROOT / "content-to-editable-ppt" / "runtime" / "vendor" / "tabler-icons" / "3.46.0"
LOCK = ROOT / "content-to-editable-ppt" / "runtime" / "vendor-lock.json"


class TablerVendorSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not VENDOR.is_dir():
            raise unittest.SkipTest("managed Tabler vendor copy has not been synchronized")
        cls.index = build_index(VENDOR)

    def test_pinned_index_is_complete_and_paths_exist(self) -> None:
        self.assertEqual(self.index["library_version"], "3.46.0")
        self.assertEqual(self.index["source_commit"], "8ac7d81b72ece11072ef25ea9fd92e80c6f3c9fc")
        self.assertEqual(self.index["icon_count"], 5130)
        for entry in self.index["entries"]:
            self.assertTrue((VENDOR / entry["relative_path"]).is_file())

    def test_committed_lock_and_attribution_match_managed_vendor(self) -> None:
        import hashlib
        lock = json.loads(LOCK.read_text(encoding="utf-8"))["vendors"]["tabler-icons"]
        self.assertEqual(lock["commit"], self.index["source_commit"])
        self.assertEqual(lock["outline_icon_count"], self.index["icon_count"])
        pairs = [[item["relative_path"].split("/")[-1], item["source_sha256"]] for item in self.index["entries"]]
        tree = hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(tree, lock["outline_tree_sha256"])
        self.assertEqual(hashlib.sha256((VENDOR / "LICENSE").read_bytes()).hexdigest(), lock["license_sha256"])
        self.assertTrue((ROOT / "content-to-editable-ppt" / "third_party" / "tabler-icons" / "LICENSE").is_file())

    def test_exact_canonical_and_official_alias_auto_select(self) -> None:
        canonical = rank(self.index, "code", 5)
        self.assertEqual(canonical["status"], "auto_selected")
        self.assertEqual(canonical["automatic_icon_name"], "code")
        alias = rank(self.index, "2fa", 5)
        self.assertEqual(alias["status"], "auto_selected")
        self.assertEqual(alias["automatic_icon_name"], "auth-2fa")

    def test_non_exact_search_requires_host_and_is_deterministic(self) -> None:
        first = rank(self.index, "artificial intelligence code", 8)
        second = rank(self.index, "artificial intelligence code", 8)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "host_selection_required")
        self.assertEqual(len(first["top_k"]), 8)


if __name__ == "__main__":
    unittest.main()
