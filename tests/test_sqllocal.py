"""本機 SQL 練習場的測試：解析題目、建表、跑查詢、對答案。

真正執行時連的是 SQL Server（pyodbc）；這裡用 sqlite3 代替資料庫，
因為建表與放資料用的語法（DROP TABLE IF EXISTS、[欄名]、? 參數）兩邊都通，不需要裝 SQL Server。
"""
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from game import sqllocal as S  # noqa: E402

# 照 LeetCode 175. Combine Two Tables 的格式寫的題目敘述（兩張表、答案裡有 null）
CONTENT_175 = """<p>Table: <code>Person</code></p>
<pre>
+-------------+---------+
| Column Name | Type    |
+-------------+---------+
| personId    | int     |
| lastName    | varchar |
| firstName   | varchar |
+-------------+---------+
</pre>
<p>Table: <code>Address</code></p>
<pre>
+-------------+---------+
| Column Name | Type    |
+-------------+---------+
| addressId   | int     |
| personId    | int     |
| city        | varchar |
| state       | varchar |
+-------------+---------+
</pre>
<p>Return the result table in <strong>any order</strong>.</p>
<p><strong class="example">Example 1:</strong></p>
<pre>
<strong>Input:</strong>
Person table: ...
<strong>Output:</strong>
+-----------+----------+---------------+----------+
| firstName | lastName | city          | state    |
+-----------+----------+---------------+----------+
| Allen     | Wang     | Null          | Null     |
| Bob       | Alice    | New York City | New York |
+-----------+----------+---------------+----------+
</pre>"""
CASES_175 = json.dumps({
    "headers": {"Person": ["personId", "lastName", "firstName"], "Address": ["addressId", "personId", "city", "state"]},
    "rows": {"Person": [[1, "Wang", "Allen"], [2, "Alice", "Bob"]],
             "Address": [[1, 2, "New York City", "New York"], [2, 3, "Leetcode", "California"]]}})
Q175 = {"content": CONTENT_175, "exampleTestcases": CASES_175}

# 照 LeetCode 197. Rising Temperature 的格式（date 型別、有排序要求的變形）
CONTENT_197 = """<p>Table: <code>Weather</code></p>
<pre>
+---------------+---------+
| Column Name   | Type    |
+---------------+---------+
| id            | int     |
| recordDate    | date    |
| temperature   | int     |
+---------------+---------+
</pre>
<p>Return the result table <strong>ordered by</strong> id.</p>
<p><strong class="example">Example 1:</strong></p>
<pre>
<strong>Output:</strong>
+----+
| id |
+----+
| 2  |
| 4  |
+----+
</pre>"""
CASES_197 = json.dumps({"headers": {"Weather": ["id", "recordDate", "temperature"]},
                        "rows": {"Weather": [[1, "2015-01-01", 10], [2, "2015-01-02", 25],
                                             [3, "2015-01-03", 20], [4, "2015-01-04", 30]]}})
Q197 = {"content": CONTENT_197, "exampleTestcases": CASES_197}


class _Cur:
    def __init__(self, db):
        self.c = db.cursor()

    def execute(self, sql, params=None):
        self.c.execute(sql, params or ())
        return self

    description = property(lambda self: self.c.description)

    def fetchall(self):
        return self.c.fetchall()

    def nextset(self):
        return False


class FakeConn:
    """跟 pyodbc 連線一樣的介面，底下是 sqlite3。"""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")

    def cursor(self):
        return _Cur(self.db)

    def close(self):
        pass


class ParseTests(unittest.TestCase):
    def test_schema_and_types(self):
        schema = S.parse_schema(CONTENT_175)
        self.assertEqual(list(schema), ["Person", "Address"])
        self.assertEqual(schema["Address"][0], ("addressId", "int"))
        self.assertEqual(S.sql_type("int"), "INT")
        self.assertEqual(S.sql_type("varchar"), "NVARCHAR(255)")
        self.assertEqual(S.sql_type("date"), "DATE")
        self.assertEqual(S.sql_type("enum"), "NVARCHAR(255)")
        self.assertEqual(S.sql_type("", [1, 2, None]), "INT")
        self.assertEqual(S.sql_type("", ["2020-01-01"]), "DATE")

    def test_expected_and_order(self):
        exp = S.parse_expected(CONTENT_175)
        self.assertEqual(exp[0][0], ["firstName", "lastName", "city", "state"])
        self.assertEqual(exp[0][1][0], ["Allen", "Wang", "Null", "Null"])
        self.assertFalse(S.is_ordered(CONTENT_175))
        self.assertTrue(S.is_ordered(CONTENT_197))

    def test_create_statements_quote_names(self):
        stmts = S.table_statements(S.parse_schema(CONTENT_175), S.parse_cases(CASES_175)[0])
        self.assertIn("CREATE TABLE [Person] ([personId] INT NULL, [lastName] NVARCHAR(255) NULL", stmts[1][0])
        self.assertEqual(sum(1 for s, p in stmts if p is not None), 4)  # 2 + 2 筆資料


class RunTests(unittest.TestCase):
    def test_left_join_with_nulls_is_accepted(self):
        code = ("SELECT p.firstName, p.lastName, a.city, a.state FROM Person p "
                "LEFT JOIN Address a ON a.personId = p.personId")
        r = S.run_local(Q175, code, conn=FakeConn(), server="test")
        self.assertEqual((r["status_msg"], r["total_correct"], r["total_testcases"]), ("Accepted", 1, 1))

    def test_inner_join_is_wrong_answer(self):
        code = "SELECT p.firstName, p.lastName, a.city, a.state FROM Person p JOIN Address a ON a.personId = p.personId"
        r = S.run_local(Q175, code, conn=FakeConn(), server="test")
        self.assertEqual(r["status_msg"], "Wrong Answer")
        self.assertIn("Bob", r["cases"][0]["output"])

    def test_wrong_column_name_is_wrong_answer(self):
        code = "SELECT p.firstName AS fname, p.lastName, a.city, a.state FROM Person p LEFT JOIN Address a ON a.personId = p.personId"
        self.assertEqual(S.run_local(Q175, code, conn=FakeConn())["status_msg"], "Wrong Answer")

    def test_ordered_problem_checks_order(self):
        good = "SELECT w.id FROM Weather w JOIN Weather y ON w.id = y.id + 1 WHERE w.temperature > y.temperature ORDER BY w.id"
        bad = good.replace("ORDER BY w.id", "ORDER BY w.id DESC")
        self.assertEqual(S.run_local(Q197, good, conn=FakeConn())["status_msg"], "Accepted")
        self.assertEqual(S.run_local(Q197, bad, conn=FakeConn())["status_msg"], "Wrong Answer")

    def test_syntax_error_is_runtime_error(self):
        r = S.run_local(Q197, "SELEC id FROM Weather", conn=FakeConn())
        self.assertEqual(r["status_msg"], "Runtime Error")
        self.assertTrue(r["cases"][0]["error"])

    def test_custom_input_has_no_expected_answer(self):
        mine = json.dumps({"headers": {"Weather": ["id", "recordDate", "temperature"]},
                           "rows": {"Weather": [[1, "2020-01-01", 5], [2, "2020-01-02", 1]]}})
        r = S.run_local(Q197, "SELECT id FROM Weather", data_input=mine, conn=FakeConn())
        self.assertEqual(r["status_msg"], "Finished")
        self.assertIsNone(r["cases"][0]["expected"])

    def test_setup_then_drop(self):
        conn = FakeConn()
        info = S.setup(Q175, conn=conn, server="test")
        self.assertEqual(info["tables"], {"Person": 2, "Address": 2})
        self.assertEqual(conn.db.execute("SELECT COUNT(*) FROM Address").fetchone()[0], 2)
        self.assertEqual(S.drop(Q175, conn=conn, server="test")["dropped"], ["Person", "Address"])
        with self.assertRaises(sqlite3.OperationalError):
            conn.db.execute("SELECT * FROM Person")

    def test_without_pyodbc_or_driver_is_unsupported(self):
        import builtins
        real = builtins.__import__

        def fake(name, *a, **k):
            if name == "pyodbc":
                raise ImportError(name)
            return real(name, *a, **k)
        builtins.__import__ = fake
        try:
            with self.assertRaises(S.Unsupported):
                S.connect()
        finally:
            builtins.__import__ = real


if __name__ == "__main__":
    unittest.main()
