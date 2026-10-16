# -*- coding: utf-8 -*-
"""
本機遊戲伺服器：python lc.py game
================================

只聽 127.0.0.1，不會對外開放。瀏覽器（或 VS Code 的 Simple Browser）打開
http://localhost:8765 就是遊戲畫面；畫面上的按鈕會呼叫這裡的 /api/*，
再轉去用 lc.py 原本的功能（建檔、試跑、提交、同步）。

遊戲存檔：data/game.json
"""

import base64
import contextlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import lc  # noqa: E402
from game import browser_login, engine, rogue  # noqa: E402

STATIC = lc.APP_DIR / "game" / "static"
SAVE_PATH = lc.DATA_DIR / "game.json"
PROFILE_PATH = lc.DATA_DIR / "profile.json"
ASSET_DIR = lc.ROOT / "assets"
MAX_UPLOAD = 6 * 1024 * 1024
IMAGE_MAGIC = {b"\x89PNG": "png", b"\xff\xd8\xff": "jpg", b"GIF8": "gif", b"RIFF": "webp"}
BACKGROUNDS = ["dungeon", "starry", "sakura", "abyss", "ember", "forest", "plain"]
COMPANIONS = {c["id"]: c for c in json.loads((STATIC / "companions.json").read_text(encoding="utf-8"))["companions"]}


def persona_of(prof):
    """目前的看板娘個性：有指定就用指定的，否則跟著頭像；上傳頭像時預設露緹。"""
    pid = prof.get("persona")
    if pid in COMPANIONS:
        return pid
    return prof.get("avatar") if prof.get("avatar") in COMPANIONS else "p0"


def strategy(prof=None):
    st = dict(COMPANIONS[persona_of(prof or load_profile())]["strategy"])
    st.setdefault("mode", "balanced")
    st.setdefault("offset", 80)
    st.setdefault("width", 180)
    return st


PROFILE_DEFAULT = {"name": "", "companion": "露緹", "avatar": "p0", "bg": "dungeon", "dim": 0.55,
                   "onboarded": False, "lcUser": None, "lcAvatar": None, "uploads": {}}
TOKEN = secrets.token_urlsafe(16)
LOCK = threading.RLock()
BROWSER = None  # 在 verify_login 定義之後建立

LEVEL_TITLES = [(1, "見習獵題人"), (4, "銅徽獵題人"), (8, "銀徽獵題人"), (12, "金徽獵題人"),
                (18, "演算法術士"), (25, "傳奇獵題人")]


# ---------------------------------------------------------------------------
# 存檔
# ---------------------------------------------------------------------------
def load_save():
    save = lc.load_json(SAVE_PATH, None) or rogue.new_save()
    base = rogue.new_save()
    for k, v in base["meta"].items():
        save["meta"].setdefault(k, v)
    save.setdefault("run", None)
    return save


def write_save(save):
    lc.save_json(SAVE_PATH, save)


def load_profile():
    prof = dict(PROFILE_DEFAULT)
    prof.update(lc.load_json(PROFILE_PATH, {}) or {})
    return prof


def save_profile(prof):
    lc.save_json(PROFILE_PATH, prof)


def logged_in(cfg):
    sess = cfg.get("session") or ""
    return bool(sess and cfg.get("csrftoken") and "貼上" not in sess)


def save_login(sess, csrf, user, avatar):
    threading.Thread(target=lambda: lc.fetch_contest(user), daemon=True).start()
    with LOCK:
        cfg = lc.load_config()
        cfg.update({"session": sess, "csrftoken": csrf})
        cfg.setdefault("lang", "python3")
        lc.save_json(lc.CONFIG_PATH, cfg)
        prof = load_profile()
        prof["lcUser"], prof["lcAvatar"] = user, avatar
        if not prof["name"]:
            prof["name"] = user
        save_profile(prof)


def verify_login(session_cookie, csrftoken):
    """用 cookie 問 LeetCode「我是誰」。回傳 (username, avatar)，失敗丟 ValueError。"""
    s = lc.requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
                      "Origin": lc.BASE, "Referer": lc.BASE + "/", "x-csrftoken": csrftoken})
    s.cookies.set("LEETCODE_SESSION", session_cookie, domain="leetcode.com")
    s.cookies.set("csrftoken", csrftoken, domain="leetcode.com")
    try:
        who = lc.graphql(s, "query { userStatus { username isSignedIn avatar } }", {})["userStatus"]
    except RuntimeError:
        who = lc.graphql(s, "query { userStatus { username isSignedIn } }", {})["userStatus"]
    if not who or not who.get("isSignedIn"):
        raise ValueError("LeetCode 說這組 cookie 沒有登入，可能複製錯了或已過期，重新複製一次試試。")
    return who.get("username"), who.get("avatar")


def load_world():
    problems = lc.load_json(lc.PROBLEMS_PATH, [])
    records = lc.load_json(lc.RECORDS_PATH, {})
    return problems, records


def context(problems, records):
    if not engine.RATINGS:
        engine.set_ratings(lc.load_ratings())
    tree = engine.build_tree(problems, records)
    power = engine.compute_power(problems, records, contest=lc.load_json(lc.DATA_DIR / "contest.json", None))
    st = strategy()
    return {"problems": problems, "records": records, "tree": tree, "power": power,
            "mode": st["mode"], "strategy": st}


# ---------------------------------------------------------------------------
# 等級
# ---------------------------------------------------------------------------
def xp_for(level):
    return 25 * level * (level - 1)


def level_info(xp):
    L = 1
    while xp_for(L + 1) <= xp:
        L += 1
    title = [t for lv, t in LEVEL_TITLES if L >= lv][-1]
    return {"level": L, "title": title, "xp": xp, "base": xp_for(L), "next": xp_for(L + 1)}


# ---------------------------------------------------------------------------
# VS Code
# ---------------------------------------------------------------------------
BROWSER = browser_login.BrowserLogin(lc.ROOT / "browser-profile", verify_login)


def code_line(path: Path) -> int:
    """游標要停的行：程式碼標記之後，最後一個函式宣告的下一行（Python、C++、Java… 都適用）。"""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 1
    start = next((i for i, l in enumerate(lines) if lc.MARK in l), 0)
    sigs = [i for i, l in enumerate(lines)
            if i > start and "(" in l and l.rstrip().endswith((":", "{"))
            and not l.strip().startswith(("class", "struct", "impl", "if", "for", "while"))]
    return (sigs[-1] + 2) if sigs else start + 2


def open_in_editor(path: Path, line=None):
    line = line or (code_line(path) if path.is_file() else None)
    target = f"{path}:{line}" if line else str(path)
    code = shutil.which("code") or shutil.which("code.cmd")
    if code:
        try:
            args = [code, "-r", "-g", target] if line else [code, target]
            subprocess.Popen(args, cwd=str(lc.ROOT),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return "vscode"
        except OSError:
            pass
    uri = "vscode://file/" + str(path).replace("\\", "/") + (f":{line}" if line else "")
    try:
        if os.name == "nt":
            os.startfile(uri)  # type: ignore[attr-defined]
        else:
            webbrowser.open(uri)
        return "uri"
    except OSError:
        return "none"


# ---------------------------------------------------------------------------
# 組合整個畫面需要的狀態
# ---------------------------------------------------------------------------
def problem_brief(p, records):
    r = records.get(p["slug"]) or {}
    return {
        "slug": p["slug"], "id": p["id"], "title": p["title"], "difficulty": p["difficulty"],
        "acRate": p.get("acRate"), "tags": p.get("tags", []), "rating": engine.problem_rating(p),
        "solved": bool(r.get("solved")), "attempts": len(r.get("attempts", [])),
        "file": lc.solution_path(p).exists(),
    }


def build_state(save, events=None):
    problems, records = load_world()
    ctx = context(problems, records)
    by_slug = {p["slug"]: p for p in problems}

    events = list(events or [])
    events += rogue.resolve(save, records, by_slug)
    events += rogue.resolve_bounties(save, records)
    if events:
        write_save(save)

    power = ctx["power"]
    names = {n["id"]: n["name"] for n in ctx["tree"]["nodes"]}
    per_tag = [
        {"id": t, "name": names.get(t, t), **v}
        for t, v in power["per_tag"].items() if t in names
    ]
    per_tag.sort(key=lambda x: -x["events"])
    total_xp = power["xp"] + save["meta"]["bonus_xp"]

    run = save.get("run")
    run_view = None
    if run:
        run_view = dict(run)
        run_view["moves"] = rogue.moves(run)
        cur = run.get("current")
        if cur and cur.get("chosen") and cur["chosen"] in by_slug:
            run_view["chosen"] = problem_brief(by_slug[cur["chosen"]], records)

    st = ctx["strategy"]
    picks = engine.recommend(problems, records, ctx["tree"], power, k=3, seed=f"daily:{date.today()}:{st['mode']}",
                             mode=st["mode"], offset=st["offset"], width=st["width"])
    cfg = lc.load_config()
    solved_recent = sorted(
        [{"slug": s, "id": r.get("id"), "title": r.get("title"), "difficulty": r.get("difficulty"),
          "at": r.get("solved_at") or ""} for s, r in records.items() if r.get("solved")],
        key=lambda x: x["at"], reverse=True)[:8]

    return {
        "player": {**level_info(total_xp), **{k: power[k] for k in (
            "rating", "estimate", "official", "contest", "rank", "tier", "nextRank", "needRank", "power",
            "hardest", "ratedBy", "accuracy", "events", "wins", "solved")},
                   "shards": save["meta"]["shards"]},
        "tree": ctx["tree"],
        "perTag": per_tag,
        "run": run_view,
        "meta": {"upgrades": rogue.public_upgrades(save), "history": save["meta"]["history"],
                 "bounties": save["meta"]["bounties"], "runs": save["meta"].get("runs_started", 0)},
        "relics": rogue.public_relics(),
        "nodeTypes": {k: v["name"] for k, v in rogue.NODE_TYPES.items()},
        "picks": picks,
        "recent": solved_recent,
        "library": {"total": len(problems), "playable": sum(1 for p in problems if engine.playable(p)),
                    "allDifficulties": any(p.get("difficulty") != "Easy" for p in problems)},
        "login": logged_in(cfg),
        "profile": {k: v for k, v in load_profile().items()},
        "persona": persona_of(load_profile()),
        "dayStreak": engine.day_streak(records),
        "langs": [{"id": k, "name": v[2]} for k, v in lc.LANGS.items()],
        "lang": lc.default_lang(),
        "transport": lc.transport(),
        "workspace": str(lc.ROOT),
        "frozen": lc.FROZEN,
        "browserLogin": bool(browser_login.find_browser()),
        "vscodeInstalled": (lc.ROOT / ".vscode" / "tasks.json").exists(),
        "backgrounds": BACKGROUNDS,
        "events": events,
    }


def find(slug):
    problems, _ = load_world()
    for p in problems:
        if p["slug"] == slug:
            return p
    return lc.find_problem(slug)


def captured(fn, *a, **kw):
    """執行 lc.py 的指令並把它印出來的文字收集起來。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*a, **kw)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def warm_relay():
    """玩家選題或看題時，背景先把藏起來的瀏覽器準備好，按出招時就不用等。"""
    if lc.transport() != "browser" or not logged_in(lc.load_config()):
        return
    relay = lc.get_relay()
    if relay:
        relay.warm()


def api(path, body, query):
    if path == "/api/relay/status":  # 出招時會一直拿著 LOCK，這個查詢要能同時回應
        relay = lc._RELAY
        return relay.status() if relay else {"needsUser": False, "ready": False}
    with LOCK:
        save = load_save()
        problems, records = load_world()

        if path == "/api/state":
            return build_state(save)

        if path == "/api/profile":
            prof = load_profile()
            for k in ("name", "companion"):
                if k in body:
                    prof[k] = str(body[k]).strip()[:24]
            if "avatar" in body:
                av = str(body["avatar"])
                if av == "upload" and not prof["uploads"].get("avatar"):
                    raise ValueError("還沒有上傳頭像")
                if av != "upload" and not re.fullmatch(r"p\d{1,2}", av):
                    raise ValueError("沒有這個頭像")
                prof["avatar"] = av
            if "bg" in body:
                bg = str(body["bg"])
                if bg != "upload" and bg not in BACKGROUNDS:
                    raise ValueError("沒有這個背景")
                if bg == "upload" and not prof["uploads"].get("bg"):
                    raise ValueError("還沒有上傳背景圖")
                prof["bg"] = bg
            if "dim" in body:
                prof["dim"] = max(0.0, min(0.9, float(body["dim"])))
            if "persona" in body:
                if body["persona"] not in COMPANIONS:
                    raise ValueError("沒有這位看板娘")
                prof["persona"] = body["persona"]
            if "onboarded" in body:
                prof["onboarded"] = bool(body["onboarded"])
            if "transport" in body:
                if body["transport"] not in ("browser", "direct"):
                    raise ValueError("沒有這種提交方式")
                cfg = lc.load_config()
                cfg["transport"] = body["transport"]
                lc.save_json(lc.CONFIG_PATH, cfg)
            if "lang" in body:
                if body["lang"] not in lc.LANGS:
                    raise ValueError("不支援這個語言")
                cfg = lc.load_config()
                cfg["lang"] = body["lang"]
                lc.save_json(lc.CONFIG_PATH, cfg)
            save_profile(prof)
            return build_state(save)

        if path == "/api/upload":
            kind = body.get("kind")
            if kind not in ("avatar", "bg"):
                raise ValueError("只能上傳頭像或背景")
            data = str(body.get("data", ""))
            raw = base64.b64decode(data.split(",", 1)[-1], validate=False)
            if len(raw) > MAX_UPLOAD:
                raise ValueError("圖片太大了，請小於 6 MB")
            ext = next((e for m, e in IMAGE_MAGIC.items() if raw.startswith(m)), None)
            if not ext or (ext == "webp" and raw[8:12] != b"WEBP"):
                raise ValueError("只支援 PNG、JPG、GIF、WebP 圖片")
            ASSET_DIR.mkdir(parents=True, exist_ok=True)
            for old in ASSET_DIR.glob(f"{kind}.*"):
                old.unlink()
            (ASSET_DIR / f"{kind}.{ext}").write_bytes(raw)
            prof = load_profile()
            prof["uploads"][kind] = f"{ext}?v={secrets.token_hex(4)}"
            prof["avatar" if kind == "avatar" else "bg"] = "upload"
            save_profile(prof)
            return build_state(save)

        if path == "/api/login":
            sess = str(body.get("session", "")).strip().strip('"')
            csrf = str(body.get("csrftoken", "")).strip().strip('"')
            if len(sess) < 20 or len(csrf) < 10:
                raise ValueError("兩個欄位都要貼上完整的 cookie 值")
            user, avatar = verify_login(sess, csrf)
            save_login(sess, csrf, user, avatar)
            return build_state(save, [{"kind": "login", "user": user}])

        if path == "/api/login/browser":
            return BROWSER.start(save_login)

        if path == "/api/login/status":
            return BROWSER.status()

        if path == "/api/login/cancel":
            BROWSER.cancel()
            return BROWSER.status()

        if path == "/api/logout":
            cfg = lc.load_config()
            cfg.pop("session", None)
            cfg.pop("csrftoken", None)
            lc.save_json(lc.CONFIG_PATH, cfg)
            prof = load_profile()
            prof["lcUser"], prof["lcAvatar"] = None, None
            save_profile(prof)
            return build_state(save)

        if path == "/api/workspace/open":
            how = open_in_editor(lc.ROOT)
            if how == "none" and os.name == "nt":
                os.startfile(str(lc.ROOT))  # type: ignore[attr-defined]
                how = "explorer"
            return {"opened": how, "path": str(lc.ROOT)}

        if path == "/api/vscode/install":
            f = lc.install_vscode(force=True)
            return {"file": str(f), **build_state(save)}

        if path == "/api/problem":
            slug = (query.get("slug") or [""])[0]
            p = find(slug)
            q = lc.fetch_question_detail(p["slug"])
            snippet = lc.get_python_snippet(q)
            warm_relay()
            return {
                **problem_brief(p, records), "html": q.get("content") or "",
                "examples": q.get("exampleTestcases") or "", "snippet": snippet,
                "url": f"{lc.BASE}/problems/{p['slug']}/",
                "cnUrl": f"https://leetcode.cn/problems/{p['slug']}/",
            }

        if path == "/api/open":
            p = find(body["slug"])
            fpath, created = lc.create_solution(p)
            how = open_in_editor(fpath)
            warm_relay()
            return {"file": str(fpath.relative_to(lc.ROOT)), "created": created, "opened": how}

        if path == "/api/test":
            p = find(body["slug"])
            if not lc.solution_path(p).exists():
                lc.create_solution(p)
            res = lc.run_test(p, body.get("input") or None)
            return {"result": slim(res)}

        if path == "/api/submit":
            p = find(body["slug"])
            res, ok = lc.run_submit(p)
            return {"result": slim(res), "accepted": ok, **build_state(load_save())}

        if path == "/api/sync":
            out = captured(lc.cmd_sync, type("A", (), {"all": False})())
            return {"log": out, **build_state(save)}

        if path == "/api/fetch":
            out = captured(lc.cmd_fetch, type("A", (), {"all": bool(body.get("all"))})())
            return {"log": out, **build_state(save)}

        if path == "/api/recommend":
            ctx = context(problems, records)
            st = ctx["strategy"]
            return {"items": engine.recommend(
                problems, records, ctx["tree"], ctx["power"], k=int(body.get("k", 5)),
                tag=body.get("tag"), seen=save["meta"]["ads_seen"], seed=body.get("seed"),
                mode=st["mode"], offset=st["offset"], width=st["width"])}

        if path == "/api/ad":
            ctx = context(problems, records)
            st = ctx["strategy"]
            items = engine.recommend(problems, records, ctx["tree"], ctx["power"], k=1,
                                     seen=save["meta"]["ads_seen"],
                                     exclude=set(save["meta"]["bounties"]),
                                     mode=st["mode"], offset=st["offset"], width=st["width"])
            if items:
                save["meta"]["ads_seen"] = (save["meta"]["ads_seen"] + [items[0]["slug"]])[-40:]
                write_save(save)
            return {"ad": items[0] if items else None}

        if path == "/api/bounty":
            ctx = context(problems, records)
            p = find(body["slug"])
            rec = {"slug": p["slug"], "title": p["title"], "difficulty": p["difficulty"],
                   "xp": engine.DIFF_XP.get(p["difficulty"], 10)}
            rogue.accept_bounty(save, rec, was_solved=bool((records.get(p["slug"]) or {}).get("solved")))
            write_save(save)
            fpath, _ = lc.create_solution(p)
            open_in_editor(fpath)
            return build_state(save, [{"kind": "bountyAccepted", "title": p["title"]}])

        if path.startswith("/api/run/") or path == "/api/upgrade":
            ctx = context(problems, records)
            events = []
            if path == "/api/run/start":
                if save.get("run") and save["run"]["status"] == "active":
                    raise ValueError("遠征還在進行中")
                rogue.start_run(save, persona=persona_of(load_profile()))
            elif path == "/api/run/enter":
                events = rogue.enter(save, body["key"], ctx)
            elif path == "/api/run/choose":
                p = find(body["slug"])
                fpath, _ = lc.create_solution(p)  # 先建檔，失敗就不算開戰
                rogue.choose(save, body["slug"])
                open_in_editor(fpath)
                warm_relay()
            elif path == "/api/run/reroll":
                events = rogue.reroll(save, ctx)
            elif path == "/api/run/flee":
                events = rogue.flee(save)
            elif path == "/api/run/act":
                events = rogue.act(save, body.get("action"), body.get("arg"))
            elif path == "/api/run/abandon":
                events = rogue.abandon(save)
            elif path == "/api/run/clear":
                if save.get("run") and save["run"]["status"] != "active":
                    save["run"] = None
            elif path == "/api/upgrade":
                rogue.buy_upgrade(save, body["id"])
            write_save(save)
            return build_state(save, events)

        raise LookupError("沒有這個 API")


def slim(res):
    keep = ("status_msg", "code_answer", "expected_code_answer", "compile_error", "full_compile_error",
            "runtime_error", "full_runtime_error", "total_correct", "total_testcases", "status_runtime",
            "status_memory", "last_testcase", "code_output", "expected_output", "std_output_list",
            "correct_answer", "_input")
    return {k: res.get(k) for k in keep if res.get(k) not in (None, "", [])}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}


class Handler(BaseHTTPRequestHandler):
    server_version = "HappyLeetGame/1.0"

    def log_message(self, fmt, *args):  # 安靜一點
        pass

    def _send(self, code, data, ctype="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, rel):
        f = (STATIC / rel).resolve()
        if STATIC.resolve() not in f.parents or not f.is_file():
            return self._send(404, {"error": "找不到"})
        data = f.read_bytes()
        if f.name == "index.html":
            data = data.replace(b"__GAME_TOKEN__", TOKEN.encode())
        self._send(200, data, MIME.get(f.suffix, "application/octet-stream"))

    def _asset(self, kind):
        files = list(ASSET_DIR.glob(f"{kind}.*")) if kind in ("avatar", "bg") else []
        if not files:
            return self._send(404, {"error": "找不到"})
        f = files[0]
        mime = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp"}
        self._send(200, f.read_bytes(), mime.get(f.suffix.lstrip("."), "application/octet-stream"))

    def _handle(self, method):
        u = urlparse(self.path)
        if u.path.startswith("/user-asset/"):
            return self._asset(u.path.rsplit("/", 1)[-1])
        if not u.path.startswith("/api/"):
            return self._static("index.html" if u.path in ("/", "") else u.path.lstrip("/"))
        if self.headers.get("X-Game-Token") != TOKEN:
            return self._send(403, {"error": "權杖不符，請重新整理頁面"})
        body = {}
        if method == "POST":
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                try:
                    body = json.loads(self.rfile.read(n).decode("utf-8"))
                except ValueError:
                    return self._send(400, {"error": "JSON 格式錯誤"})
        try:
            self._send(200, api(u.path, body, parse_qs(u.query)))
        except SystemExit as e:
            self._send(400, {"error": str(e.code).strip()})
        except (ValueError, KeyError, IndexError) as e:
            self._send(400, {"error": str(e)})
        except LookupError as e:
            self._send(404, {"error": str(e)})
        except lc.requests.RequestException as e:
            self._send(502, {"error": f"連不到 LeetCode：{e}"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")


def _refresh_ratings():
    n = lc.update_ratings()
    if n:
        engine.set_ratings(lc.load_ratings())


def serve(port=8765, open_browser=True):
    lc.ensure_home()
    engine.set_ratings(lc.load_ratings())
    threading.Thread(target=_refresh_ratings, daemon=True).start()
    if not lc.PROBLEMS_PATH.exists():
        print("📥 第一次啟動，先抓題目清單…")
        lc.cmd_fetch(type("A", (), {"all": False})())
    httpd = None
    for p in range(port, port + 10):
        try:
            httpd = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if httpd is None:
        sys.exit(f"❌ {port}~{port + 9} 的埠都被占用了，用 --port 換一個試試。")
    url = f"http://localhost:{port}/"
    print("🎮 開心每日刷題 · 遊戲模式啟動！")
    print(f"   網址：{url}")
    print(f"   工作區：{lc.ROOT}")
    print("   在 VS Code 裡：Ctrl+Shift+P → 輸入 Simple Browser: Show → 貼上網址，就能邊寫邊玩")
    print("   關閉：在這個終端機按 Ctrl+C")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 下次見！")
    finally:
        httpd.server_close()
