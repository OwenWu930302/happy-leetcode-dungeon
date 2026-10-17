"""本地錯誤報告：遊戲出錯時寫進工作區的 logs/game.log；需要回報時，產生一段可以直接貼到 GitHub Issue 的文字。

報告只在你的電腦上產生，不會自動上傳。登入 cookie、LeetCode 帳號名稱、電腦路徑都會先遮掉。
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import re
import sys
from pathlib import Path

LOG = logging.getLogger("lcd")
_PATH = None


def setup(root: Path):
    global _PATH
    d = Path(root) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    _PATH = d / "game.log"
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in LOG.handlers):
        h = logging.handlers.RotatingFileHandler(_PATH, maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        LOG.addHandler(h)
        LOG.setLevel(logging.INFO)


def mask(text: str, secrets=(), names=(), paths=()) -> str:
    for s in secrets:
        if s and len(s) >= 6:
            text = text.replace(s, "<已遮蔽>")
    for n in names:
        if n and len(n) >= 2:
            text = re.sub(re.escape(n), "<帳號>", text, flags=re.I)
    for p, label in sorted(paths, key=lambda x: -len(x[0] or "")):
        if p:
            text = text.replace(p, label).replace(p.replace("\\", "/"), label)
    text = re.sub(r"eyJ[\w-]{10,}\.[\w-]{10,}\.[\w-]{5,}", "<已遮蔽>", text)          # JWT
    text = re.sub(r"(?i)(csrftoken|LEETCODE_SESSION|session)([\"'=: ]+)[\w.-]{16,}", r"\1\2<已遮蔽>", text)
    return text


def tail(n=60) -> list[str]:
    if not _PATH or not Path(_PATH).exists():
        return []
    try:
        return Path(_PATH).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def build(version: str, extra: str = "", secrets=(), names=(), paths=()) -> str:
    lines = [
        "### 錯誤報告（LeetCode 演算法地城）",
        f"- 版本：{version}",
        f"- 系統：{platform.platform()}",
        f"- Python：{platform.python_version()}{'（EXE）' if getattr(sys, 'frozen', False) else ''}",
        f"- 語系：{os.environ.get('LANG') or os.environ.get('LC_ALL') or '—'}",
        "",
    ]
    if extra:
        lines += ["**剛剛的錯誤**", "```", extra.strip()[:4000], "```", ""]
    log = tail()
    if log:
        lines += ["**最近的紀錄**", "```", *log, "```"]
    return mask("\n".join(lines), secrets, names, paths)
