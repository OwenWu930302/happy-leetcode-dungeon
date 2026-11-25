# -*- coding: utf-8 -*-
"""本機 SQL 練習場：依 LeetCode 資料庫題，在自己電腦的 SQL Server 建出題目的資料表。

- 建立：照題目敘述的表格結構（欄位與型別）建表，放進範例資料（exampleTestcases）
- 刪除：把這題的資料表刪掉
- 本地試招：每個範例都重建一次資料表 → 跑你的 T-SQL → 跟題目範例的 Output 對答案

全部放在獨立的資料庫 LeetCodeLocal，不會碰到你其他的資料庫。
預設連到 LocalDB（Visual Studio 會一起裝）；要用別台 SQL Server，在 config.json 設 "sqlServer"。
需要 pyodbc 與 Microsoft ODBC Driver 17／18 for SQL Server；沒有的話丟 Unsupported，呼叫端改用線上試跑。
"""
from __future__ import annotations

import html as htmllib
import json
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

__all__ = ["Unsupported", "DB_NAME", "DEFAULT_SERVER", "parse_schema", "parse_cases", "parse_expected",
           "connect", "setup", "drop", "run_local", "ascii_table"]

DB_NAME = "LeetCodeLocal"
DEFAULT_SERVER = r"(localdb)\MSSQLLocalDB"
DRIVERS = ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server Native Client 11.0")


class Unsupported(Exception):
    """這台電腦沒辦法在本機跑 SQL（沒有 pyodbc、ODBC 驅動程式或 SQL Server）。"""


# ---------------------------------------------------------------------------
# 解析題目：表格結構、範例資料、範例答案
# ---------------------------------------------------------------------------
def _text(content: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", content or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return htmllib.unescape(t).replace("\xa0", " ").replace("\r\n", "\n")


def _ascii_rows(lines):
    """把 +---+ / | a | b | 的文字表格拆成 [[欄, 欄], ...]（第一列是表頭）。"""
    return [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines if ln.strip().startswith("|")]


def parse_schema(content: str) -> dict:
    """題目敘述裡每張表的「Column Name | Type」→ {表名: [(欄名, 型別), ...]}。"""
    text = _text(content)
    out = {}
    for m in re.finditer(r"Table:\s*([A-Za-z_]\w*)\s*\n((?:[ \t]*[+|].*\n)+)", text):
        rows = _ascii_rows(m.group(2).splitlines())
        if rows and len(rows[0]) >= 2 and rows[0][0].lower() == "column name":
            out[m.group(1)] = [(r[0], r[1]) for r in rows[1:] if len(r) >= 2 and r[0]]
    return out


def parse_cases(example_testcases: str) -> list:
    """exampleTestcases（每個範例一行 JSON）→ [{"headers": {表: [欄]}, "rows": {表: [[值]]}}, ...]。"""
    cases = []
    for ln in (example_testcases or "").splitlines():
        ln = ln.strip()
        if ln.startswith("{"):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            if isinstance(d.get("headers"), dict):
                cases.append(d)
    return cases


def parse_expected(content: str) -> list:
    """每個範例的 Output 表格 → [(表頭, [[值]]), ...]，依範例順序。"""
    text = _text(content)
    out = []
    for m in re.finditer(r"Output:\s*\n((?:[ \t]*[+|].*\n?)+)", text):
        rows = _ascii_rows(m.group(1).splitlines())
        if rows:
            out.append((rows[0], rows[1:]))
    return out


def is_ordered(content: str) -> bool:
    """題目有要求排序（ordered by／order by）時，答案要照順序比；不然不管順序。"""
    head = _text(content).split("Example 1")[0].lower()
    return "ordered by" in head or "order by" in head or "sorted by" in head


# ---------------------------------------------------------------------------
# 型別：LeetCode 的型別名稱 → T-SQL
# ---------------------------------------------------------------------------
def sql_type(name: str, values=()) -> str:
    t = (name or "").lower()
    if t in ("int", "integer", "smallint", "tinyint", "mediumint"):
        return "INT"
    if t == "bigint":
        return "BIGINT"
    if t.startswith(("decimal", "numeric")):
        return "DECIMAL(18,4)"
    if t in ("float", "double", "real"):
        return "FLOAT"
    if t == "date":
        return "DATE"
    if t in ("datetime", "timestamp"):
        return "DATETIME2(0)"
    if t in ("bool", "boolean", "bit"):
        return "BIT"
    if t in ("varchar", "char", "enum", "text", "string", "nvarchar"):
        return "NVARCHAR(255)"
    vals = [v for v in values if v is not None]  # 題目沒寫型別：看範例資料猜
    if vals and all(isinstance(v, bool) for v in vals):
        return "BIT"
    if vals and all(isinstance(v, int) and not isinstance(v, bool) for v in vals):
        return "INT"
    if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "FLOAT"
    if vals and all(isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
        return "DATE"
    return "NVARCHAR(255)"


def _q(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def table_statements(schema: dict, case: dict) -> list:
    """建表＋放資料的 SQL（參數化），回傳 [(sql, params), ...]。"""
    stmts = []
    for table, cols in case["headers"].items():
        rows = case.get("rows", {}).get(table, [])
        types = dict(schema.get(table, []))
        defs = []
        for i, c in enumerate(cols):
            defs.append(f"{_q(c)} {sql_type(types.get(c, ''), [r[i] for r in rows if i < len(r)])} NULL")
        stmts.append((f"DROP TABLE IF EXISTS {_q(table)}", None))
        stmts.append((f"CREATE TABLE {_q(table)} ({', '.join(defs)})", None))
        if rows:
            marks = ", ".join("?" for _ in cols)
            sql = f"INSERT INTO {_q(table)} ({', '.join(_q(c) for c in cols)}) VALUES ({marks})"
            for r in rows:
                stmts.append((sql, [_param(v) for v in r]))
    return stmts


def _param(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return v


def _tables(q: dict) -> list:
    names = list(parse_schema(q.get("content", "")))
    for case in parse_cases(q.get("exampleTestcases") or ""):
        names += [t for t in case["headers"] if t not in names]
    return names


# ---------------------------------------------------------------------------
# 連線
# ---------------------------------------------------------------------------
def connect(server: str = None):
    """連到 SQL Server 的 LeetCodeLocal 資料庫（沒有就建立）。回傳 (連線, 伺服器名稱)。"""
    try:
        import pyodbc
    except ImportError:
        raise Unsupported("沒有安裝 pyodbc（pip install pyodbc）")
    names = set(pyodbc.drivers())
    driver = next((d for d in DRIVERS if d in names), None)
    if not driver:
        raise Unsupported("沒找到 Microsoft ODBC Driver 17／18 for SQL Server")
    server = server or DEFAULT_SERVER
    base = f"DRIVER={{{driver}}};SERVER={server};Trusted_Connection=yes;TrustServerCertificate=yes"
    try:
        conn = pyodbc.connect(base + ";DATABASE=master", autocommit=True, timeout=30)
        conn.execute(f"IF DB_ID(N'{DB_NAME}') IS NULL CREATE DATABASE {_q(DB_NAME)}")
        conn.execute(f"USE {_q(DB_NAME)}")
    except pyodbc.Error as e:
        raise Unsupported(f"連不到 SQL Server（{server}）：{_err(e)}")
    return conn, server


def _err(e) -> str:
    msg = e.args[-1] if getattr(e, "args", None) else str(e)
    msg = re.sub(r"\[[^\]]*\]", "", str(msg))  # 拿掉 [Microsoft][ODBC Driver 17 …] 這些前綴
    return re.sub(r"\s*\(\d+\)\s*\(SQL\w+\)\s*$", "", msg).strip()


def _load(conn, q: dict, case: dict, schema: dict):
    cur = conn.cursor()
    for sql, params in table_statements(schema, case):
        if params is None:
            cur.execute(sql)
        else:
            cur.execute(sql, params)


# ---------------------------------------------------------------------------
# 建立／刪除
# ---------------------------------------------------------------------------
def setup(q: dict, server: str = None, case: int = 0, conn=None) -> dict:
    """依題目建出資料表並放進第 case+1 個範例的資料。"""
    cases = parse_cases(q.get("exampleTestcases") or "")
    if not cases:
        raise Unsupported("這題沒有可以用的範例資料表")
    case = max(0, min(case, len(cases) - 1))
    own = conn is None
    if own:
        conn, server = connect(server)
    try:
        _load(conn, q, cases[case], parse_schema(q.get("content", "")))
        rows = {t: len(cases[case].get("rows", {}).get(t, [])) for t in cases[case]["headers"]}
    finally:
        if own:
            conn.close()
    return {"server": server, "database": DB_NAME, "tables": rows, "case": case + 1, "cases": len(cases)}


def drop(q: dict, server: str = None, conn=None) -> dict:
    """刪掉這題的資料表。"""
    own = conn is None
    if own:
        conn, server = connect(server)
    try:
        names = _tables(q)
        cur = conn.cursor()
        for t in names:
            cur.execute(f"DROP TABLE IF EXISTS {_q(t)}")
    finally:
        if own:
            conn.close()
    return {"server": server, "database": DB_NAME, "dropped": names}


# ---------------------------------------------------------------------------
# 本地試招
# ---------------------------------------------------------------------------
def _norm(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    if s.lower() in ("null", "none"):
        return "null"
    try:
        d = Decimal(s)
        if d.is_finite():
            d = d.quantize(Decimal("0.00001")).normalize()
            return "0" if d == 0 else format(d, "f")
    except (InvalidOperation, ValueError):
        pass
    return s


def ascii_table(headers, rows) -> str:
    cells = [[str(h) for h in headers]] + [["null" if v is None else _show(v) for v in r] for r in rows]
    w = [max(len(r[i]) for r in cells) for i in range(len(headers))] if headers else []
    line = "+" + "+".join("-" * (x + 2) for x in w) + "+"
    fmt = lambda r: "| " + " | ".join(c.ljust(w[i]) for i, c in enumerate(r)) + " |"
    out = [line, fmt(cells[0]), line] + [fmt(r) for r in cells[1:]] + [line]
    return "\n".join(out)


def _show(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return _norm(v)
    return str(v)


def _same(got_h, got_rows, exp_h, exp_rows, ordered) -> bool:
    if [h.lower() for h in got_h] != [h.lower() for h in exp_h]:
        return False
    a = [tuple(_norm(v) for v in r) for r in got_rows]
    b = [tuple(_norm(v) for v in r) for r in exp_rows]
    return a == b if ordered else sorted(a) == sorted(b)


def _first_result(cur):
    while True:
        if cur.description:
            return [c[0] for c in cur.description], [list(r) for r in cur.fetchall()]
        if not cur.nextset():
            return None, None


def run_local(q: dict, code: str, data_input: str = None, server: str = None, conn=None) -> dict:
    """每個範例：重建資料表 → 跑玩家的 T-SQL → 跟範例 Output 對答案。回傳跟本地試跑一樣格式的結果。"""
    examples = q.get("exampleTestcases") or ""
    data_input = data_input or examples
    cases = parse_cases(data_input)
    if not cases:
        raise Unsupported("沒有可以用的測資（格式要跟 LeetCode 的資料表 JSON 一樣）")
    expected = parse_expected(q.get("content", "")) if data_input.strip() == examples.strip() else []
    ordered = is_ordered(q.get("content", ""))
    schema = parse_schema(q.get("content", ""))
    own = conn is None
    if own:
        conn, server = connect(server)
    start = time.time()
    result = {"local": True, "engine": f"SQL Server · {server or '本機'} · {DB_NAME}", "_input": data_input,
              "cases": [], "code_answer": [], "expected_code_answer": [], "std_output_list": []}
    correct = judged = 0
    try:
        for i, case in enumerate(cases):
            inp = [f"{t}：{len(case.get('rows', {}).get(t, []))} 列" for t in case["headers"]]
            item = {"input": inp, "output": "", "expected": None, "ok": None}
            if i < len(expected):
                item["expected"] = "\n" + ascii_table(*expected[i])
            try:
                _load(conn, q, case, schema)
                t0 = time.time()
                cur = conn.cursor()
                cur.execute(code)
                heads, rows = _first_result(cur)
                item["ms"] = int((time.time() - t0) * 1000)
            except Exception as e:  # noqa: BLE001  pyodbc.Error：語法錯、欄位名打錯…
                item["error"] = _err(e)
                item["ok"] = False if i < len(expected) else None
                judged += 1 if i < len(expected) else 0
                result["cases"].append(item)
                continue
            if heads is None:
                item["output"] = "（沒有查詢結果：記得要有 SELECT）"
            else:
                item["output"] = "\n" + ascii_table(heads, rows)
            if i < len(expected):
                judged += 1
                item["ok"] = heads is not None and _same(heads, rows, *expected[i], ordered)
                correct += item["ok"]
            result["cases"].append(item)
    finally:
        if own:
            conn.close()
    result["elapsed_ms"] = int((time.time() - start) * 1000)
    errors = [c for c in result["cases"] if c.get("error")]
    if errors and not correct:
        status = "Runtime Error"
        result["runtime_error"] = errors[0]["error"]
    elif judged:
        status = "Accepted" if correct == judged else "Wrong Answer"
    else:
        status = "Finished"
    result.update(status_msg=status, total_correct=correct, total_testcases=judged)
    return result
