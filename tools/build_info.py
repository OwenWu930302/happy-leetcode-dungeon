"""打包前記下這次建置的資訊（commit、時間），讓遊戲能判斷有沒有新版本。

用法：python tools/build_info.py [commit] [標籤]（沒給 commit 就問 git）
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sha = sys.argv[1] if len(sys.argv) > 1 else ""
if not sha:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        sha = ""
info = {"sha": sha, "ref": sys.argv[2] if len(sys.argv) > 2 else "",
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
out = Path(__file__).resolve().parents[1] / "game" / "build_info.json"
out.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
print("build info:", info)
