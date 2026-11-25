"""登入小幫手（瀏覽器擴充功能）送來的登入：只收擴充功能、先確認帳號、一樣的就不重複處理。"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lc  # noqa: E402
from game import server  # noqa: E402

GOOD = {"session": "S" * 40, "csrftoken": "C" * 20}
EXT = "chrome-extension://abcdefghijklmnop"


class ExtLoginTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.saved = (lc.CONFIG_PATH, server.PROFILE_PATH, server.verify_login)
        lc.CONFIG_PATH = self.tmp / "config.json"
        server.PROFILE_PATH = self.tmp / "profile.json"
        self.calls = []

        def verify(sess, csrf):
            self.calls.append(sess)
            if sess.startswith("BAD"):
                raise ValueError("LeetCode 說這組 cookie 沒有登入")
            return "owen", None
        server.verify_login = verify

    def tearDown(self):
        lc.CONFIG_PATH, server.PROFILE_PATH, server.verify_login = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_only_extensions_are_accepted(self):
        for origin in (None, "", "https://evil.example", "http://127.0.0.1:8765"):
            code, out = server.ext_login(origin, GOOD)
            self.assertEqual(code, 403, origin)
            self.assertEqual(out["app"], "LeetCodeDungeon")
        self.assertFalse(lc.CONFIG_PATH.exists())

    def test_saves_verified_login_once(self):
        code, out = server.ext_login(EXT, GOOD)
        self.assertEqual((code, out["user"]), (200, "owen"))
        cfg = lc.load_config()
        self.assertEqual((cfg["session"], cfg["csrftoken"]), (GOOD["session"], GOOD["csrftoken"]))
        code, out = server.ext_login(EXT, GOOD)  # 一樣的 cookie：不再問 LeetCode
        self.assertTrue(out.get("same"))
        self.assertEqual(len(self.calls), 1)

    def test_logged_out_cookie_is_rejected(self):
        code, out = server.ext_login(EXT, {"session": "BAD" + "x" * 30, "csrftoken": "C" * 20})
        self.assertEqual(code, 400)
        self.assertFalse(lc.CONFIG_PATH.exists())

    def test_incomplete_cookie_is_rejected(self):
        self.assertEqual(server.ext_login(EXT, {"session": "short", "csrftoken": ""})[0], 400)


if __name__ == "__main__":
    unittest.main()
