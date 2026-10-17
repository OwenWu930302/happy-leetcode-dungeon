"""資料包：範例要能載入；格式錯誤要指出是哪一行、整包不載入。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game import mods, rogue  # noqa: E402


class ModTests(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        (self.ws / "mods").mkdir()

    def tearDown(self):
        shutil.rmtree(self.ws, ignore_errors=True)
        rogue.MOD_RELICS.clear()
        rogue.MOD_EVENTS.clear()
        rogue.MOD_SYNERGIES.clear()

    def test_example_pack_loads(self):
        shutil.copytree(ROOT / "docs" / "example-mod", self.ws / "mods" / "example-mod")
        out = mods.load_all(self.ws)
        self.assertTrue(out["mods"][0]["ok"], out["mods"])
        self.assertEqual(out["mods"][0]["counts"], {"companions": 1, "relics": 2, "events": 1, "synergies": 1})
        self.assertIn("mod-example-pack-anvil", rogue.MOD_RELICS)
        self.assertIn("mod-example-pack-forge", rogue.MOD_SYNERGIES)
        self.assertEqual(out["companions"][0]["id"], "mod-example-pack-pola")
        # 資料包遺物會出現在寶箱選項裡，效果也會生效
        save = rogue.new_save()
        run = rogue.start_run(save, seed=1)
        rogue._add_relic(run, "mod-example-pack-anvil")
        rogue._add_relic(run, "mod-example-pack-bellows")
        self.assertIn("mod-example-pack-forge", rogue.active_synergies(run))
        self.assertAlmostEqual(rogue._eff_mult(run, "xp_mult"), 1.15)
        self.assertEqual(run["max_hp"], 65)

    def test_json_syntax_error_has_line(self):
        (self.ws / "mods" / "bad.json").write_text('{\n  "id": "x",\n  "name": "壞掉"\n  "relics": []\n}', encoding="utf-8")
        out = mods.load_all(self.ws)
        self.assertFalse(out["mods"][0]["ok"])
        self.assertIn("第 4 行", out["mods"][0]["errors"][0])

    def test_field_errors_point_to_item(self):
        data = {"id": "p", "name": "包", "relics": [
            {"id": "ok", "name": "好", "glyph": "好", "desc": "x", "effect": {"xp_mult": 1.1}},
            {"id": "too-strong", "name": "壞", "glyph": "壞", "desc": "x", "effect": {"xp_mult": 50, "fly": 1}}]}
        (self.ws / "mods" / "p.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        out = mods.load_all(self.ws)
        errs = "\n".join(out["mods"][0]["errors"])
        self.assertIn("xp_mult", errs)
        self.assertIn("fly", errs)
        self.assertRegex(errs, r"第 \d+ 行附近")
        self.assertEqual(rogue.MOD_RELICS, {}, "有錯的資料包整包都不能載入")

    def test_image_must_stay_inside_folder(self):
        d = self.ws / "mods" / "evil"
        d.mkdir()
        (self.ws / "secret.png").write_bytes(b"\x89PNG")
        data = {"id": "evil", "name": "x", "companions": [
            {"id": "a", "name": "a", "title": "a", "intro": "a", "image": "../../secret.png"}]}
        (d / "mod.json").write_text(json.dumps(data), encoding="utf-8")
        out = mods.load_all(self.ws)
        self.assertFalse(out["mods"][0]["ok"])
        self.assertIsNone(mods.asset_path(out, "evil", "../../secret.png"))

    def test_duplicate_ids(self):
        for n in ("a", "b"):
            (self.ws / "mods" / f"{n}.json").write_text(json.dumps({"id": "same", "name": n, "events": [
                {"title": "t", "text": "x", "effects": {"gold": 5}}]}), encoding="utf-8")
        out = mods.load_all(self.ws)
        self.assertEqual([m["ok"] for m in out["mods"]], [True, False])


if __name__ == "__main__":
    unittest.main()
