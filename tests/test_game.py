"""演算法核心、遠征、備份、錯題本、週報的測試（不需要網路）。"""
import json
import os
import random
import shutil
import sys
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game import backup, engine, mistakes, rogue, weekly  # noqa: E402

PROBLEMS = json.loads((ROOT / "data" / "problems.json").read_text(encoding="utf-8"))


def fake_records(n, seed=1, days=14):
    rng = random.Random(seed)
    pool = [p for p in PROBLEMS if engine.playable(p)]
    now = datetime.now()
    recs = {}
    for i, p in enumerate(rng.sample(pool, n)):
        t = (now - timedelta(days=rng.randint(0, days - 1))).strftime("%Y-%m-%d %H:%M:%S")
        recs[p["slug"]] = {"id": p["id"], "title": p["title"], "difficulty": p["difficulty"], "solved": True,
                           "attempts": [{"time": t, "status": "Accepted", "accepted": True, "submission_id": i}]}
    return recs


class TreeTests(unittest.TestCase):
    def test_tree_is_layered_dag(self):
        tree = engine.build_tree(PROBLEMS, {})
        layer = {n["id"]: n["layer"] for n in tree["nodes"]}
        self.assertTrue(tree["nodes"])
        for n in tree["nodes"]:
            for p in n["parents"]:
                self.assertLess(layer[p], n["layer"], f"{p} → {n['id']} 應該往下一層")

    def test_kahn_detects_order(self):
        order = engine.kahn_topo(["a", "b", "c"], {"a": [], "b": ["a"], "c": ["b"]})
        self.assertEqual(list(order[0] if isinstance(order, tuple) else order)[:3], ["a", "b", "c"])

    def test_lit_needs_solving(self):
        self.assertFalse(any(n["lit"] for n in engine.build_tree(PROBLEMS, {})["nodes"]))
        self.assertTrue(any(n["lit"] for n in engine.build_tree(PROBLEMS, fake_records(40))["nodes"]))


class PowerTests(unittest.TestCase):
    def test_power_never_drops_when_solving_more(self):
        recs = fake_records(30, seed=3)
        prev = -1
        items = list(recs.items())
        for k in range(1, len(items) + 1):
            p = engine.compute_power(PROBLEMS, dict(items[:k]))["power"]
            self.assertGreaterEqual(p, prev)
            prev = p

    def test_rank_info_is_consistent(self):
        for r in (800, 1200, 1500, 1999, 2400, 3200):
            ri = engine.rank_info(r)
            self.assertIn("rank", ri)


class RogueTests(unittest.TestCase):
    def test_same_seed_same_map(self):
        a = rogue.gen_map(random.Random(42))
        b = rogue.gen_map(random.Random(42))
        self.assertEqual(a, b)

    def test_paths_do_not_cross(self):
        for seed in range(30):
            m = rogue.gen_map(random.Random(seed))
            pos = {k: (n["r"], n["c"]) for k, n in m["nodes"].items()}
            segs = [(pos[a], pos[b]) for a, b in m["edges"] if b != "boss"]
            for (r1, c1), (_, d1) in segs:
                for (r2, c2), (_, d2) in segs:
                    if r1 == r2:
                        self.assertFalse((c1 < c2 and d1 > d2) or (c1 > c2 and d1 < d2), f"seed {seed} 路線交叉")

    def test_daily_seed_and_code(self):
        self.assertEqual(rogue.daily_seed("2026-10-16"), rogue.daily_seed("2026-10-16"))
        self.assertNotEqual(rogue.daily_seed("2026-10-16"), rogue.daily_seed("2026-10-17"))
        s1, s2 = rogue.new_save(), rogue.new_save()
        r1 = rogue.start_run(s1, persona="p5", daily="2026-10-16")
        r2 = rogue.start_run(s2, persona="p0", daily="2026-10-16")
        self.assertEqual(r1["map"], r2["map"], "每日挑戰不能受看板娘影響")
        rogue.abandon(s1)
        code = s1["meta"]["daily"]["2026-10-16"]["code"]
        self.assertRegex(code, r"^LCD-20261016-L\d{2}-\d+HP-\d+M-[0-9A-F]{4}$")


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "data").mkdir()
        (self.root / "solutions").mkdir()
        (self.root / "data" / "records.json").write_text('{"a": 1}', encoding="utf-8")
        (self.root / "solutions" / "0001-x.py").write_text("print(1)", encoding="utf-8")
        (self.root / "config.json").write_text('{"session": "secret"}', encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_snapshot_skips_login_and_restores(self):
        z = backup.snapshot(self.root)
        names = zipfile.ZipFile(z).namelist()
        self.assertIn("data/records.json", names)
        self.assertIn("solutions/0001-x.py", names)
        self.assertNotIn("config.json", names)
        (self.root / "data" / "records.json").write_text('{"a": 2}', encoding="utf-8")
        out = backup.restore(self.root, z.name)
        self.assertEqual(json.loads((self.root / "data" / "records.json").read_text(encoding="utf-8")), {"a": 1})
        self.assertTrue(out["safety"])  # 還原前有先備份現況

    def test_daily_once_and_prune(self):
        self.assertIsNotNone(backup.daily(self.root))
        self.assertIsNone(backup.daily(self.root))
        for _ in range(20):
            backup.snapshot(self.root, "manual")
        self.assertLessEqual(len(list(backup.backup_dir(self.root).glob("*.zip"))), backup.KEEP)

    def test_rejects_bad_names_and_paths(self):
        with self.assertRaises(ValueError):
            backup.restore(self.root, "../../etc/passwd")
        self.assertFalse(backup._safe("../x"))
        self.assertFalse(backup._safe("data/../../x.json"))
        self.assertFalse(backup._safe("config.json"))


class MistakeAndWeeklyTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_add_tag_resolve(self):
        p = {"slug": "x", "id": "1", "title": "X", "difficulty": "Easy"}
        e = mistakes.add(self.d, p, "python3", {"status_msg": "Wrong Answer", "total_correct": 1, "total_testcases": 3}, "code")
        mistakes.tag(self.d, e["id"], "邊界條件")
        self.assertEqual(mistakes.open_by_slug(mistakes.load(self.d)), {"x": 1})
        self.assertEqual(mistakes.resolve(self.d, "x"), 1)
        self.assertEqual(mistakes.open_by_slug(mistakes.load(self.d)), {})
        with self.assertRaises(ValueError):
            mistakes.tag(self.d, e["id"], "亂打的錯因")

    def test_weekly_counts_only_this_week(self):
        recs = fake_records(25, seed=5, days=14)
        rep = weekly.report(PROBLEMS, recs, [], weekly.week_start())
        start = weekly.week_start().strftime("%Y-%m-%d")
        expect = sum(1 for r in recs.values() if r["attempts"][0]["time"][:10] >= start)
        self.assertEqual(rep["solvedCount"], expect)
        self.assertGreaterEqual(rep["ratingTo"], 0)

    def test_as_of_keeps_undated_solves(self):
        recs = {"old": {"solved": True, "attempts": []}}
        self.assertTrue(weekly.as_of(recs, "2000-01-01 00:00:00")["old"]["solved"])


if __name__ == "__main__":
    unittest.main()


def make_ctx(lang="python3"):
    recs = fake_records(20, seed=9)
    tree = engine.build_tree(PROBLEMS, recs)
    return {"problems": PROBLEMS, "records": recs, "tree": tree, "power": engine.compute_power(PROBLEMS, recs),
            "mode": "balanced", "lang": lang}


def fight_ready(save, ctx, kind="fight"):
    """把目前的遠征直接放進一場指定種類的戰鬥（測試用）。"""
    run = save["run"]
    offers, tag = rogue._offers(run, ctx, kind)
    run["pos"] = "test"
    run["current"] = {"key": "test", "type": kind, "offers": offers, "chosen": None, "started_at": None,
                      "seen": [], "wrong": 0, "rerolled": False, "boss_tag": tag}
    return run["current"]


class RunDepthTests(unittest.TestCase):
    def setUp(self):
        self.ctx = make_ctx()
        self.save = rogue.new_save()

    def tearDown(self):
        rogue.MOD_RELICS.clear()
        rogue.MOD_SYNERGIES.clear()

    def attempt(self, slug, ok, lang="python3", sid=1, at=None):
        return {slug: {"attempts": [{"time": at or rogue.NOW(), "accepted": ok, "status": "Accepted" if ok else "Wrong Answer",
                                     "submission_id": sid, "lang": lang}], "solved": ok}}

    def test_skill_once_and_rules(self):
        run = rogue.start_run(self.save, seed=3, persona="p2")
        run["hp"] = 20
        rogue.use_skill(self.save, self.ctx)
        self.assertEqual(run["hp"], 35)  # 25% of 60
        with self.assertRaises(ValueError):
            rogue.use_skill(self.save, self.ctx)

    def test_moon_step_only_in_normal_fight(self):
        rogue.start_run(self.save, seed=4, persona="p5")
        with self.assertRaises(ValueError):
            rogue.use_skill(self.save, self.ctx)  # 不在戰鬥中
        fight_ready(self.save, self.ctx, "elite")
        with self.assertRaises(ValueError):
            rogue.use_skill(self.save, self.ctx)
        fight_ready(self.save, self.ctx, "fight")
        rogue.use_skill(self.save, self.ctx)
        self.assertIsNone(self.save["run"]["current"])

    def test_cheer_blocks_next_hit(self):
        rogue.start_run(self.save, seed=5, persona="p1")
        cur = fight_ready(self.save, self.ctx)
        slug = cur["offers"][0]["slug"]
        rogue.choose(self.save, slug)
        rogue.use_skill(self.save, self.ctx)
        hp = self.save["run"]["hp"]
        ev = rogue.resolve(self.save, self.attempt(slug, False), {})
        self.assertEqual(ev[0]["dmg"], 0)
        self.assertEqual(self.save["run"]["hp"], hp)

    def test_boss_language_seal(self):
        rogue.start_run(self.save, seed=6)
        run = self.save["run"]
        cur = fight_ready(self.save, self.ctx, "boss")
        cur.update(rule="lang", rule_lang="cpp")
        slug = cur["offers"][0]["slug"]
        rogue.choose(self.save, slug)
        ev = rogue.resolve(self.save, self.attempt(slug, True, lang="python3"), {})
        self.assertEqual(ev[0]["kind"], "hit")
        self.assertIn("語言封印", ev[0]["status"])
        self.assertEqual(run["status"], "active")
        ev = rogue.resolve(self.save, {slug: {"attempts": [
            {"time": rogue.NOW(), "accepted": True, "submission_id": 2, "lang": "cpp"}], "solved": True}}, {})
        self.assertEqual(ev[-1]["kind"], "won")

    def test_boss_rule_is_chosen_on_enter(self):
        rogue.start_run(self.save, seed=7)
        run = self.save["run"]
        boss_key = "boss"
        run["map"]["edges"].append(["here", boss_key])
        run["pos"] = "here"
        rogue.enter(self.save, boss_key, self.ctx)
        self.assertIn(run["current"]["rule"], rogue.BOSS_RULES)

    def test_ascension_unlock_and_penalties(self):
        with self.assertRaises(ValueError):
            rogue.start_run(self.save, asc=1)
        self.save["meta"]["asc_max"] = 2
        run = rogue.start_run(self.save, seed=8, asc=2)
        self.assertEqual(run["max_hp"], 50)
        rogue._finish(self.save, won=True)
        self.assertEqual(self.save["meta"]["asc_max"], 3)
        daily = rogue.start_run(self.save, daily="2026-10-17", asc=2)
        self.assertEqual(daily["asc"], 0, "每日挑戰固定一般難度")

    def test_synergy_and_shop_price(self):
        run = rogue.start_run(self.save, seed=9)
        rogue._add_relic(run, "rubber_duck")
        self.assertEqual(rogue.active_synergies(run), [])
        rogue._add_relic(run, "debugger")
        self.assertIn("debug_duo", rogue.active_synergies(run))
        cur = fight_ready(self.save, self.ctx)
        cur["wrong"] = 1  # 小黃鴨只擋第一次
        self.assertEqual(rogue._damage(run, cur), round(10 * 0.7 * 0.8))
        self.assertEqual(rogue._price(run, 100), 100)
        rogue._add_relic(run, "golden_keyboard")
        rogue._add_relic(run, "lucky_cat")
        self.assertEqual(rogue._price(run, 100), 80)

    def test_mod_relic_effect(self):
        rogue.MOD_RELICS["mod:sword"] = {"name": "劍", "glyph": "劍", "desc": "經驗 ×2", "effect": {"xp_mult": 2.0}}
        run = rogue.start_run(self.save, seed=10)
        cur = fight_ready(self.save, self.ctx)
        problem = {"title": "x", "difficulty": "Easy", "tags": []}
        base = rogue._win(self.save, dict(cur), problem)[0]["xp"]
        run["relics"].append("mod:sword")
        cur = fight_ready(self.save, self.ctx)
        self.assertEqual(rogue._win(self.save, cur, problem)[0]["xp"], base * 2)

    def test_hint_penalty(self):
        rogue.start_run(self.save, seed=11)
        cur = fight_ready(self.save, self.ctx)
        slug = cur["offers"][0]["slug"]
        rogue.choose(self.save, slug)
        rogue.note_hint(self.save, slug, 2)
        problem = {"title": "x", "difficulty": "Medium", "tags": []}
        xp = rogue._win(self.save, cur, problem)[0]["xp"]
        self.assertEqual(xp, round(engine.DIFF_XP["Medium"] * 0.7))
