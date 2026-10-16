import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from game import localrun as L  # noqa: E402
import fixtures as F  # noqa: E402

HAS_CXX = L.find_cxx() is not None


class ParseTests(unittest.TestCase):
    def test_examples_assignments(self):
        ex = L.parse_examples(F.PAIR_SUM["content"])
        self.assertEqual(ex, [(["[1,4,6]", "10"], "[1,2]"), (["[5,5]", "10"], "[0,1]")])

    def test_examples_new_format(self):
        self.assertEqual(L.parse_examples(F.SHOUT["content"]), [(['"hey"'], '"HEY"')])

    def test_examples_design(self):
        ex = L.parse_examples(F.COUNTER["content"])
        self.assertEqual(ex[0][0], ['["Tally","add","add","total"]', "[[5],[2],[3],[]]"])
        self.assertEqual(ex[0][1], "[null, null, null, 10]")

    def test_same_answer(self):
        self.assertTrue(L.same_answer("[1,2]", "[1, 2]"))
        self.assertFalse(L.same_answer("[2,1]", "[1,2]"))
        self.assertTrue(L.same_answer("[2,1]", "[1,2]", any_order=True))
        self.assertTrue(L.same_answer("2.000001", "2.00000"))
        self.assertFalse(L.same_answer("true", "1"))
        self.assertTrue(L.same_answer('"a"', '"a"'))

    def test_signature(self):
        self.assertEqual(L._signature(F.PAIR_SUM["codeSnippets"][1]["code"], "cpp"),
                         {"kind": "func", "name": "pairSum", "params": ["vector<int>& vals", "int goal"]})
        sig = L._signature(F.COUNTER["codeSnippets"][1]["code"], "cpp")
        self.assertEqual((sig["kind"], sig["name"], sig["ctor"], sig["methods"]), ("design", "Tally", ["int"], ["add", "total"]))
        self.assertEqual(L._signature(F.COUNTER["codeSnippets"][0]["code"], "python3")["methods"], ["add", "total"])

    def test_interactive_unsupported(self):
        with self.assertRaises(L.Unsupported):
            L._signature(F.INTERACTIVE["codeSnippets"][0]["code"], "python3")


class RunBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_it(self, q, lang, code, data=None):
        return L.run_local(q, lang, code, 10, "sol", data, self.tmp)


class PythonRunTests(RunBase):
    def test_accepted(self):
        code = ("class Solution:\n    def pairSum(self, vals, goal):\n        seen = {}\n"
                "        for i, v in enumerate(vals):\n            if goal - v in seen: return [seen[goal - v], i]\n"
                "            seen[v] = i\n")
        r = self.run_it(F.PAIR_SUM, "python3", code)
        self.assertEqual(r["status_msg"], "Accepted")
        self.assertEqual((r["total_correct"], r["total_testcases"]), (2, 2))

    def test_any_order_and_wrong(self):
        r = self.run_it(F.PAIR_SUM, "python3", "class Solution:\n    def pairSum(self, vals, goal):\n        return [len(vals)-1, len(vals)-2]\n")
        self.assertEqual([c["ok"] for c in r["cases"]], [True, True])  # 題目說可以任意順序
        r = self.run_it(F.PAIR_SUM, "python3", "class Solution:\n    def pairSum(self, vals, goal):\n        return [0, 0]\n")
        self.assertEqual(r["status_msg"], "Wrong Answer")

    def test_runtime_error_points_at_line(self):
        r = self.run_it(F.SHOUT, "python3", "class Solution:\n    def shout(self, w):\n        return w[99]\n")
        self.assertEqual(r["status_msg"], "Runtime Error")
        self.assertIn("第 13 行", r["runtime_error"])  # 前面有 10 行說明，程式第 3 行
        self.assertIn("w[99]", r["runtime_error"])

    def test_syntax_error(self):
        r = self.run_it(F.SHOUT, "python3", "class Solution:\n    def shout(self, w)\n        return w\n")
        self.assertEqual(r["status_msg"], "Compile Error")
        self.assertIn("第 12 行", r["compile_error"])

    def test_print_is_captured(self):
        r = self.run_it(F.SHOUT, "python3", "class Solution:\n    def shout(self, w):\n        print('hi', w)\n        return w.upper()\n")
        self.assertEqual(r["cases"][0]["stdout"], "hi hey\n")
        self.assertEqual(r["status_msg"], "Accepted")

    def test_design(self):
        code = ("class Tally:\n    def __init__(self, start: int):\n        self.t = start\n"
                "    def add(self, x: int) -> None:\n        self.t += x\n    def total(self) -> int:\n        return self.t\n")
        r = self.run_it(F.COUNTER, "python3", code)
        self.assertEqual(r["status_msg"], "Accepted", r)

    def test_linked_list_and_tree(self):
        r = self.run_it(F.REVERSE_LIST, "python3", "class Solution:\n    def flipChain(self, head):\n        prev = None\n"
                        "        while head:\n            head.next, prev, head = prev, head, head.next\n        return prev\n")
        self.assertEqual(r["status_msg"], "Accepted", r)
        r = self.run_it(F.TREE_DEPTH, "python3", "class Solution:\n    def treeHeight(self, root):\n"
                        "        return 0 if not root else 1 + max(self.treeHeight(root.left), self.treeHeight(root.right))\n")
        self.assertEqual(r["status_msg"], "Accepted", r)

    def test_custom_input_without_answer(self):
        r = self.run_it(F.SHOUT, "python3", "class Solution:\n    def shout(self, w):\n        return w.upper()\n", '"hey"\n"yo"')
        self.assertEqual(r["status_msg"], "Finished")
        self.assertEqual([c.get("ok") for c in r["cases"]], [True, None])

    def test_timeout(self):
        r = self.run_it(F.SHOUT, "python3", "class Solution:\n    def shout(self, w):\n        while True: pass\n")
        self.assertEqual(r["status_msg"], "Time Limit Exceeded")

    def test_hidden_argument_unsupported(self):
        with self.assertRaises(L.Unsupported):
            self.run_it(F.HIDDEN_ARG, "python3", "class Solution:\n    def hasLoop(self, head):\n        return True\n")

    def test_other_language_unsupported(self):
        with self.assertRaises(L.Unsupported):
            self.run_it(F.SHOUT, "java", "class Solution {}")


@unittest.skipUnless(HAS_CXX, "沒有 C++ 編譯器")
class CppRunTests(RunBase):
    def test_accepted_and_wrong(self):
        ok = ("class Solution {\npublic:\n    vector<int> pairSum(vector<int>& vals, int goal) {\n"
              "        unordered_map<int,int> s;\n        for (int i = 0; i < (int)vals.size(); i++) {\n"
              "            if (s.count(goal - vals[i])) return {s[goal - vals[i]], i};\n            s[vals[i]] = i;\n        }\n"
              "        return {};\n    }\n};")
        self.assertEqual(self.run_it(F.PAIR_SUM, "cpp", ok)["status_msg"], "Accepted")
        bad = "class Solution {\npublic:\n    vector<int> pairSum(vector<int>& vals, int goal) { return {0, 0}; }\n};"
        self.assertEqual(self.run_it(F.PAIR_SUM, "cpp", bad)["status_msg"], "Wrong Answer")

    def test_compile_error_line(self):
        r = self.run_it(F.SHOUT, "cpp", "class Solution {\npublic:\n    string shout(string w) {\n        return w\n    }\n};")
        self.assertEqual(r["status_msg"], "Compile Error")
        self.assertIn("sol:15", r["compile_error"])  # 第 5 行的 } 前面少了分號

    def test_design_and_nodes(self):
        tally = ("class Tally {\n    int t;\npublic:\n    Tally(int start) : t(start) {}\n    void add(int x) { t += x; }\n"
                 "    int total() { return t; }\n};")
        self.assertEqual(self.run_it(F.COUNTER, "cpp", tally)["status_msg"], "Accepted")
        flip = ("class Solution {\npublic:\n    ListNode* flipChain(ListNode* head) {\n        ListNode* p = nullptr;\n"
                "        while (head) { auto n = head->next; head->next = p; p = head; head = n; }\n        return p;\n    }\n};")
        self.assertEqual(self.run_it(F.REVERSE_LIST, "cpp", flip)["status_msg"], "Accepted")
        h = ("class Solution {\npublic:\n    int treeHeight(TreeNode* r) { return r ? 1 + max(treeHeight(r->left), treeHeight(r->right)) : 0; }\n};")
        self.assertEqual(self.run_it(F.TREE_DEPTH, "cpp", h)["status_msg"], "Accepted")

    def test_runtime_error(self):
        r = self.run_it(F.SHOUT, "cpp", "class Solution {\npublic:\n    string shout(string w) { return string(1, w.at(50)); }\n};")
        self.assertEqual(r["status_msg"], "Runtime Error")


if __name__ == "__main__":
    unittest.main()
