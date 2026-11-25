"""送出到 LeetCode 的流程：瀏覽器代送逾時、被 Cloudflare 擋時，要快速給出明確的錯誤，不能卡住或當掉。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import lc  # noqa: E402
from game.browser_login import NeedsUser  # noqa: E402


class FakeResp:
    def __init__(self, status=200, body=None, challenge=False):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.text = "<title>Just a moment...</title>" if challenge else json.dumps(body or {})
        self.headers = lc.requests.structures.CaseInsensitiveDict({"cf-mitigated": "challenge"} if challenge else {})
        self.url = "https://leetcode.com/x"
        self.request = type("Req", (), {"method": "POST"})()

    def json(self):
        return json.loads(self.text)


class FakeSession:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.calls = resp, exc, 0

    def request(self, *a, **k):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.resp


class FakeRelay:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, 0

    def request(self, *a, **k):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.result


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.saved = (lc.get_relay, lc.transport, lc.DATA_DIR, lc._RELAY_UNTIL)
        lc.DATA_DIR = Path(tempfile.mkdtemp())
        lc.transport = lambda: "browser"
        lc._RELAY_UNTIL = 0

    def tearDown(self):
        lc.get_relay, lc.transport, lc.DATA_DIR, lc._RELAY_UNTIL = self.saved

    def use(self, relay):
        lc.get_relay = lambda: relay

    def test_relay_success(self):
        self.use(FakeRelay(result=(200, '{"submission_id": 7}', "")))
        self.assertEqual(lc.lc_request(FakeSession(), "POST", "/p/", {}, action="提交")["submission_id"], 7)

    def test_relay_timeout_then_direct_ok(self):
        relay = FakeRelay(exc=TimeoutError("timed out"))
        self.use(relay)
        out = lc.lc_request(FakeSession(FakeResp(body={"submission_id": 8})), "POST", "/p/", {}, action="提交")
        self.assertEqual(out["submission_id"], 8)

    def test_relay_timeout_and_direct_challenged_gives_clear_error_without_waiting_twice(self):
        relay = FakeRelay(exc=TimeoutError("timed out"))
        self.use(relay)
        with self.assertRaises(lc.LcError) as cm:
            lc.lc_request(FakeSession(FakeResp(403, challenge=True)), "POST", "/p/", {}, action="提交")
        self.assertEqual(cm.exception.kind, "cloudflare")
        self.assertIn("改到官網出招", str(cm.exception))
        self.assertEqual(relay.calls, 1)  # 不會再讓瀏覽器等第二次

    def test_unfinished_human_check_is_blocked_not_a_crash(self):
        relay = FakeRelay(exc=NeedsUser())
        self.use(relay)
        with self.assertRaises(lc.LcError) as cm:
            lc.lc_request(FakeSession(FakeResp(403, challenge=True)), "POST", "/p/", {}, action="提交")
        self.assertEqual(cm.exception.kind, "cloudflare")

    def test_blocked_while_polling_says_already_submitted(self):
        self.use(FakeRelay(exc=TimeoutError("timed out")))
        with self.assertRaises(lc.LcError) as cm:
            lc.lc_request(FakeSession(FakeResp(403, challenge=True)), "GET", "/check/", action="取得判題結果")
        self.assertEqual(cm.exception.kind, "timeout")
        self.assertIn("同步官網進度", str(cm.exception))

    def test_network_failure_is_reported(self):
        lc.transport = lambda: "direct"
        self.use(None)
        with self.assertRaises(lc.LcError) as cm:
            lc.lc_request(FakeSession(exc=lc.requests.exceptions.ReadTimeout("slow")), "POST", "/p/", {}, action="提交")
        self.assertEqual(cm.exception.kind, "network")


if __name__ == "__main__":
    unittest.main()
