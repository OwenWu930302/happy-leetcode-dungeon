"""錯題本：每次出招沒過（答錯、超時、執行錯誤、編譯錯誤），自動記下當時的程式碼和出錯的測資。

玩家可以替每一筆標上錯因；之後同一題通過了，這題的錯題會自動標成「已解決」。
星璃（複習流派）的推薦會優先從還沒解決的錯題裡出題。
"""
from __future__ import annotations

import json
import secrets
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

CAUSES = ["邊界條件", "整數溢位", "複雜度太高", "看錯題目", "語法／打字", "演算法想錯", "其他"]
STATUS_ZH = {
    "Wrong Answer": "答案錯誤", "Time Limit Exceeded": "超過時間", "Runtime Error": "執行錯誤",
    "Compile Error": "編譯錯誤", "Memory Limit Exceeded": "超過記憶體", "Output Limit Exceeded": "輸出太多",
}
MAX_CODE = 20000
MAX_ENTRIES = 500


def _path(data_dir: Path) -> Path:
    return Path(data_dir) / "mistakes.json"


def load(data_dir: Path) -> list[dict]:
    try:
        return json.loads(_path(data_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(data_dir: Path, items: list[dict]):
    p = _path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-MAX_ENTRIES:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add(data_dir: Path, p: dict, lang: str, result: dict, code: str = "") -> dict:
    status = result.get("status_msg") or "?"
    err = result.get("full_runtime_error") or result.get("runtime_error") \
        or result.get("full_compile_error") or result.get("compile_error") or ""
    entry = {
        "id": secrets.token_hex(4), "slug": p["slug"], "pid": p.get("id"), "title": p.get("title"),
        "difficulty": p.get("difficulty"), "time": _now(), "status": status, "lang": lang,
        "passed": f"{result.get('total_correct')}/{result.get('total_testcases')}"
                  if result.get("total_testcases") is not None else None,
        "input": (result.get("last_testcase") or "")[:2000],
        "output": str(result.get("code_output") or "")[:2000],
        "expected": str(result.get("expected_output") or "")[:2000],
        "error": str(err)[:3000], "code": (code or "")[:MAX_CODE],
        "cause": None, "note": "", "resolved": False,
    }
    items = load(data_dir)
    items.append(entry)
    _save(data_dir, items)
    return entry


def resolve(data_dir: Path, slug: str) -> int:
    """這題通過了：把它的錯題都標成已解決，回傳標了幾筆。"""
    items = load(data_dir)
    n = 0
    for e in items:
        if e["slug"] == slug and not e["resolved"]:
            e["resolved"], e["resolved_at"] = True, _now()
            n += 1
    if n:
        _save(data_dir, items)
    return n


def tag(data_dir: Path, entry_id: str, cause=None, note=None) -> dict:
    if cause is not None and cause not in CAUSES and cause != "":
        raise ValueError("沒有這種錯因")
    items = load(data_dir)
    for e in items:
        if e["id"] == entry_id:
            if cause is not None:
                e["cause"] = cause or None
            if note is not None:
                e["note"] = str(note)[:300]
            _save(data_dir, items)
            return e
    raise ValueError("找不到這筆錯題")


def remove(data_dir: Path, entry_id: str):
    items = load(data_dir)
    keep = [e for e in items if e["id"] != entry_id]
    if len(keep) == len(items):
        raise ValueError("找不到這筆錯題")
    _save(data_dir, keep)


def open_by_slug(items: list[dict]) -> dict:
    """還沒解決的錯題數，依題目分組（給推薦用）。"""
    return dict(Counter(e["slug"] for e in items if not e["resolved"]))


def summary(items: list[dict], days: int | None = None) -> dict:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d") if days else ""
    rec = [e for e in items if e["time"] >= since]
    causes = Counter(e["cause"] for e in rec if e.get("cause"))
    return {
        "total": len(rec), "open": sum(1 for e in rec if not e["resolved"]),
        "resolved": sum(1 for e in rec if e["resolved"]),
        "byStatus": dict(Counter(e["status"] for e in rec)),
        "byCause": dict(causes.most_common()),
        "untagged": sum(1 for e in rec if not e.get("cause")),
    }


def public(items: list[dict], limit: int = 120) -> list[dict]:
    """給畫面用：新的在前，未解決的優先。"""
    order = sorted(items, key=lambda e: e["time"], reverse=True)
    order = sorted(order, key=lambda e: e["resolved"])  # 穩定排序：未解決在前，各自新到舊
    return [{**e, "statusZh": STATUS_ZH.get(e["status"], e["status"])} for e in order[:limit]]
