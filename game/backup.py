"""存檔快照：每天第一次開遊戲時，把進度壓成一個 zip，保留最近 14 份，可以一鍵還原。

只備份玩家自己的東西（紀錄、遊戲存檔、個人設定、錯題本、解題檔）。
登入用的 config.json 不放進備份：舊的 cookie 還原回來也是過期的，沒有意義，還多一份外洩風險。
"""
from __future__ import annotations

import re
import zipfile
from datetime import datetime
from pathlib import Path

KEEP = 14
DATA_FILES = ("records.json", "game.json", "profile.json", "mistakes.json", "contest.json", "weekly.json")
NAME_RE = re.compile(r"^backup-(\d{8})-(\d{6})(-[a-z]+)?\.zip$")


def backup_dir(root: Path) -> Path:
    return Path(root) / "backups"


def _members(root: Path):
    root = Path(root)
    for name in DATA_FILES:
        f = root / "data" / name
        if f.is_file():
            yield f, f"data/{name}"
    sol = root / "solutions"
    if sol.is_dir():
        for f in sorted(sol.rglob("*")):
            if f.is_file() and f.stat().st_size < 512 * 1024:
                yield f, "solutions/" + f.relative_to(sol).as_posix()


def snapshot(root: Path, tag: str = "") -> Path | None:
    """建立一份快照；沒有東西可備份就回傳 None。"""
    files = list(_members(root))
    if not files:
        return None
    d = backup_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    when = datetime.now().timestamp()
    while True:  # 同一秒按兩次就往後挪一秒
        stamp = datetime.fromtimestamp(when).strftime("%Y%m%d-%H%M%S")
        out = d / f"backup-{stamp}{'-' + tag if tag else ''}.zip"
        if not any(d.glob(f"backup-{stamp}*.zip")):
            break
        when += 1
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for f, arc in files:
            z.write(f, arc)
    tmp.replace(out)
    prune(root)
    return out


def prune(root: Path, keep: int = KEEP):
    items = sorted(backup_dir(root).glob("backup-*.zip"), key=lambda p: p.name, reverse=True)
    for old in items[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def daily(root: Path) -> Path | None:
    """今天還沒有快照就建一份。"""
    today = datetime.now().strftime("%Y%m%d")
    if any(p.name.startswith(f"backup-{today}") for p in backup_dir(root).glob("backup-*.zip")):
        return None
    return snapshot(root)


def listing(root: Path) -> list[dict]:
    out = []
    for p in sorted(backup_dir(root).glob("backup-*.zip"), key=lambda p: p.name, reverse=True):
        m = NAME_RE.match(p.name)
        if not m:
            continue
        when = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        try:
            with zipfile.ZipFile(p) as z:
                names = z.namelist()
        except zipfile.BadZipFile:
            continue
        out.append({"name": p.name, "time": when.strftime("%Y-%m-%d %H:%M"),
                    "kind": {"-manual": "手動", "-restore": "還原前自動備份"}.get(m.group(3) or "", "每日"),
                    "size": p.stat().st_size,
                    "solutions": sum(1 for n in names if n.startswith("solutions/")),
                    "hasRecords": "data/records.json" in names})
    return out


def _safe(arc: str) -> bool:
    if arc.startswith(("/", "\\")) or ".." in Path(arc).parts or ":" in arc:
        return False
    if arc.startswith("data/"):
        return arc[5:] in DATA_FILES
    return arc.startswith("solutions/")


def restore(root: Path, name: str) -> dict:
    """還原某一份快照。還原前先把現狀再備份一次，所以還原錯了也能退回來。"""
    if not NAME_RE.match(name or ""):
        raise ValueError("沒有這份備份")
    src = backup_dir(root) / name
    if not src.is_file():
        raise ValueError("沒有這份備份")
    before = snapshot(root, "restore")
    root = Path(root)
    restored = 0
    with zipfile.ZipFile(src) as z:
        for info in z.infolist():
            if info.is_dir() or not _safe(info.filename):
                continue
            dest = root / info.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".restoring")
            with z.open(info) as fin, open(tmp, "wb") as fout:
                fout.write(fin.read())
            tmp.replace(dest)
            restored += 1
    return {"restored": restored, "safety": before.name if before else None}
