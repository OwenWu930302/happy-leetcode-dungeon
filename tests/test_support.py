"""錯誤報告的遮蔽、提示階梯、新版判斷、羈絆。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game import bond, hints, report, rogue, update  # noqa: E402


class ReportTests(unittest.TestCase):
    def test_mask_hides_secrets_names_and_paths(self):
        text = ("session=abcdefghijklmnopqrstuvwxyz0123 csrftoken: ZZZZZZZZZZZZZZZZZZZZ user OwenWu930302 "
                "file C:\\Users\\Owen\\Documents\\LeetCodeDungeon\\data\\x.json "
                "jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk")
        out = report.mask(text, secrets=("ZZZZZZZZZZZZZZZZZZZZ",), names=("owenwu930302",),
                          paths=(("C:\\Users\\Owen\\Documents\\LeetCodeDungeon", "<工作區>"), ("C:\\Users\\Owen", "~")))
        for leaked in ("abcdefghijklmnopqrstuvwxyz0123", "ZZZZ", "OwenWu930302", "C:\\Users\\Owen", "eyJhbGci"):
            self.assertNotIn(leaked, out)
        self.assertIn("<工作區>\\data\\x.json", out)

    def test_build_includes_log_tail(self):
        d = Path(tempfile.mkdtemp())
        try:
            report.setup(d)
            report.LOG.error("boom at %s", str(d))
            text = report.build("v1", "Traceback ...", paths=((str(d), "<工作區>"),))
            self.assertIn("boom at <工作區>", text)
            self.assertNotIn(str(d), text)
        finally:
            for h in list(report.LOG.handlers):
                report.LOG.removeHandler(h)
                h.close()
            shutil.rmtree(d, ignore_errors=True)


class UpdateTests(unittest.TestCase):
    def test_newer_needs_half_hour_gap(self):
        info = {"built": "2026-10-17T03:00:00Z"}
        self.assertFalse(update.newer({"published_at": "2026-10-17T03:10:00Z"}, info))  # 就是這次建置發佈的
        self.assertTrue(update.newer({"published_at": "2026-10-18T03:00:00Z"}, info))
        self.assertFalse(update.newer({"published_at": None}, info))

    def test_check_records_available_release(self):
        class R:
            ok, status_code = True, 200

            def json(self):
                return {"published_at": "2026-12-01T00:00:00Z", "tag_name": "v1.0.1", "html_url": "https://x"}
        update.STATE.update(available=None)
        update.check(lambda url, timeout: R(), {"built": "2026-10-17T03:00:00Z"})
        self.assertEqual(update.STATE["available"]["url"], "https://x")
        update.STATE.update(available=None)


class HintTests(unittest.TestCase):
    def test_ladder_levels_and_primary_tag(self):
        hints.set_problems([{"tags": ["array", "hash-table"]}] * 5 + [{"tags": ["array"]}] * 20)
        p = {"tags": ["array", "hash-table"]}
        names = {"array": "陣列", "hash-table": "雜湊表"}
        self.assertEqual(hints.primary_tag(p["tags"]), "hash-table")  # 比較少見的那個
        lad = hints.ladder(p, names, 3)
        self.assertEqual([h["level"] for h in lad], [1, 2, 3])
        self.assertIn("雜湊表", lad[2]["title"])
        self.assertEqual(len(hints.ladder({"tags": []}, {}, 3)), 3)


class BondTests(unittest.TestCase):
    def test_scan_levels_and_story(self):
        save = rogue.new_save()
        static = ROOT / "game" / "static"
        self.assertEqual(bond.scan(save, {}, "p7", [], static), [])  # 第一次只記下起點
        save["meta"]["bond_since"] = "2000-01-01 00:00:00"
        recs = {f"s{i}": {"attempts": [{"time": f"2026-01-01 00:00:{i:02d}", "accepted": True}]} for i in range(20)}
        ev = bond.scan(save, recs, "p7", [{"kind": "won"}], static)
        self.assertEqual(save["meta"]["bond"]["p7"], 3 * 10 + 12)  # 一次最多算 10 筆通過
        self.assertEqual(ev[-1]["level"], 4)
        save["meta"]["bond"]["p7"] = 48
        ev = bond.scan(save, {}, "p7", [{"kind": "win"}], static)
        self.assertEqual(ev[0]["story"]["level"], 5)
        with self.assertRaises(ValueError):
            bond.read_story(save, "p7", 10, static)
        self.assertIn("{name}", bond.read_story(save, "p7", 5, static)["text"])

    def test_every_companion_has_three_stories(self):
        data = json.loads((ROOT / "game" / "static" / "stories.json").read_text(encoding="utf-8"))
        comps = json.loads((ROOT / "game" / "static" / "companions.json").read_text(encoding="utf-8"))["companions"]
        for c in comps:
            self.assertEqual([s["level"] for s in data["stories"][c["id"]]], [5, 10, 15], c["id"])


if __name__ == "__main__":
    unittest.main()
