"""羈絆：跟哪位看板娘一起刷題，就累積她的好感度。每 10 點升一級，5、10、15 級解鎖一段劇情。

加分來源（全部記在當下的夥伴身上）：
- 通過一次提交 +3（遊戲裡、終端機、同步回來的新紀錄都算；同一次掃描最多算 10 筆）
- 遠征擊敗一隻怪 +2、征服地城 +12、倒下 +4（一起經歷過也是羈絆）
- 完成賞金 +3
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

PER_LEVEL = 10
MAX_LEVEL = 20
EVENT_POINTS = {"win": 2, "won": 12, "dead": 4, "bounty": 3}
AC_POINTS = 3
AC_CAP = 10

_STORIES = None


def stories(static_dir: Path) -> dict:
    global _STORIES
    if _STORIES is None:
        try:
            _STORIES = json.loads((Path(static_dir) / "stories.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _STORIES = {"levels": [5, 10, 15], "stories": {}}
    return _STORIES


def level_of(points: int) -> int:
    return min(MAX_LEVEL, points // PER_LEVEL)


def _add(save, pid, pts, static_dir, events):
    b = save["meta"].setdefault("bond", {})
    before = b.get(pid, 0)
    after = min(before + pts, PER_LEVEL * MAX_LEVEL)
    b[pid] = after
    lv0, lv1 = level_of(before), level_of(after)
    if lv1 > lv0:
        data = stories(static_dir)
        story = next((s for s in data["stories"].get(pid, []) if lv0 < s["level"] <= lv1), None)
        events.append({"kind": "bond", "pid": pid, "level": lv1,
                       "story": {"level": story["level"], "title": story["title"]} if story else None})


def scan(save, records: dict, pid: str, run_events: list, static_dir: Path) -> list:
    """看看有沒有新的通過紀錄、遠征事件，加好感度。回傳要通知玩家的事件。"""
    meta = save["meta"]
    events = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    since = meta.get("bond_since")
    if since is None:  # 第一次啟用：以前的紀錄不算，從現在開始累積
        meta["bond_since"] = now
        since = now
    new = sorted(a["time"] for r in records.values() for a in r.get("attempts", [])
                 if a.get("accepted") and (a.get("time") or "") > since)
    if new:
        meta["bond_since"] = new[-1]
        _add(save, pid, AC_POINTS * min(len(new), AC_CAP), static_dir, events)
    pts = sum(EVENT_POINTS.get(e.get("kind"), 0) for e in run_events)
    if pts:
        _add(save, pid, pts, static_dir, events)
    return events


def public(save, companions: dict, static_dir: Path) -> dict:
    data = stories(static_dir)
    b = save["meta"].get("bond", {})
    out = {}
    for pid in companions:
        pts = b.get(pid, 0)
        lv = level_of(pts)
        out[pid] = {
            "points": pts, "level": lv, "max": MAX_LEVEL,
            "into": pts - lv * PER_LEVEL if lv < MAX_LEVEL else PER_LEVEL, "per": PER_LEVEL,
            "stories": [{"level": s["level"], "title": s["title"], "unlocked": lv >= s["level"]}
                        for s in data["stories"].get(pid, [])],
        }
    return out


def read_story(save, pid: str, level: int, static_dir: Path) -> dict:
    lv = level_of(save["meta"].get("bond", {}).get(pid, 0))
    for s in stories(static_dir)["stories"].get(pid, []):
        if s["level"] == level:
            if lv < level:
                raise ValueError(f"羈絆 Lv{level} 才能看這段劇情")
            return s
    raise ValueError("沒有這段劇情")
