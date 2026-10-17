"""模板庫的每一份程式都要能用：C++ 能編譯，Python 能執行，基本功能正確。"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game import localrun, templates  # noqa: E402

CXX = localrun.find_cxx()


class TemplateTests(unittest.TestCase):
    def test_every_template_has_both_languages(self):
        for key, t in templates.TEMPLATES.items():
            self.assertTrue(t.get("title") and t.get("python") and t.get("cpp"), key)
        for alias, target in templates.ALIASES.items():
            self.assertIn(target, templates.TEMPLATES, alias)

    def test_python_templates_run(self):
        for key, t in templates.TEMPLATES.items():
            ns = {}
            exec(localrun.PY_PRELUDE, ns)
            exec(t["python"], ns)  # 定義函式／類別不能出錯
        ns = {}
        exec(localrun.PY_PRELUDE, ns)
        for key in ("binary-search", "sliding-window", "prefix-sum", "monotonic-stack", "union-find",
                    "trie", "shortest-path", "topological-sort", "string-matching", "binary-indexed-tree"):
            exec(templates.TEMPLATES[key]["python"], ns)
        self.assertEqual(ns["first_true"](0, 100, lambda x: x * x >= 50), 8)
        self.assertEqual(ns["longest_window"]("eceba", 2), 3)
        self.assertEqual(ns["count_subarrays"]([1, 1, 1], 2), 2)
        self.assertEqual(ns["next_greater"]([2, 1, 3]), [3, 3, -1])
        d = ns["DSU"](4); d.union(0, 1); d.union(2, 3)
        self.assertNotEqual(d.find(0), d.find(2))
        tr = ns["Trie"](); tr.insert("apple")
        self.assertTrue(tr.search("apple") and tr.starts_with("app") and not tr.search("app"))
        self.assertEqual(ns["dijkstra"](3, [(0, 1, 4), (0, 2, 1), (2, 1, 1)], 0), [0, 2, 1])
        self.assertEqual(ns["topo_order"](2, [(0, 1), (1, 0)]), [])
        self.assertEqual(ns["find_all"]("abababa", "aba"), [0, 2, 4])
        f = ns["Fenwick"](5)
        for i, v in enumerate([1, 2, 3, 4, 5]):
            f.add(i, v)
        self.assertEqual(f.range_sum(1, 3), 9)

    @unittest.skipUnless(CXX, "沒有 C++ 編譯器")
    def test_cpp_templates_compile(self):
        body = "\n".join(t["cpp"] for t in templates.TEMPLATES.values())
        src = localrun.CPP_PRELUDE + localrun.CPP_NODES + body + "\nint main() { return 0; }\n"
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "t.cpp"
            f.write_text(src, encoding="utf-8")
            r = subprocess.run([CXX[0], "-std=gnu++17", "-fsyntax-only", str(f)], capture_output=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace")[:3000])

    def test_listing_unlocks_by_lit_nodes(self):
        nodes = [{"id": "hash-table", "name": "雜湊表", "lit": True}, {"id": "tree", "name": "樹", "lit": True},
                 {"id": "graph", "name": "圖論", "lit": False}]
        items = {i["id"]: i for i in templates.listing(nodes, "cpp")}
        self.assertTrue(items["hash-table"]["unlocked"])
        self.assertTrue(items["binary-tree"]["unlocked"])     # 透過別名「樹」解鎖
        self.assertEqual(items["binary-tree"]["lang"], "cpp")
        self.assertFalse(items["graph"]["unlocked"])
        self.assertNotIn("code", items["graph"])


if __name__ == "__main__":
    unittest.main()
