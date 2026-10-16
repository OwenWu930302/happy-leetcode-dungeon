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

import atexit
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


def _local_json(port, path, method="GET"):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 本機連線不走代理
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
    with opener.open(req, timeout=3) as r:
        return json.loads(r.read().decode("utf-8"))


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
# 共用：開啟（或接上已經開著的）專用瀏覽器
# ---------------------------------------------------------------------------
class BrowserWindow:
    """專用設定檔的 Edge/Chrome。同一個設定檔只會有一個瀏覽器在跑，已經開著就直接接上。"""

    def __init__(self, profile_dir: Path):
        self.profile_dir = Path(profile_dir)
        self.proc = None

    def port(self):
        """讀 Chromium 寫在設定檔裡的 DevToolsActivePort，確認還連得上。"""
        f = self.profile_dir / "DevToolsActivePort"
        try:
            port = int(f.read_text().split()[0])
            _local_json(port, "/json/version")
            return port
        except (OSError, ValueError, IndexError):
            return None

    def alive(self):
        return self.port() is not None

    def open(self, url, size="900,760", hidden=False):
        """確保瀏覽器開著並有一個分頁在 url。回傳 (port, target_id)。

        hidden=True 時把視窗開在螢幕外面（不是無頭模式，對網站來說就是一般的瀏覽器），
        需要使用者操作時再用 set_visible() 叫出來。
        """
        port = self.port()
        if port:
            t = _local_json(port, "/json/new?" + url, method="PUT")
            return port, t.get("id")
        exe = find_browser()
        if not exe:
            raise RuntimeError("找不到 Edge 或 Chrome。")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            (self.profile_dir / "DevToolsActivePort").unlink()
        except OSError:
            pass
        args = [exe, f"--user-data-dir={self.profile_dir}", "--remote-debugging-port=0",
                "--remote-debugging-address=127.0.0.1", "--no-first-run", "--no-default-browser-check",
                "--disable-features=Translate", f"--window-size={size}", f"--app={url}"]
        if hidden:
            args.insert(-1, "--window-position=-32000,-32000")
        extra = os.environ.get("LCD_BROWSER_ARGS")
        if extra:
            args[1:1] = extra.split()
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline:
            port = self.port()
            if port:
                pages = [t for t in _local_json(port, "/json/list") if t.get("type") == "page"]
                return port, (pages[0]["id"] if pages else None)
            if self.proc.poll() is not None:
                raise RuntimeError("瀏覽器視窗沒有開起來。")
            time.sleep(0.3)
        raise RuntimeError("等不到瀏覽器視窗回應。")

    def browser_ws(self, port):
        return MiniWS(_local_json(port, "/json/version")["webSocketDebuggerUrl"])

    def set_visible(self, port, target_id, visible, size=(560, 720)):
        """把分頁所在的視窗移到螢幕中間（visible）或螢幕外（hidden）。失敗就算了，不影響流程。"""
        if not target_id:
            return
        ws = None
        try:
            ws = self.browser_ws(port)
            wid = ws.call("Browser.getWindowForTarget", {"targetId": target_id})["windowId"]
            ws.call("Browser.setWindowBounds", {"windowId": wid, "bounds": {"windowState": "normal"}})
            if visible:
                bounds = {"left": 160, "top": 90, "width": size[0], "height": size[1]}
            else:
                bounds = {"left": -32000, "top": -32000}
            ws.call("Browser.setWindowBounds", {"windowId": wid, "bounds": bounds})
            if visible:
                ws.call("Target.activateTarget", {"targetId": target_id})
        except Exception:  # noqa: BLE001
            pass
        finally:
            if ws:
                ws.close()

    def close_browser(self):
        port = self.port()
        if not port:
            return
        try:
            ws = self.browser_ws(port)
            ws.call("Browser.close")
            ws.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# 登入流程（在背景執行緒跑，前端用 status() 輪詢）
# ---------------------------------------------------------------------------
class BrowserLogin:
    def __init__(self, profile_dir: Path, verify):
        """verify(session, csrftoken) -> (username, avatar)；還沒登入時丟 ValueError。"""
        self.win = BrowserWindow(profile_dir)
        self.verify = verify
        self.lock = threading.Lock()
        self.state = {"state": "idle"}
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
        threading.Thread(target=self._run, args=(on_success,), daemon=True).start()
        return self.status()

    def cancel(self):
        self.cancelled = True
        self._set(state="idle")

    def _run(self, on_success):
        ws = None
        try:
            port, target = self.win.open(LOGIN_URL, size="520,760")
            self.win.set_visible(port, target, True, size=(520, 760))
            ws = self.win.browser_ws(port)
            deadline = time.time() + TIMEOUT
            last_session = None
            net_errors = 0
            while time.time() < deadline:
                if self.cancelled:
                    return
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
                        try:  # 只關登入分頁；之後代送提交還會用到這個瀏覽器
                            if target:
                                ws.call("Target.closeTarget", {"targetId": target})
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


# ---------------------------------------------------------------------------
# 瀏覽器代送：LeetCode 的防火牆（Cloudflare）要求真人驗證時，改從真正的瀏覽器送出
# ---------------------------------------------------------------------------
FETCH_JS = r"""
(async () => {
  const csrf = (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/) || [])[1] || "";
  const opt = { method: %(method)s, credentials: "include", referrer: %(referer)s,
                headers: { "content-type": "application/json", "x-csrftoken": csrf } };
  if (%(body)s !== null) opt.body = %(body)s;
  const r = await fetch(%(path)s, opt);
  return { status: r.status, text: await r.text(), mitigated: r.headers.get("cf-mitigated") || "" };
})()
"""


class BrowserRelay:
    """在專用瀏覽器的 leetcode.com 分頁裡執行 fetch。

    請求是由真正的瀏覽器送出（同樣的登入 cookie、同樣的瀏覽器特徵），所以 Cloudflare 會正常放行。
    視窗平常開在螢幕外，玩家只看得到遊戲；Cloudflare 真的要求點「我是真人」時，
    視窗才會跳到螢幕中間讓玩家自己點，點完再藏回去。程式不會代替人通過驗證。
    """

    CHALLENGE_SHOW_AFTER = 5  # 驗證頁停留超過幾秒就把視窗叫出來

    def __init__(self, profile_dir: Path, base="https://leetcode.com"):
        self.win = BrowserWindow(profile_dir)
        self.base = base.rstrip("/")
        self.page = None  # MiniWS 連到 leetcode 分頁
        self.target = None
        self.port = None
        self.lock = threading.RLock()
        self.visible = False
        self.needs_user = False
        self.launched = False

    # ---- 狀態（給遊戲畫面顯示「請在視窗裡完成驗證」）----
    def status(self):
        return {"needsUser": self.needs_user, "ready": self.page is not None}

    def _eval(self, expr, timeout=60):
        self.page.sock.settimeout(timeout)
        res = self.page.call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
        if res.get("exceptionDetails"):
            raise RuntimeError("瀏覽器裡的請求失敗：" + json.dumps(res["exceptionDetails"].get("exception", {}).get("description", ""))[:200])
        return res.get("result", {}).get("value")

    def _show(self, on):
        if on != self.visible:
            self.win.set_visible(self.port, self.target, on)
            self.visible = on

    def _connect(self, url):
        if self.page:
            try:
                origin = self._eval("location.origin", timeout=5)
                if origin == self.base:
                    return
            except Exception:  # noqa: BLE001  分頁被關掉了，重新開
                pass
            self.page.close()
            self.page = None
        port = self.win.port()
        existing = []
        if port:  # 瀏覽器已經開著：優先重用已經在 LeetCode 上的分頁，不要一直開新分頁
            existing = [t for t in _local_json(port, "/json/list")
                        if t.get("type") == "page" and t.get("url", "").startswith(self.base)]
        if existing:
            target = existing[0]["id"]
        else:
            was_running = port is not None
            port, target = self.win.open(url, hidden=True)
            if not was_running and not self.launched:
                self.launched = True
                atexit.register(self.win.close_browser)  # 遊戲關掉時一起收掉藏起來的瀏覽器
            self.visible = False
        pages = [t for t in _local_json(port, "/json/list") if t.get("type") == "page"]
        page = next((t for t in pages if t.get("id") == target), None) or next(
            (t for t in pages if t.get("url", "").startswith(self.base)), None) or (pages[0] if pages else None)
        if not page:
            raise RuntimeError("找不到 LeetCode 分頁。")
        self.port = port
        self.target = page["id"]
        self.page = MiniWS(page["webSocketDebuggerUrl"], timeout=60)

    def _wait_ready(self, timeout):
        """等頁面載完、而且不在 Cloudflare 的驗證頁上。驗證卡太久就把視窗叫出來給玩家點。"""
        start = time.time()
        deadline = start + timeout
        try:
            while time.time() < deadline:
                try:
                    st = self._eval("[location.origin, document.readyState, document.title].join('|')", timeout=10)
                except (RuntimeError, ConnectionError, OSError, socket.timeout):
                    st = ""
                origin, ready, title = (st.split("|", 2) + ["", "", ""])[:3]
                challenged = "just a moment" in title.lower()
                if origin == self.base and ready == "complete" and not challenged:
                    return True
                if challenged and time.time() - start > self.CHALLENGE_SHOW_AFTER:
                    self.needs_user = True
                    self._show(True)
                time.sleep(1.0)
            return False
        finally:
            if self.needs_user:
                self.needs_user = False
                self._show(False)

    def warm(self, path="/problemset/"):
        """背景先把瀏覽器和 LeetCode 分頁準備好，按出招時就不用等。"""
        def run():
            try:
                with self.lock:
                    self._connect(self.base + path)
                    self._wait_ready(40)
            except Exception:  # noqa: BLE001
                pass
        threading.Thread(target=run, daemon=True).start()

    def request(self, method, path, payload=None, referer=None, wait=180):
        """回傳 (狀態碼, 內容文字, cf-mitigated)。"""
        with self.lock:
            url = self.base + (referer or "/problemset/")
            self._connect(url)
            if not self._wait_ready(wait):
                raise SystemExit("❌ LeetCode 要求真人驗證，但還沒完成。請在跳出的 LeetCode 視窗裡點一下驗證，再出招一次。")
            expr = FETCH_JS % {
                "method": json.dumps(method), "referer": json.dumps(url), "path": json.dumps(path),
                "body": json.dumps(json.dumps(payload)) if payload is not None else "null",
            }
            out = self._eval(expr, timeout=60) or {}
            if out.get("mitigated") == "challenge":
                # 連瀏覽器也被要求驗證：重新載入頁面讓驗證出現，玩家點完後再送一次
                self.page.call("Page.navigate", {"url": url})
                time.sleep(1.5)
                if not self._wait_ready(wait):
                    raise SystemExit("❌ LeetCode 要求真人驗證，但還沒完成。請在跳出的 LeetCode 視窗裡點一下驗證，再出招一次。")
                out = self._eval(expr, timeout=60) or {}
            return out.get("status", 0), out.get("text", ""), out.get("mitigated", "")
