"""SQL 題（LeetCode Database 題，用 MS SQL Server 作答）與遠征題型的測試（不需要網路）。"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lc  # noqa: E402
from game import engine  # noqa: E402

PROBLEMS = json.loads((ROOT / "data" / "problems.json").read_text(encoding="utf-8"))
SQL_PROBLEM = next(p for p in PROBLEMS if p["slug"] == "combine-two-tables")
ALGO_PROBLEM = next(p for p in PROBLEMS if p["slug"] == "two-sum")


class FocusTests(unittest.TestCase):
    def tearDown(self):
        engine.set_focus("algo")

    def test_default_focus_keeps_old_behaviour(self):
        engine.set_focus("algo")
        self.assertFalse(engine.playable(SQL_PROBLEM))
        self.assertTrue(engine.playable(ALGO_PROBLEM))

    def test_sql_focus_only_plays_free_sql_problems(self):
        engine.set_focus("sql")
        pool = [p for p in PROBLEMS if engine.playable(p)]
        self.assertTrue(pool)
        self.assertTrue(all(engine.is_sql(p) and not p["paidOnly"] for p in pool))
        self.assertFalse(engine.playable(ALGO_PROBLEM))

    def test_mixed_focus_plays_both(self):
        engine.set_focus("mixed")
        self.assertTrue(engine.playable(SQL_PROBLEM))
        self.assertTrue(engine.playable(ALGO_PROBLEM))

    def test_unknown_focus_falls_back_to_algo(self):
        engine.set_focus("nonsense")
        self.assertEqual(engine.FOCUS, "algo")

    def test_shell_and_concurrency_stay_excluded(self):
        engine.set_focus("mixed")
        for p in PROBLEMS:
            if {"shell", "concurrency"} & set(p["tags"]):
                self.assertFalse(engine.playable(p), p["slug"])

    def test_sql_focus_grows_sql_skill_and_recommends_sql(self):
        engine.set_focus("sql")
        tree = engine.build_tree(PROBLEMS, {})
        ids = {n["id"] for n in tree["nodes"]}
        self.assertIn("database", ids)
        power = engine.compute_power(PROBLEMS, {})
        picks = engine.recommend(PROBLEMS, {}, tree, power, k=5)
        self.assertTrue(picks)
        for item in picks:
            slug = item.get("slug") if isinstance(item, dict) else item
            p = next(x for x in PROBLEMS if x["slug"] == slug)
            self.assertTrue(engine.is_sql(p), slug)


class SqlSolutionFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (lc.CONFIG_PATH, lc.SOLUTIONS_DIR, lc.DATA_DIR, lc.fetch_question_detail)
        lc.CONFIG_PATH = self.tmp / "config.json"
        lc.SOLUTIONS_DIR = self.tmp / "solutions"
        lc.DATA_DIR = self.tmp / "data"
        lc.save_json(lc.CONFIG_PATH, {"lang": "csharp"})
        lc.fetch_question_detail = lambda slug: {
            "questionFrontendId": "175", "title": "Combine Two Tables", "difficulty": "Easy", "questionId": "175",
            "codeSnippets": [
                {"langSlug": "mysql", "code": "# Write your MySQL query statement below\n"},
                {"langSlug": "mssql", "code": "/* Write your T-SQL query statement below */\n"},
            ]}

    def tearDown(self):
        lc.CONFIG_PATH, lc.SOLUTIONS_DIR, lc.DATA_DIR, lc.fetch_question_detail = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sql_problem_uses_mssql_and_algo_keeps_setting(self):
        self.assertEqual(lc.lang_for(SQL_PROBLEM), "mssql")
        self.assertEqual(lc.lang_for(ALGO_PROBLEM), "csharp")
        self.assertEqual(lc.solution_path(SQL_PROBLEM).suffix, ".sql")

    def test_sql_is_never_the_algorithm_language(self):
        lc.save_json(lc.CONFIG_PATH, {"lang": "mssql"})
        self.assertEqual(lc.default_lang(), "python3")

    def test_create_and_read_sql_solution(self):
        path, created = lc.create_solution(SQL_PROBLEM, lang="python3")  # 要求別的語言也會改用 SQL
        self.assertTrue(created)
        self.assertEqual(path.suffix, ".sql")
        text = path.read_text(encoding="utf-8")
        self.assertIn("-- meta-lang: mssql", text)
        self.assertIn("T-SQL", text)
        path.write_text(text + "SELECT p.firstName FROM Person p;\n", encoding="utf-8")
        qid, lang, code, _ = lc.read_solution(SQL_PROBLEM)
        self.assertEqual((qid, lang), ("175", "mssql"))
        self.assertIn("SELECT p.firstName", code)
        self.assertNotIn("meta-", code)


if __name__ == "__main__":
    unittest.main()
