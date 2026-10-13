# -*- coding: utf-8 -*-
"""
EXE 的進入點
============

- 直接雙擊 LeetCodeDungeon.exe → 啟動遊戲並打開瀏覽器
- 在終端機加參數 → 跟 python lc.py 一樣，例如：
      LeetCodeDungeon.exe submit 0001-two-sum
      LeetCodeDungeon.exe sync
"""

import os
import sys
import traceback

if os.name == "nt":  # 讓 Windows 主控台正確顯示中文與 emoji
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleTitleW("LeetCode 演算法地城")
    except Exception:  # noqa: BLE001
        pass

import lc
from game import server  # noqa: F401  讓 PyInstaller 一定把遊戲模組打包進去


def run():
    if len(sys.argv) > 1:
        lc.main()
        return
    lc.ensure_home()
    print("=" * 56)
    print("  LeetCode 演算法地城 · 開心每日刷題")
    print("=" * 56)
    server.serve()


if __name__ == "__main__":
    try:
        run()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        if getattr(sys, "frozen", False) and len(sys.argv) == 1:
            input("\n發生錯誤了，按 Enter 關閉視窗…")
        sys.exit(1)
