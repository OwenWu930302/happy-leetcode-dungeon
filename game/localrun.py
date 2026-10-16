"""本地試跑：用題目的範例測資，在自己的電腦上直接跑 Python／C++。

不經過 LeetCode，所以幾乎不會失敗、也不需要登入；跑不了的題目（互動題、
有隱藏參數的題目、沒裝編譯器……）會丟出 Unsupported，呼叫端改用線上試跑。

正確答案從題目敘述裡的範例（Input / Output）讀出來，用輸入內容對應，
所以自訂測資只要跟某個範例一樣，也會幫你對答案。
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

__all__ = ["Unsupported", "run_local", "parse_examples", "find_python", "find_cxx", "env_info", "same_answer"]

SUPPORTED = ("python3", "cpp")
WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if WIN else 0  # CREATE_NO_WINDOW：子程序不要跳出黑色視窗


class Unsupported(Exception):
    """這題（或這台電腦）沒辦法本地跑；訊息是給玩家看的白話原因。"""


# ---------------------------------------------------------------------------
# 找執行環境
# ---------------------------------------------------------------------------
_CACHE: dict = {}


def _probe(cmd: list, timeout=8) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return (r.stdout or r.stderr).decode("utf-8", "replace").strip()


def find_python() -> tuple[str, str] | None:
    """回傳 (直譯器路徑, 版本字串)。打包成 EXE 時 sys.executable 是遊戲本身，要另外找。"""
    if "py" in _CACHE:
        return _CACHE["py"]
    cands = []
    if os.environ.get("LCD_PYTHON"):
        cands.append(os.environ["LCD_PYTHON"])
    if not getattr(sys, "frozen", False):
        cands.append(sys.executable)
    for name in ("python3", "python", "py"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    found = None
    for c in cands:
        args = [c, "-3"] if Path(c).stem.lower() == "py" else [c]
        # Windows 的 WindowsApps\python.exe 可能只是「開微軟商店」的捷徑，要實際跑跑看
        ver = _probe(args + ["-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"])
        if ver and re.fullmatch(r"3\.(\d+)\.\d+", ver) and int(ver.split(".")[1]) >= 8:
            found = (" ".join(args) if len(args) > 1 else c, f"Python {ver}")
            break
    _CACHE["py"] = found
    return found


def _py_cmd(found) -> list:
    exe = found[0]
    return exe.split(" ") if exe.endswith(" -3") else [exe]


def find_cxx() -> tuple[str, str] | None:
    """回傳 (編譯器路徑, 版本字串)，找不到就 None。"""
    if "cxx" in _CACHE:
        return _CACHE["cxx"]
    cands = []
    if os.environ.get("LCD_CXX"):
        cands.append(os.environ["LCD_CXX"])
    for name in ("g++", "clang++"):
        w = shutil.which(name)
        if w:
            cands.append(w)
    if WIN:
        for p in (r"C:\msys64\ucrt64\bin\g++.exe", r"C:\msys64\mingw64\bin\g++.exe",
                  r"C:\msys64\clang64\bin\clang++.exe", r"C:\MinGW\bin\g++.exe",
                  r"C:\mingw64\bin\g++.exe", r"C:\Program Files\LLVM\bin\clang++.exe"):
            if Path(p).exists():
                cands.append(p)
    found = None
    for c in cands:
        out = _probe([c, "--version"])
        if out:
            first = out.splitlines()[0]
            m = re.search(r"(\d+\.\d+(\.\d+)?)", first)
            kind = "clang++" if "clang" in first.lower() else "g++"
            found = (c, f"{kind} {m.group(1) if m else ''}".strip())
            break
    _CACHE["cxx"] = found
    return found


def env_info() -> dict:
    py, cxx = find_python(), find_cxx()
    return {"python": {"path": py[0], "version": py[1]} if py else None,
            "cxx": {"path": cxx[0], "version": cxx[1]} if cxx else None}


# ---------------------------------------------------------------------------
# 讀題目：範例的輸入與正確答案
# ---------------------------------------------------------------------------
def _norm(v: str) -> str:
    """把一個值整理成固定格式，方便比對（去空白、統一 JSON 寫法）。"""
    v = v.strip()
    try:
        return json.dumps(json.loads(v), separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        return re.sub(r"\s+", " ", v)


def _json_values(s: str) -> list[str]:
    """把一段文字裡連續出現的 JSON 值一個個切出來（設計題的兩行輸入）。"""
    dec, out, i = json.JSONDecoder(), [], 0
    while i < len(s):
        while i < len(s) and s[i] in " \t\r\n,":
            i += 1
        if i >= len(s):
            break
        try:
            val, j = dec.raw_decode(s, i)
        except ValueError:
            return []
        out.append(json.dumps(val, separators=(",", ":"), ensure_ascii=False))
        i = j
    return out


def _split_assign(s: str) -> list[str] | None:
    """`nums = [2,7], target = 9` → ['[2,7]', '9']。"""
    s = s.strip()
    if not re.match(r"^[A-Za-z_]\w*\s*=", s):
        return None
    parts = re.split(r",\s*(?=[A-Za-z_]\w*\s*=(?!=))", s)
    vals = []
    for p in parts:
        if "=" not in p:
            return None
        vals.append(_norm(p.split("=", 1)[1]))
    return vals


def _html_text(content: str) -> str:
    t = re.sub(r"<br\s*/?>|</p>|</div>|</pre>|</li>", "\n", content or "", flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = htmllib.unescape(t).replace("\xa0", " ")
    return t


def parse_examples(content: str) -> list[tuple[list[str], str]]:
    """從題目敘述讀出每個範例的 (輸入值清單, 正確輸出)。讀不出來的範例就略過。"""
    text = _html_text(content)
    out = []
    pat = re.compile(r"Input:?\s*(.*?)\n?\s*Output:?\s*(.*?)(?:\n|$)", re.S)
    for m in pat.finditer(text):
        raw_in, raw_out = m.group(1).strip(), m.group(2).strip()
        if not raw_out:
            # 輸出寫在下一行
            rest = text[m.end():].lstrip("\n ")
            raw_out = rest.split("\n", 1)[0].strip()
        vals = _split_assign(raw_in)
        if vals is None:
            vals = _json_values(raw_in)
        if not vals or not raw_out:
            continue
        out.append((vals, raw_out))
    return out


def _expected_value(raw: str) -> str:
    """範例的 Output 有時會多寫說明（`2, nums = [1,2,_]`），只取回傳值那段。"""
    raw = raw.strip()
    try:
        json.loads(raw)
        return _norm(raw)
    except ValueError:
        pass
    m = re.match(r"^(.*?),\s*[A-Za-z_]\w*\s*=", raw)
    if m:
        return _norm(m.group(1))
    return _norm(raw)


# ---------------------------------------------------------------------------
# 比對答案
# ---------------------------------------------------------------------------
def _close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b if isinstance(a, bool) and isinstance(b, bool) else False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-5 * max(1.0, abs(b))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b))
    return a == b


def same_answer(got: str, expected: str, any_order: bool = False) -> bool:
    try:
        a, b = json.loads(got), json.loads(expected)
    except ValueError:
        return _norm(got) == _norm(expected)
    if _close(a, b):
        return True
    if any_order and isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        key = lambda v: json.dumps(v, sort_keys=True)
        return _close(sorted(a, key=key), sorted(b, key=key))
    return False


# ---------------------------------------------------------------------------
# 讀範本：函式名稱、參數、設計題的類別
# ---------------------------------------------------------------------------
_SPECIAL = re.compile(
    r"\b(Node|NestedInteger|MountainArray|Employee|Sea|Master|Robot|ArrayReader|BinaryMatrix|"
    r"CustomFunction|ImmutableListNode|HtmlParser|Relation|Iterator|PolyNode|Foo|FooBar|ZeroEvenOdd|"
    r"H2O|DiningPhilosophers|FizzBuzz|BoundedBlockingQueue|TrafficLight)\b"
    r"|isBadVersion|\bguess\(|read4|\bknows\(|rand7|rand10|already defined for you")


def _split_top(s: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _strip_comments(code: str) -> str:
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    code = re.sub(r"//[^\n]*", "", code)
    return re.sub(r"(?m)^\s*#(?!include)[^\n]*", "", code)


def _signature(snippet: str, lang: str) -> dict:
    """回傳 {'kind': 'func'|'design', 'name', 'params': [型別或名稱], 'methods', 'ctor'}。"""
    body = _strip_comments(snippet)
    # 用原始範本判斷（「API is already defined」這類說明寫在註解裡）
    if _SPECIAL.search(snippet) or re.search(r"\bclass\s+Node\b|\bstruct\s+Node\b", snippet):
        raise Unsupported("這題用了 LeetCode 內建的特殊介面（互動題或自訂節點），本地沒辦法重現。")
    if lang == "python3":
        classes = re.findall(r"^class\s+(\w+)", body, re.M)
        if "Solution" in classes:
            m = re.search(r"class\s+Solution\b.*?\n\s+def\s+(\w+)\s*\(\s*self\s*,?(.*?)\)\s*(->[^:]*)?:", body, re.S)
            if not m:
                raise Unsupported("看不懂這題的函式範本。")
            return {"kind": "func", "name": m.group(1), "params": _split_top(m.group(2))}
        if classes:
            cls = classes[0]
            methods = [n for n in re.findall(r"^\s+def\s+(\w+)\s*\(", body, re.M) if not n.startswith("_")]
            return {"kind": "design", "name": cls, "methods": methods}
        raise Unsupported("看不懂這題的程式範本。")
    # C++
    m = re.search(r"class\s+Solution\s*\{(.*)\}\s*;", body, re.S)
    if m:
        f = re.search(r"([\w:<>,\s\*&]+?)\b(\w+)\s*\(([^)]*)\)\s*(const\s*)?\{", m.group(1))
        if not f:
            raise Unsupported("看不懂這題的函式範本。")
        return {"kind": "func", "name": f.group(2), "params": _split_top(f.group(3))}
    m = re.search(r"class\s+(\w+)\s*\{(.*)\}\s*;", body, re.S)
    if not m:
        raise Unsupported("看不懂這題的程式範本。")
    cls, inner = m.group(1), m.group(2)
    ctor = re.search(rf"\b{cls}\s*\(([^)]*)\)\s*\{{", inner)
    ctor_types = []
    for p in _split_top(ctor.group(1)) if ctor else []:
        t = re.match(r"(.*?)(\w+)\s*$", p)
        ctor_types.append((t.group(1) if t else p).strip())
    methods = []
    for nm in re.findall(r"\b(\w+)\s*\([^;{)]*\)\s*(?:const\s*)?\{", inner):
        if nm not in (cls, "if", "for", "while", "switch", "return") and nm not in methods:
            methods.append(nm)
    return {"kind": "design", "name": cls, "ctor": ctor_types, "methods": methods}


# ---------------------------------------------------------------------------
# 把測資切成一筆一筆
# ---------------------------------------------------------------------------
def _cases(data_input: str, per_case: int) -> list[list[str]]:
    lines = [ln.rstrip("\r") for ln in (data_input or "").split("\n") if ln.strip() != ""]
    if not lines:
        raise Unsupported("沒有測資可以跑。")
    if len(lines) % per_case:
        raise Unsupported(f"測資的行數（{len(lines)}）不是參數個數（{per_case}）的倍數，請檢查自訂測資。")
    return [lines[i:i + per_case] for i in range(0, len(lines), per_case)]


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------
PY_PRELUDE = r'''
from typing import *
import collections, heapq, bisect, math, itertools, functools, string, re, random, operator, array, sys, builtins
from collections import *
from heapq import *
from bisect import *
from math import *
from functools import *
from itertools import *
pow = builtins.pow  # math 的 pow 不支援第三個參數，換回內建的
try:
    from sortedcontainers import SortedList, SortedDict, SortedSet
except ImportError:
    pass

class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
'''

PY_HARNESS = r'''
import contextlib, inspect, io, json, linecache, re, sys, time, traceback
sys.setrecursionlimit(100000)
cases_path, out_path, user_path, offset, display, kind, name = sys.argv[1:8]
PRELUDE = open(sys.argv[8], encoding="utf-8").read()
HINTS = json.loads(sys.argv[9]) if len(sys.argv) > 9 else []  # 官方範本的參數型別（玩家拿掉型別提示時用）
ns = {"__name__": "__main__"}
exec(PRELUDE, ns)
ListNode, TreeNode = ns["ListNode"], ns["TreeNode"]
results = {"cases": []}

def save():
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False)

def user_tb(exc):
    frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == display]
    msg = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    lines = [msg] + [f"    第 {f.lineno} 行，在 {f.name}()：{(f.line or '').strip()}" for f in frames[-4:]]
    return "\n".join(lines)

src = open(user_path, encoding="utf-8").read()
full = "\n" * int(offset) + src
linecache.cache[display] = (len(full), None, full.splitlines(True), display)  # 錯誤訊息才能印出那一行
try:
    code = compile(full, display, "exec")
    exec(code, ns)
except SyntaxError as e:
    results["compile_error"] = f"{type(e).__name__}: {e.msg}\n    第 {e.lineno} 行：{(e.text or '').strip()}"
    save(); sys.exit(0)
except BaseException as e:
    results["compile_error"] = user_tb(e)
    save(); sys.exit(0)

def kind_of(ann):
    s = ann if isinstance(ann, str) else str(ann)
    for node in ("ListNode", "TreeNode"):
        if node in s:
            return node + ("[]" if re.search(r"[Ll]ist\[\s*(typing\.)?(Optional\[)?[\w.]*" + node, s) else "")
    return ""

def mk_list(vals):
    d = t = ListNode()
    for v in vals:
        t.next = ListNode(v); t = t.next
    return d.next

def mk_tree(vals):
    if not vals or vals[0] is None:
        return None
    root = TreeNode(vals[0]); q = [root]; i = 1; h = 0
    while h < len(q) and i < len(vals):
        n = q[h]; h += 1
        if i < len(vals) and vals[i] is not None:
            n.left = TreeNode(vals[i]); q.append(n.left)
        i += 1
        if i < len(vals) and vals[i] is not None:
            n.right = TreeNode(vals[i]); q.append(n.right)
        i += 1
    return root

def conv_in(v, k):
    if k == "ListNode": return mk_list(v or [])
    if k == "TreeNode": return mk_tree(v or [])
    if k == "ListNode[]": return [mk_list(x or []) for x in v]
    if k == "TreeNode[]": return [mk_tree(x or []) for x in v]
    return v

def conv_out(v):
    if isinstance(v, ListNode):
        out, seen = [], 0
        while v is not None and seen < 100000:
            out.append(v.val); v = v.next; seen += 1
        return out
    if isinstance(v, TreeNode):
        out, q, h = [], [v], 0
        while h < len(q):
            n = q[h]; h += 1
            if n is None:
                out.append(None); continue
            out.append(n.val); q.append(n.left); q.append(n.right)
        while out and out[-1] is None:
            out.pop()
        return out
    if isinstance(v, (list, tuple)):
        return [conv_out(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [conv_out(x) for x in v]
    return v

def call(fn, raw_args, inplace, hints=()):
    try:
        params = list(inspect.signature(fn).parameters.values())
        ret = inspect.signature(fn).return_annotation
    except (TypeError, ValueError):
        params, ret = [], inspect.Signature.empty
    def k(i):
        own = kind_of(params[i].annotation) if i < len(params) and params[i].annotation is not inspect.Parameter.empty else ""
        return own or (hints[i] if i < len(hints) else "")
    args = [conv_in(a, k(i)) for i, a in enumerate(raw_args)]
    r = fn(*args)
    if inplace and r is None and args and (ret is None or ret == "None" or ret is inspect.Signature.empty):
        return conv_out(args[0])
    return conv_out(r)

for case in json.load(open(cases_path, encoding="utf-8")):
    buf = io.StringIO()
    t0 = time.perf_counter()
    item = {}
    try:
        vals = [json.loads(x) for x in case]
        with contextlib.redirect_stdout(buf):
            if kind == "func":
                obj = ns["Solution"]()
                item["out"] = json.dumps(call(getattr(obj, name), vals, True, HINTS), separators=(",", ":"), ensure_ascii=False)
            else:
                names, argl = vals
                outs = [None]
                cls = ns[names[0]]
                try:
                    ps = list(inspect.signature(cls.__init__).parameters.values())[1:]
                except (TypeError, ValueError):
                    ps = []
                obj = cls(*[conv_in(a, kind_of(ps[i].annotation) if i < len(ps) else "") for i, a in enumerate(argl[0])])
                for nm, a in zip(names[1:], argl[1:]):
                    outs.append(call(getattr(obj, nm), a, False))
                item["out"] = json.dumps(outs, separators=(",", ":"), ensure_ascii=False)
    except BaseException as e:
        item["error"] = user_tb(e)
    item["ms"] = round((time.perf_counter() - t0) * 1000, 2)
    item["stdout"] = buf.getvalue()[-4000:]
    results["cases"].append(item)
    save()
    if "error" in item:
        break
save()
'''


def _hint_kind(ann: str) -> str:
    """跟 harness 裡的 kind_of 一樣的規則，用在官方範本的型別提示上。"""
    for node in ("ListNode", "TreeNode"):
        if node in ann:
            return node + ("[]" if re.search(r"[Ll]ist\[\s*(Optional\[)?\s*" + node, ann) else "")
    return ""


def _run_python(sig, cases, code, offset, display, workdir: Path, timeout: float) -> dict:
    found = find_python()
    if not found:
        raise Unsupported("找不到 Python 3.8 以上的直譯器。到設定頁的「環境檢查」看怎麼安裝。")
    (workdir / "solution.py").write_text(code, encoding="utf-8")
    (workdir / "prelude.py").write_text(PY_PRELUDE, encoding="utf-8")
    (workdir / "harness.py").write_text(PY_HARNESS, encoding="utf-8")
    (workdir / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    out = workdir / "out.json"
    hints = [_hint_kind(p.split(":", 1)[1]) if ":" in p else "" for p in sig.get("params", [])]
    cmd = _py_cmd(found) + ["-X", "utf8", str(workdir / "harness.py"), str(workdir / "cases.json"), str(out),
                            str(workdir / "solution.py"), str(offset), display, sig["kind"], sig["name"],
                            str(workdir / "prelude.py"), json.dumps(hints)]
    timed_out, stderr = False, ""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(workdir),
                           creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        stderr = r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        timed_out = True
    res = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {"cases": []}
    res["timed_out"] = timed_out
    if not res["cases"] and not res.get("compile_error") and not timed_out and stderr.strip():
        res["crash"] = stderr.strip()[-2000:]
    res["engine"] = found[1]
    return res


# ---------------------------------------------------------------------------
# C++
# ---------------------------------------------------------------------------
CPP_PRELUDE = r'''
#include <algorithm>
#include <array>
#include <bitset>
#include <cassert>
#include <cctype>
#include <chrono>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <list>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <stack>
#include <string>
#include <string_view>
#include <tuple>
#include <type_traits>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using namespace std;
'''

CPP_NODES = r'''
struct ListNode {
    int val; ListNode *next;
    ListNode() : val(0), next(nullptr) {}
    ListNode(int x) : val(x), next(nullptr) {}
    ListNode(int x, ListNode *n) : val(x), next(n) {}
};
struct TreeNode {
    int val; TreeNode *left; TreeNode *right;
    TreeNode() : val(0), left(nullptr), right(nullptr) {}
    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
    TreeNode(int x, TreeNode *l, TreeNode *r) : val(x), left(l), right(r) {}
};
'''

CPP_SUPPORT = r'''
namespace lcd {
struct J { int t = 0; bool b = false; std::string v; std::vector<J> a; };  // t: 0 null 1 bool 2 num 3 str 4 arr
struct Rd {
    const std::string& s; size_t i = 0;
    explicit Rd(const std::string& s_) : s(s_) {}
    void ws() { while (i < s.size() && std::isspace((unsigned char)s[i])) i++; }
    static void utf8(std::string& o, unsigned cp) {
        if (cp < 0x80) o += (char)cp;
        else if (cp < 0x800) { o += (char)(0xC0 | (cp >> 6)); o += (char)(0x80 | (cp & 0x3F)); }
        else { o += (char)(0xE0 | (cp >> 12)); o += (char)(0x80 | ((cp >> 6) & 0x3F)); o += (char)(0x80 | (cp & 0x3F)); }
    }
    J val() {
        ws(); J j;
        if (i >= s.size()) throw std::runtime_error("測資格式錯誤：資料不完整");
        char c = s[i];
        if (c == '[') {
            j.t = 4; i++; ws();
            if (i < s.size() && s[i] == ']') { i++; return j; }
            while (true) {
                j.a.push_back(val()); ws();
                if (i < s.size() && s[i] == ',') { i++; continue; }
                if (i < s.size() && s[i] == ']') { i++; break; }
                throw std::runtime_error("測資格式錯誤：陣列沒有結尾");
            }
            return j;
        }
        if (c == '"') {
            j.t = 3; i++;
            while (i < s.size() && s[i] != '"') {
                if (s[i] == '\\' && i + 1 < s.size()) {
                    char e = s[++i];
                    if (e == 'n') j.v += '\n'; else if (e == 't') j.v += '\t'; else if (e == 'r') j.v += '\r';
                    else if (e == 'u' && i + 4 < s.size()) { utf8(j.v, (unsigned)std::stoul(s.substr(i + 1, 4), nullptr, 16)); i += 4; }
                    else j.v += e;
                    i++;
                } else j.v += s[i++];
            }
            i++;
            return j;
        }
        if (s.compare(i, 4, "true") == 0) { j.t = 1; j.b = true; i += 4; return j; }
        if (s.compare(i, 5, "false") == 0) { j.t = 1; i += 5; return j; }
        if (s.compare(i, 4, "null") == 0) { i += 4; return j; }
        j.t = 2; size_t st = i;
        while (i < s.size() && (std::isdigit((unsigned char)s[i]) || std::strchr("+-.eE", s[i]))) i++;
        j.v = s.substr(st, i - st);
        if (j.v.empty()) throw std::runtime_error("測資格式錯誤：看不懂的值");
        return j;
    }
};
inline J parse(const std::string& s) { Rd r(s); return r.val(); }

template <class T> struct Tag {};
template <class T> using D = std::decay_t<T>;
inline long long num(const J& j) { return j.t == 1 ? (long long)j.b : std::stoll(j.v); }
inline int from(const J& j, Tag<int>) { return (int)num(j); }
inline long from(const J& j, Tag<long>) { return (long)num(j); }
inline long long from(const J& j, Tag<long long>) { return num(j); }
inline unsigned from(const J& j, Tag<unsigned>) { return (unsigned)std::stoull(j.v); }
inline unsigned long long from(const J& j, Tag<unsigned long long>) { return std::stoull(j.v); }
inline double from(const J& j, Tag<double>) { return std::stod(j.v); }
inline float from(const J& j, Tag<float>) { return std::stof(j.v); }
inline bool from(const J& j, Tag<bool>) { return j.t == 1 ? j.b : num(j) != 0; }
inline char from(const J& j, Tag<char>) { return j.t == 3 ? (j.v.empty() ? '\0' : j.v[0]) : (char)num(j); }
inline std::string from(const J& j, Tag<std::string>) { return j.v; }
inline ListNode* from(const J& j, Tag<ListNode*>) {
    ListNode d; ListNode* t = &d;
    for (auto& x : j.a) { t->next = new ListNode((int)num(x)); t = t->next; }
    return d.next;
}
inline TreeNode* from(const J& j, Tag<TreeNode*>) {
    if (j.a.empty() || j.a[0].t == 0) return nullptr;
    TreeNode* root = new TreeNode((int)num(j.a[0]));
    std::queue<TreeNode*> q; q.push(root); size_t i = 1;
    while (!q.empty() && i < j.a.size()) {
        TreeNode* n = q.front(); q.pop();
        if (i < j.a.size() && j.a[i].t != 0) { n->left = new TreeNode((int)num(j.a[i])); q.push(n->left); } i++;
        if (i < j.a.size() && j.a[i].t != 0) { n->right = new TreeNode((int)num(j.a[i])); q.push(n->right); } i++;
    }
    return root;
}
template <class T> std::vector<T> from(const J& j, Tag<std::vector<T>>) {
    std::vector<T> r; r.reserve(j.a.size());
    for (auto& x : j.a) r.push_back(from(x, Tag<T>{}));
    return r;
}

inline void out(std::ostream& o, bool b) { o << (b ? "true" : "false"); }
inline void out(std::ostream& o, char c) { o << '"' << c << '"'; }
inline void out(std::ostream& o, int x) { o << x; }
inline void out(std::ostream& o, long x) { o << x; }
inline void out(std::ostream& o, long long x) { o << x; }
inline void out(std::ostream& o, unsigned x) { o << x; }
inline void out(std::ostream& o, unsigned long x) { o << x; }
inline void out(std::ostream& o, unsigned long long x) { o << x; }
inline void out(std::ostream& o, double x) { o << std::fixed << std::setprecision(5) << x << std::defaultfloat; }
inline void out(std::ostream& o, float x) { out(o, (double)x); }
inline void out(std::ostream& o, const std::string& s) {
    o << '"';
    for (char c : s) {
        if (c == '"' || c == '\\') o << '\\' << c;
        else if (c == '\n') o << "\\n";
        else o << c;
    }
    o << '"';
}
inline void out(std::ostream& o, const char* s) { out(o, std::string(s ? s : "")); }
inline void out(std::ostream& o, ListNode* h) {
    o << '['; int n = 0;
    for (; h && n < 100000; h = h->next, n++) { if (n) o << ','; o << h->val; }
    o << ']';
}
inline void out(std::ostream& o, TreeNode* r) {
    std::vector<TreeNode*> q{r}; std::vector<std::string> v;
    if (!r) { o << "[]"; return; }
    for (size_t h = 0; h < q.size(); h++) {
        if (!q[h]) { v.push_back("null"); continue; }
        v.push_back(std::to_string(q[h]->val)); q.push_back(q[h]->left); q.push_back(q[h]->right);
    }
    while (!v.empty() && v.back() == "null") v.pop_back();
    o << '[';
    for (size_t i = 0; i < v.size(); i++) { if (i) o << ','; o << v[i]; }
    o << ']';
}
template <class T> void out(std::ostream& o, const std::vector<T>& v) {
    o << '[';
    for (size_t i = 0; i < v.size(); i++) { if (i) o << ','; out(o, (T)v[i]); }
    o << ']';
}

template <class C, class R, class... A, size_t... I>
void call_impl(C& obj, R (C::*f)(A...), const J& args, std::ostream& o, bool inplace, std::index_sequence<I...>) {
    if (args.a.size() != sizeof...(A)) throw std::runtime_error("測資的參數個數跟函式不符");
    std::tuple<D<A>...> t{from(args.a[I], Tag<D<A>>{})...};
    if constexpr (std::is_void_v<R>) {
        (obj.*f)(std::get<I>(t)...);
        if constexpr (sizeof...(A) > 0) { if (inplace) { out(o, std::get<0>(t)); return; } }
        o << "null";
    } else {
        auto&& r = (obj.*f)(std::get<I>(t)...);
        out(o, r);
    }
}
template <class C, class R, class... A>
void call(C& obj, R (C::*f)(A...), const J& args, std::ostream& o, bool inplace) {
    call_impl(obj, f, args, o, inplace, std::index_sequence_for<A...>{});
}
template <class C, class R, class... A, size_t... I>
void call_impl_c(C& obj, R (C::*f)(A...) const, const J& args, std::ostream& o, bool inplace, std::index_sequence<I...>) {
    if (args.a.size() != sizeof...(A)) throw std::runtime_error("測資的參數個數跟函式不符");
    std::tuple<D<A>...> t{from(args.a[I], Tag<D<A>>{})...};
    if constexpr (std::is_void_v<R>) { (obj.*f)(std::get<I>(t)...); o << "null"; }
    else { auto&& r = (obj.*f)(std::get<I>(t)...); out(o, r); }
}
template <class C, class R, class... A>
void call(C& obj, R (C::*f)(A...) const, const J& args, std::ostream& o, bool inplace) {
    call_impl_c(obj, f, args, o, inplace, std::index_sequence_for<A...>{});
}
}  // namespace lcd
'''


def _cpp_case_code(sig) -> tuple[int, str]:
    """產生「跑一筆測資」的 C++ 程式碼。回傳 (每筆幾行, 程式碼)。"""
    if sig["kind"] == "func":
        n = len(sig["params"])
        body = ("lcd::J args; args.t = 4;\n"
                f"for (int k = 0; k < {n}; k++) args.a.push_back(lcd::parse(L[c + k]));\n"
                "Solution* sol = new Solution();\n"
                f"lcd::call(*sol, &Solution::{sig['name']}, args, o, true);\n")
        return max(n, 1), body
    cls = sig["name"]
    ctor = sig.get("ctor") or []
    lines = ["lcd::J names = lcd::parse(L[c]); lcd::J al = lcd::parse(L[c + 1]);",
             "if (names.a.size() != al.a.size()) throw std::runtime_error(\"方法名稱和參數的個數不一樣\");",
             f"{cls}* obj = nullptr;",
             "{ const lcd::J& ca = al.a[0];",
             f"  if (ca.a.size() != {len(ctor)}) throw std::runtime_error(\"建構子的參數個數不符\");"]
    for k, t in enumerate(ctor):
        lines.append(f"  auto a{k} = lcd::from(ca.a[{k}], lcd::Tag<lcd::D<{t}>>{{}});")
    lines.append(f"  obj = new {cls}({', '.join(f'a{k}' for k in range(len(ctor)))}); }}")
    lines.append("o << \"[null\";")
    lines.append("for (size_t m = 1; m < names.a.size(); m++) { o << ','; const std::string& nm = names.a[m].v; const lcd::J& ma = al.a[m];")
    first = True
    for meth in sig["methods"]:
        lines.append(f"  {'if' if first else 'else if'} (nm == \"{meth}\") lcd::call(*obj, &{cls}::{meth}, ma, o, false);")
        first = False
    lines.append(("  else " if not first else "  ") + "throw std::runtime_error(\"沒有這個方法：\" + nm); }")
    lines.append("o << ']';")
    return 2, "\n".join(lines) + "\n"


CPP_MAIN = r'''
int main(int argc, char** argv) {
    std::ifstream in(argv[1]);
    std::ofstream res(argv[2], std::ios::binary);
    std::vector<std::string> L; std::string line;
    while (std::getline(in, line)) { if (!line.empty() && line.back() == '\r') line.pop_back(); L.push_back(line); }
    const size_t N = __PER_CASE__;
    for (size_t c = 0; c + N <= L.size(); c += N) {
        std::ostringstream o;
        auto t0 = std::chrono::steady_clock::now();
        bool ok = true; std::string err;
        try {
__CASE__
        } catch (const std::exception& e) { ok = false; err = e.what(); }
        catch (...) { ok = false; err = "丟出了未知的例外"; }
        double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        std::cout << std::flush << "\x1e" << std::flush;
        if (ok) res << "R " << ms << " " << o.str() << "\n";
        else { for (auto& ch : err) if (ch == '\n') ch = ' '; res << "E " << ms << " " << err << "\n"; }
        res.flush();
        if (!ok) break;
    }
    return 0;
}
'''

_CRASH = {
    -11: "記憶體存取錯誤（Segmentation fault）：可能是陣列越界、用了空指標，或遞迴太深。",
    -6: "程式中止（abort）：可能是 assert 失敗或記憶體被破壞。",
    -8: "算術錯誤：可能除以 0 或整數溢位。",
    3221225477: "記憶體存取錯誤（Access violation）：可能是陣列越界、用了空指標。",
    3221225725: "堆疊溢位（Stack overflow）：遞迴太深了。",
    3221225620: "算術錯誤：除以 0。",
    3221226505: "程式中止：可能是 STL 的檢查失敗（例如 vector 越界）。",
}


def _clean_compile(stderr: str, src_name: str, workdir: Path) -> str:
    s = stderr.replace(str(workdir) + os.sep, "").replace(str(workdir), "")
    keep = []
    for ln in s.splitlines():
        if "In function 'int main" in ln or "lcd_harness" in ln and "error" not in ln:
            continue
        keep.append(ln)
    s = "\n".join(keep).strip()
    return s[:6000] or "編譯失敗（沒有錯誤訊息）"


def _run_cpp(sig, cases, code, offset, display, workdir: Path, timeout: float, cache_dir: Path) -> dict:
    found = find_cxx()
    if not found:
        raise Unsupported("沒找到 C++ 編譯器（g++ 或 clang++）。到設定頁的「環境檢查」看怎麼安裝。")
    per, case_code = _cpp_case_code(sig)
    nodes = "" if re.search(r"(?m)^\s*struct\s+(ListNode|TreeNode)\b", code) else CPP_NODES
    src = (CPP_PRELUDE + nodes + f'#line {offset + 1} "{display}"\n' + code + "\n#line 1 \"lcd_harness.cpp\"\n"
           + CPP_SUPPORT + CPP_MAIN.replace("__PER_CASE__", str(per)).replace("__CASE__", case_code))
    digest = hashlib.sha1((found[0] + "\0" + src).encode("utf-8")).hexdigest()[:16]
    cache_dir.mkdir(parents=True, exist_ok=True)
    exe = cache_dir / (digest + (".exe" if WIN else ""))
    res = {"cases": [], "engine": found[1]}
    if not exe.exists():
        cpp = workdir / "main.cpp"
        cpp.write_text(src, encoding="utf-8")
        cmd = [found[0], "-std=gnu++17", "-O2", "-o", str(exe), str(cpp)]
        if WIN and "clang" not in found[1]:
            cmd[1:1] = ["-static"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120, cwd=str(workdir),
                               creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            res["compile_error"] = "編譯超過 2 分鐘，先暫停。"
            return res
        if r.returncode != 0 or not exe.exists():
            res["compile_error"] = _clean_compile(r.stderr.decode("utf-8", "replace"), display, workdir)
            return res
        for old in cache_dir.iterdir():  # 只留最近幾個執行檔
            if old != exe and old.stat().st_mtime < time.time() - 3600:
                try:
                    old.unlink()
                except OSError:
                    pass
    inp = workdir / "cases.txt"
    inp.write_text("\n".join(ln for case in cases for ln in case) + "\n", encoding="utf-8")
    outp = workdir / "out.txt"
    timed_out, rc, stdout = False, 0, b""
    try:
        r = subprocess.run([str(exe), str(inp), str(outp)], capture_output=True, timeout=timeout,
                           cwd=str(workdir), creationflags=NO_WINDOW, stdin=subprocess.DEVNULL)
        rc, stdout = r.returncode, r.stdout
    except subprocess.TimeoutExpired as e:
        timed_out, stdout = True, e.stdout or b""
    outs = stdout.decode("utf-8", "replace").split("\x1e")
    lines = outp.read_text(encoding="utf-8", errors="replace").splitlines() if outp.exists() else []
    for k, ln in enumerate(lines):
        tag, ms, rest = (ln.split(" ", 2) + ["", ""])[:3]
        item = {"ms": round(float(ms or 0), 2), "stdout": outs[k][-4000:] if k < len(outs) else ""}
        if tag == "R":
            item["out"] = rest
        else:
            item["error"] = rest
        res["cases"].append(item)
    if not timed_out and rc != 0 and len(res["cases"]) < len(cases):
        msg = _CRASH.get(rc, f"程式異常結束（代碼 {rc}）")
        tail = outs[len(res["cases"])] if len(res["cases"]) < len(outs) else ""
        res["cases"].append({"error": msg, "stdout": tail[-4000:], "ms": 0})
    res["timed_out"] = timed_out
    return res


# ---------------------------------------------------------------------------
# 對外介面
# ---------------------------------------------------------------------------
def run_local(q: dict, lang: str, code: str, offset: int, display: str, data_input: str,
              cache_root: Path) -> dict:
    """本地試跑，回傳跟 LeetCode 試跑結果長得差不多的 dict（另外多了 cases 明細）。"""
    if lang not in SUPPORTED:
        raise Unsupported(f"本地試跑目前支援 Python 3 和 C++，這個檔案是 {lang}。")
    snippet = next((s["code"] for s in q.get("codeSnippets") or [] if s["langSlug"] == lang), "")
    if not snippet:
        raise Unsupported("這題沒有這個語言的範本。")
    sig = _signature(snippet, lang)
    per = 2 if sig["kind"] == "design" else max(1, len(sig["params"]))
    examples = parse_examples(q.get("content") or "")
    if sig["kind"] == "func" and examples and any(len(v) != per for v, _ in examples):
        raise Unsupported("這題的範例有函式以外的隱藏參數（例如鏈結串列的環），本地沒辦法重現。")
    data_input = data_input or q.get("exampleTestcases") or ""
    cases = _cases(data_input, per)
    expected_map = {tuple(vals): _expected_value(out) for vals, out in examples}
    any_order = bool(re.search(r"any order", _html_text(q.get("content") or ""), re.I))

    timeout = min(15.0, 3.0 + 1.0 * len(cases)) + (0 if lang == "python3" else 2.0)
    cache_root.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(dir=str(cache_root)) as tmp:
        work = Path(tmp)
        if lang == "python3":
            raw = _run_python(sig, cases, code, offset, display, work, timeout)
        else:
            raw = _run_cpp(sig, cases, code, offset, display, work, timeout,
                           cache_root / "bin" / q.get("titleSlug", "x"))
    elapsed = round((time.perf_counter() - t0) * 1000)

    result = {"local": True, "engine": raw.get("engine"), "_input": data_input, "elapsed_ms": elapsed,
              "cases": [], "code_answer": [], "expected_code_answer": [], "std_output_list": []}
    if raw.get("compile_error"):
        result.update(status_msg="Compile Error", compile_error=raw["compile_error"])
        return result
    if raw.get("crash"):
        result.update(status_msg="Runtime Error", runtime_error=raw["crash"])
        return result

    status = None
    judged = correct = 0
    for k, case in enumerate(cases):
        item = {"input": case, "expected": expected_map.get(tuple(_norm(x) for x in case))}
        got = raw["cases"][k] if k < len(raw["cases"]) else None
        if got is None:
            if raw.get("timed_out") and status is None:
                item["error"] = "超過時間限制：跑太久了（可能是無窮迴圈或演算法太慢）。"
                status = "Time Limit Exceeded"
                result["cases"].append(item)
            break
        item["ms"] = got.get("ms")
        item["stdout"] = got.get("stdout", "")
        if "error" in got:
            item["error"] = got["error"]
            status = status or "Runtime Error"
            result["runtime_error"] = got["error"]
            result["cases"].append(item)
            break
        item["output"] = got["out"]
        if item["expected"] is not None:
            judged += 1
            item["ok"] = same_answer(got["out"], item["expected"], any_order)
            correct += item["ok"]
        result["cases"].append(item)
    for item in result["cases"]:
        result["code_answer"].append(item.get("output", ""))
        result["expected_code_answer"].append(item.get("expected") or "")
        result["std_output_list"].append(item.get("stdout", ""))
    if status is None:
        if judged and correct < judged:
            status = "Wrong Answer"
        elif judged == len(cases):
            status = "Accepted"
        else:
            status = "Finished"  # 有測資沒有標準答案（自訂測資），只顯示輸出
    result.update(status_msg=status, total_correct=correct, total_testcases=judged)
    return result
