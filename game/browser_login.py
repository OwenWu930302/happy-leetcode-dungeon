# -*- coding: utf-8 -*-
"""
用瀏覽器一鍵登入 LeetCode
=========================

LeetCode 沒有給第三方程式用的官方登入（OAuth），所以我們這樣做：

1. 用你電腦上的 Edge 或 Chrome 開一個「獨立的登入視窗」（專用的瀏覽器設定檔，
   跟你平常用的瀏覽器分開），載入真正的 leetcode.com 登入頁。
2. 你在視窗裡正常登入（email、GitHub、Google 都可以）。密碼是直接輸入給 LeetCode，
   這支程式完全碰不到。
3. 程式透過瀏覽器內建的除錯介面（Chrome DevTools Protocol，只聽 127.0.0.1）
   讀取 leetcode.com 的兩個 cookie：LEETCODE_SESSION 與 csrftoken，然後關掉視窗。

登入視窗的設定檔存在工作區的 browser-profile/，所以 cookie 過期時再按一次，
通常 LeetCode 還記得你，連密碼都不用再打。

不需要任何額外套件：WebSocket 用標準函式庫自己實作（只用到最基本的文字訊框）。
"""

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

LOGIN_URL = os.environ.get("LCD_LOGIN_URL", "https://leetcode.com/accounts/login/")
COOKIE_DOMAIN = os.environ.get("LCD_LOGIN_DOMAIN", "leetcode.com")
TIMEOUT = 600  # 最多等 10 分鐘


# ---------------------------------------------------------------------------
# 找瀏覽器
# ---------------------------------------------------------------------------
def find_browser():
    env = os.environ.get("LCD_BROWSER")
    if env and Path(env).exists():
        return env
    cands = []
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
            if base:
                cands += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                          Path(base) / "Google/Chrome/Application/chrome.exe",
                          Path(base) / "BraveSoftware/Brave-Browser/Application/brave.exe"]
    elif sys.platform == "darwin":
        cands += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                  Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
                  Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"),
                  Path("/Applications/Chromium.app/Contents/MacOS/Chromium")]
    for c in cands:
        if c.exists():
            return str(c)
    for name in ("microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser"):
        p = shutil.which(name)
        if p:
            return p
    return None


# ---------------------------------------------------------------------------
# 最小 WebSocket 用戶端（只為了跟本機瀏覽器講 DevTools Protocol）
# ---------------------------------------------------------------------------
class MiniWS:
    def __init__(self, url, timeout=10):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        path = u.path + (("?" + u.query) if u.query else "")
        req = (f"GET {path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("瀏覽器拒絕了連線")
            resp += chunk
        if b" 101 " not in resp.split(b"\r\n", 1)[0]:
            raise ConnectionError("瀏覽器拒絕了連線：" + resp.split(b"\r\n", 1)[0].decode(errors="replace"))
        self.buf = resp.split(b"\r\n\r\n", 1)[1]
        self.next_id = 0

    def _recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("瀏覽器關閉了連線")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text):
        data = text.encode("utf-8")
        head = bytearray([0x81])
        n = len(data)
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self):
        parts = []
        while True:
            b1, b2 = self._recv_exact(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b2 & 0x80 else None
            payload = self._recv_exact(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:
                raise ConnectionError("瀏覽器關閉了連線")
            if op in (0x9, 0xA):  # ping / pong：忽略
                continue
            parts.append(payload)
            if b1 & 0x80:
                return b"".join(parts).decode("utf-8")

    def call(self, method, params=None):
        self.next_id += 1
        mid = self.next_id
        self.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(msg["error"].get("message", "DevTools 錯誤"))
                return msg.get("result", {})

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


def _local_json(port, path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 本機連線不走代理
    with opener.open(f"http://127.0.0.1:{port}{path}", timeout=3) as r:
        return json.loads(r.read().decode("utf-8"))


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def pick_cookies(cookies, domain=COOKIE_DOMAIN):
    """從 DevTools 回傳的 cookie 清單挑出 LeetCode 的兩個 cookie。"""
    got = {}
    for c in cookies:
        d = (c.get("domain") or "").lstrip(".")
        if d == domain or d.endswith("." + domain):
            if c.get("name") in ("LEETCODE_SESSION", "csrftoken") and c.get("value"):
                got[c["name"]] = c["value"]
    return got


# ---------------------------------------------------------------------------
# 登入流程（在背景執行緒跑，前端用 status() 輪詢）
# ---------------------------------------------------------------------------
class BrowserLogin:
    def __init__(self, profile_dir: Path, verify):
        """verify(session, csrftoken) -> (username, avatar)；還沒登入時丟 ValueError。"""
        self.profile_dir = Path(profile_dir)
        self.verify = verify
        self.lock = threading.Lock()
        self.state = {"state": "idle"}
        self.proc = None
        self.cancelled = False

    def status(self):
        with self.lock:
            return dict(self.state)

    def _set(self, **kw):
        with self.lock:
            self.state = kw

    def start(self, on_success):
        with self.lock:
            if self.state.get("state") == "waiting":
                return dict(self.state)
        exe = find_browser()
        if not exe:
            self._set(state="error", error="找不到 Edge 或 Chrome。請改用下方「手動貼 cookie」登入。")
            return self.status()
        self.cancelled = False
        self._set(state="waiting", browser=Path(exe).stem, message="已開啟登入視窗，請在視窗裡登入 LeetCode")
        threading.Thread(target=self._run, args=(exe, on_success), daemon=True).start()
        return self.status()

    def cancel(self):
        self.cancelled = True
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self._set(state="idle")

    def _run(self, exe, on_success):
        port = _free_port()
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        args = [exe, f"--user-data-dir={self.profile_dir}", f"--remote-debugging-port={port}",
                "--remote-debugging-address=127.0.0.1", "--no-first-run", "--no-default-browser-check",
                "--disable-features=Translate", "--window-size=520,760", f"--app={LOGIN_URL}"]
        extra = os.environ.get("LCD_BROWSER_ARGS")
        if extra:
            args[1:1] = extra.split()
        ws = None
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            deadline = time.time() + TIMEOUT
            # 等瀏覽器的除錯介面起來
            while time.time() < deadline:
                if self.cancelled:
                    return
                if self.proc.poll() is not None:
                    raise RuntimeError("登入視窗沒有開起來。如果 Edge/Chrome 已經開著同一個設定檔，請先關掉再試。")
                try:
                    ws = MiniWS(_local_json(port, "/json/version")["webSocketDebuggerUrl"])
                    break
                except (OSError, ValueError, KeyError):
                    time.sleep(0.4)
            if ws is None:
                raise RuntimeError("等不到登入視窗回應")
            last_session = None
            net_errors = 0
            while time.time() < deadline:
                if self.cancelled:
                    return
                if self.proc.poll() is not None:
                    raise RuntimeError("登入視窗被關掉了，還沒拿到登入資訊。")
                try:
                    cookies = ws.call("Storage.getCookies").get("cookies", [])
                except (ConnectionError, OSError):
                    raise RuntimeError("登入視窗被關掉了，還沒拿到登入資訊。")
                got = pick_cookies(cookies)
                sess, csrf = got.get("LEETCODE_SESSION"), got.get("csrftoken")
                if sess and csrf and sess != last_session:
                    try:
                        user, avatar = self.verify(sess, csrf)
                        last_session = sess
                    except ValueError:
                        user = None  # cookie 還是未登入狀態，繼續等
                        last_session = sess
                    except Exception as e:  # noqa: BLE001  網路一時不穩：下一輪再試
                        user = None
                        net_errors += 1
                        if net_errors >= 8:
                            raise RuntimeError(f"一直連不到 LeetCode 確認登入狀態：{e}")
                        self._set(state="waiting", browser=self.state.get("browser"),
                                  message="已經拿到登入資訊，正在跟 LeetCode 確認中…")
                    if user:
                        on_success(sess, csrf, user, avatar)
                        self._set(state="ok", user=user)
                        try:
                            ws.call("Browser.close")
                        except Exception:  # noqa: BLE001
                            pass
                        return
                time.sleep(1.0)
            raise RuntimeError("等太久了（10 分鐘），請再按一次登入。")
        except Exception as e:  # noqa: BLE001
            if not self.cancelled:
                self._set(state="error", error=str(e))
        finally:
            if ws:
                ws.close()
            if self.proc and self.proc.poll() is None and self.status().get("state") != "ok":
                # 失敗時不強制關掉視窗，讓使用者自己關；成功時已經用 Browser.close 關了
                pass
