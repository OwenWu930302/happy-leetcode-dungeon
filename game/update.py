"""新版提示：啟動時問 GitHub 最新的 Release，比這個 EXE 的建置時間新，就在首頁提醒。

只提醒、不自動下載、不自動替換 EXE。從原始碼執行時不檢查（用 git pull 更新）。
設定頁可以關掉（config.json 的 checkUpdates）。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "OwenWu930302/happy-leetcode-dungeon"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
STATE = {"checked": False, "available": None, "error": None}


def build_info(app_dir: Path, frozen: bool) -> dict:
    try:
        info = json.loads((Path(app_dir) / "game" / "build_info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        info = {}
    info["frozen"] = frozen
    info["short"] = (info.get("sha") or "")[:7]
    return info


def _parse(ts: str):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def newer(release: dict, info: dict) -> bool:
    """發佈時間比建置時間晚 30 分鐘以上才算新版（自己這次建置發佈也要幾分鐘）。"""
    pub, built = _parse(release.get("published_at")), _parse(info.get("built"))
    if not pub or not built:
        return False
    return pub > built + timedelta(minutes=30)


def check(session_get, info: dict):
    """session_get(url, timeout) → 回應物件（有 .ok、.json()）。結果放在 STATE。"""
    STATE["checked"] = True
    try:
        r = session_get(API, timeout=6)
        if not r.ok:
            STATE["error"] = f"GitHub 回應 {r.status_code}"
            return
        rel = r.json()
    except Exception as e:  # noqa: BLE001
        STATE["error"] = str(e)[:200]
        return
    if newer(rel, info):
        STATE["available"] = {"name": rel.get("name") or rel.get("tag_name"), "tag": rel.get("tag_name"),
                              "published": rel.get("published_at"), "url": rel.get("html_url"),
                              "notes": (rel.get("body") or "")[:600]}


def start(session_get, info: dict, enabled: bool):
    if not enabled or not info.get("frozen") or not info.get("built"):
        return
    threading.Thread(target=check, args=(session_get, info), daemon=True).start()
