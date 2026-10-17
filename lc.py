#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
開心每日刷題 — LeetCode 簡單題練習小工具
=========================================

這支工具讓你不用打開 LeetCode 網站，就能在終端機完成整個刷題流程：

    1. fetch   抓取「簡單題」清單存到 data/problems.json
    2. list    列出題目與你的完成狀態
    3. show    顯示某題的題目敘述
    4. new     建立解題檔（自動帶官方程式碼範本）到 solutions/
    5. test    用題目附的範例測資在線上跑跑看（不算正式提交）
    6. submit  真的把程式碼送到 LeetCode 官方判題，結果寫回 data/records.json
    7. stats   看你刷了幾題
    8. game    🎮 開啟刷題遊戲（技能樹、戰力分析、肉鴿遠征）

用法範例：
    python lc.py fetch                # 第一次先抓題目清單
    python lc.py list --undone        # 看還沒寫的題目
    python lc.py new 1                # 建立第 1 題 (two-sum) 的解題檔
    python lc.py test 1               # 用範例測資跑跑看
    python lc.py submit 1             # 正式提交判題

提交（submit / test）需要登入資訊，請看 README.md 設定 config.json。
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Windows 主控台預設不是 UTF-8，會印不出 emoji 與中文，這裡強制切成 UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ---------------------------------------------------------------------------
# 路徑設定：所有資料都放在這支腳本旁邊，跨平台都能跑
# ---------------------------------------------------------------------------
# 程式本身的位置（打包成 EXE 時是解壓縮後的暫存資料夾）
FROZEN = getattr(sys, "frozen", False)
REPO_DIR = Path(__file__).resolve().parent
APP_DIR = Path(getattr(sys, "_MEIPASS", REPO_DIR))


def _default_home() -> Path:
    """每位玩家自己的工作區：登入資訊、紀錄、解題檔、遊戲存檔都放這裡，不會進到開源 repo。

    - 設了環境變數 LCD_HOME 就用它
    - 打包成 EXE：文件/LeetCodeDungeon
    - 從原始碼執行：專案底下的 workspace/（已被 .gitignore 排除）
    """
    env = os.environ.get("LCD_HOME")
    if env:
        return Path(env).expanduser().resolve()
    if FROZEN:
        return Path.home() / "Documents" / "LeetCodeDungeon"
    return REPO_DIR / "workspace"


ROOT = _default_home()
DATA_DIR = ROOT / "data"
SOLUTIONS_DIR = ROOT / "solutions"
CONFIG_PATH = ROOT / "config.json"
PROBLEMS_PATH = DATA_DIR / "problems.json"
RECORDS_PATH = DATA_DIR / "records.json"

BASE = os.environ.get("LCD_BASE", "https://leetcode.com")
GRAPHQL = f"{BASE}/graphql"

# 解題檔裡用來分隔「設定」與「你的程式碼」的標記（前面會加上該語言的註解符號）
MARK = "=== 以下是你的程式碼 (YOUR CODE BELOW) ==="
META_END = "# " + MARK  # 舊版相容

# 支援的語言：LeetCode langSlug → (副檔名, 註解符號, 顯示名稱)
LANGS = {
    "python3": (".py", "#", "Python 3"),
    "cpp": (".cpp", "//", "C++"),
    "java": (".java", "//", "Java"),
    "javascript": (".js", "//", "JavaScript"),
    "typescript": (".ts", "//", "TypeScript"),
    "c": (".c", "//", "C"),
    "csharp": (".cs", "//", "C#"),
    "golang": (".go", "//", "Go"),
    "rust": (".rs", "//", "Rust"),
    "kotlin": (".kt", "//", "Kotlin"),
}


def ensure_home():
    """第一次執行時建立工作區，並把舊版放在專案根目錄的個人資料搬進來。"""
    ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    moved = []
    # 只有用預設工作區（專案底下的 workspace/）時才搬，設了 LCD_HOME 就不碰專案資料夾
    if not FROZEN and ROOT == REPO_DIR / "workspace" and not (DATA_DIR / "records.json").exists():
        legacy = ["config.json", "data/records.json", "data/game.json", "data/profile.json",
                  "data/details", "solutions", "pdf", "SOLVED.md"]
        for rel in legacy:
            src, dst = REPO_DIR / rel, ROOT / rel
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                moved.append(rel)
    if moved:
        print(f"📦 已把你的個人資料搬到工作區 {ROOT}：{', '.join(moved)}")
    # 題庫：工作區沒有就從程式內建的種子複製一份，第一次啟動不用等抓題
    seed = APP_DIR / "data" / "problems.json"
    if not (DATA_DIR / "problems.json").exists() and seed.exists():
        shutil.copyfile(seed, DATA_DIR / "problems.json")
    return moved


# ---------------------------------------------------------------------------
# 小工具：讀寫 JSON
# ---------------------------------------------------------------------------
def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class LcError(SystemExit):
    """給玩家看的錯誤。kind 讓遊戲畫面決定要顯示哪個按鈕：
    network 網路、login 登入、verify 真人驗證、rate 太頻繁、blocked 防火牆、timeout 判題逾時、code 程式碼本身、other 其他。
    繼承 SystemExit，所以指令列版本照舊印出訊息後結束。"""

    def __init__(self, msg: str, kind: str = "other"):
        super().__init__(msg)
        self.kind = kind


# 進度：讓遊戲畫面能顯示「送出中 → 判題中 → 完成」
PROGRESS = {"phase": None, "action": None, "since": 0.0, "polls": 0}


def set_progress(phase, action=None):
    PROGRESS.update(phase=phase, since=time.time(), polls=0)
    if action:
        PROGRESS["action"] = action


def load_config():
    """讀取登入設定。沒有檔案時回傳空 dict（fetch/list 不需要登入）。"""
    return load_json(CONFIG_PATH, {})


# ---------------------------------------------------------------------------
# 建立一個帶好 cookie / header 的 requests session
# ---------------------------------------------------------------------------
def make_session(require_login: bool = False) -> requests.Session:
    cfg = load_config()
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36",
            "Content-Type": "application/json",
            "Origin": BASE,
        }
    )
    session_cookie = cfg.get("session")
    csrftoken = cfg.get("csrftoken")
    if session_cookie and csrftoken:
        s.cookies.set("LEETCODE_SESSION", session_cookie, domain="leetcode.com")
        s.cookies.set("csrftoken", csrftoken, domain="leetcode.com")
        s.headers["x-csrftoken"] = csrftoken
    elif require_login:
        raise LcError(
            "❌ 這個動作需要先登入 LeetCode。\n"
            "   遊戲裡：到「設定 → 帳號」按「用瀏覽器登入」。\n"
            "   指令列：python lc.py game 開遊戲登入，或照 README 填 config.json。", "login")
    return s


def check_response(resp: requests.Response, action: str):
    """LeetCode 回應不是 2xx 時，判斷真正原因、存下原始回應，再給看得懂的訊息。"""
    if resp.ok:
        return
    body = resp.text or ""
    low = body.lower()
    log = DATA_DIR / "last_http_error.txt"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        keep = ("server", "cf-ray", "cf-mitigated", "content-type", "retry-after")
        log.write_text(
            f"時間：{datetime.now():%Y-%m-%d %H:%M:%S}\n動作：{action}\n網址：{resp.request.method} {resp.url}\n"
            f"狀態：{resp.status_code}\n"
            + "".join(f"{k}: {resp.headers.get(k)}\n" for k in keep if resp.headers.get(k))
            + "\n" + body[:4000],
            encoding="utf-8",
        )
    except OSError:
        pass
    tail = f"\n   技術細節已存到 {log}"
    if resp.headers.get("cf-mitigated") == "challenge" or "just a moment" in low or "cf_chl" in low:
        raise LcError(f"❌ LeetCode 要求確認你是真人，這次{action}還沒送出（不是登入問題）。\n"
                      "   在遊戲裡按「重送」，跳出的視窗點一下驗證就會繼續；\n"
                      "   如果設定裡的提交方式是「程式直接送出」，改成「瀏覽器代送」會順很多。" + tail, "verify")
    if "sorry, you have been blocked" in low or "attention required" in low or "cf-error-details" in low:
        raise LcError(f"❌ LeetCode 的防火牆擋下了這次{action}（不是登入問題），可能是程式碼內容觸發了它的規則。\n"
                      "   等幾分鐘再按「重送」；一直被擋的話，試著改掉程式碼裡很長的註解或特殊字元。" + tail, "blocked")
    if resp.status_code == 429:
        raise LcError(f"❌ 送得太頻繁了（429），LeetCode 要你等一下。過一兩分鐘再{action}。" + tail, "rate")
    if resp.status_code in (401, 403) and ("csrf" in low or "login" in low or "authentication" in low or not body.strip()):
        raise LcError(f"❌ 被拒絕（{resp.status_code}）：登入資訊失效了。到「設定 → 帳號」重新登入一次。" + tail, "login")
    if resp.status_code == 403:
        raise LcError(f"❌ 被拒絕（403），原因不明，看起來不是登入過期。\n"
                      f"   LeetCode 的回應開頭：{' '.join(body.split())[:160]}" + tail, "other")
    raise LcError(f"❌ {action}失敗：LeetCode 回應 {resp.status_code}。" + tail,
                  "network" if resp.status_code >= 500 else "other")


# ---------------------------------------------------------------------------
# 瀏覽器代送：被 Cloudflare 要求真人驗證時，改從專用瀏覽器（登入用的那個）送出
# ---------------------------------------------------------------------------
_RELAY = None
_RELAY_UNTIL = 0.0


class RelayResponse:
    """把瀏覽器代送的結果包裝成跟 requests.Response 差不多的樣子。"""

    def __init__(self, method, url, status, text, mitigated):
        self.status_code = status
        self.text = text
        self.url = url
        self.ok = 200 <= status < 300
        self.headers = requests.structures.CaseInsensitiveDict({"cf-mitigated": mitigated} if mitigated else {})
        self.request = type("Req", (), {"method": method})()

    def json(self):
        return json.loads(self.text)


def is_challenge(resp) -> bool:
    if resp.headers.get("cf-mitigated") == "challenge":
        return True
    return resp.status_code in (403, 503) and "just a moment" in (resp.text or "")[:3000].lower()


def get_relay():
    global _RELAY
    if _RELAY is None:
        try:
            from game.browser_login import BrowserRelay, find_browser
        except ImportError:
            return None
        if not find_browser():
            return None
        _RELAY = BrowserRelay(ROOT / "browser-profile", BASE)
    return _RELAY


def transport() -> str:
    """提交方式：browser＝一律由藏起來的瀏覽器送出（預設，最不容易被擋）；direct＝程式直接送出。"""
    t = load_config().get("transport", "browser")
    return t if t in ("browser", "direct") else "browser"


def lc_request(session, method, path, payload=None, referer=None, action="請求"):
    """送 LeetCode 請求。

    預設由瀏覽器送出；選了「直接送出」時，被 Cloudflare 擋下也會自動改用瀏覽器（之後 30 分鐘都走瀏覽器）。
    """
    global _RELAY_UNTIL
    url = BASE + path
    relay = None
    if transport() == "browser" or time.time() < _RELAY_UNTIL:
        relay = get_relay()
    if relay is not None:
        try:
            status, text, mit = relay.request(method, path, payload, referer)
            resp = RelayResponse(method, url, status, text, mit)
            check_response(resp, action)
            return resp.json()
        except (RuntimeError, OSError, ConnectionError, ValueError) as e:
            print(f"⚠️  瀏覽器送出失敗（{e}），改由程式直接送出…")
            relay = None
    if relay is None:
        resp = session.request(method, url, json=payload if method == "POST" else None,
                               headers={"Referer": BASE + (referer or "/")}, timeout=30)
        if not is_challenge(resp):
            check_response(resp, action)
            return resp.json()
        relay = get_relay()
        if relay is None:
            check_response(resp, action)  # 沒有瀏覽器可用：照原本的方式回報
        print("🛡️  LeetCode 要求真人驗證，改用瀏覽器視窗送出…（如果視窗裡出現驗證，請點一下）")
        _RELAY_UNTIL = time.time() + 1800
    status, text, mit = relay.request(method, path, payload, referer)
    resp = RelayResponse(method, url, status, text, mit)
    check_response(resp, action)
    return resp.json()


def graphql(session: requests.Session, query: str, variables: dict) -> dict:
    resp = session.post(
        GRAPHQL,
        json={"query": query, "variables": variables},
        headers={"Referer": f"{BASE}/problemset/all/"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL 錯誤：{payload['errors']}")
    return payload["data"]


# ---------------------------------------------------------------------------
# 1. fetch — 抓取簡單題清單
# ---------------------------------------------------------------------------
PROBLEM_LIST_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug
    limit: $limit
    skip: $skip
    filters: $filters
  ) {
    total: totalNum
    questions: data {
      questionId
      frontendQuestionId: questionFrontendId
      title
      titleSlug
      difficulty
      acRate
      paidOnly: isPaidOnly
      status
      topicTags { name slug }
    }
  }
}
"""


def cmd_fetch(args):
    session = make_session()
    all_questions = []
    skip = 0
    page = 50
    scope = getattr(args, "all", False)
    filters = {} if scope else {"difficulty": "EASY"}
    print("📥 正在抓取 LeetCode " + ("全部難度" if scope else "簡單題") + "清單…")
    while True:
        data = graphql(
            session,
            PROBLEM_LIST_QUERY,
            {
                "categorySlug": "",
                "skip": skip,
                "limit": page,
                "filters": filters,
            },
        )
        block = data["problemsetQuestionList"]
        total = block["total"]
        questions = block["questions"]
        if not questions:
            break
        all_questions.extend(questions)
        skip += page
        print(f"   …已抓取 {len(all_questions)} / {total}")
        if skip >= total:
            break
        time.sleep(0.3)  # 對伺服器客氣一點，避免被擋

    # 整理成乾淨的格式，免費題排前面
    problems = []
    for q in all_questions:
        problems.append(
            {
                "id": q["frontendQuestionId"],
                "questionId": q["questionId"],
                "title": q["title"],
                "slug": q["titleSlug"],
                "difficulty": q["difficulty"],
                "acRate": round(q["acRate"], 1),
                "paidOnly": q["paidOnly"],
                "tags": [t["slug"] for t in q["topicTags"]],
            }
        )
    problems.sort(key=lambda p: int(p["id"]))
    save_json(PROBLEMS_PATH, problems)
    free = sum(1 for p in problems if not p["paidOnly"])
    kind = "題" if scope else "題簡單題"
    print(f"✅ 完成！共 {len(problems)} {kind}（其中 {free} 題免費），存到 {PROBLEMS_PATH}")


# ---------------------------------------------------------------------------
# 共用：依 id 或 slug 找題目
# ---------------------------------------------------------------------------
def get_problems():
    problems = load_json(PROBLEMS_PATH, None)
    if problems is None:
        sys.exit("❌ 還沒有題目清單，請先執行：python lc.py fetch")
    return problems


def find_problem(key: str):
    problems = get_problems()
    key = str(key).strip()
    # 容錯：接受解題檔檔名，例如 0001-two-sum 或 0001-two-sum.py（VS Code 工作用）
    m = re.match(r"^0*(\d+)-([a-z0-9-]+?)(\.[a-z]+)?$", key)
    if m:
        key = m.group(2)
    for p in problems:
        if p["id"] == key or p["slug"] == key:
            return p
    # 容錯：忽略大小寫的 slug
    for p in problems:
        if p["slug"].lower() == key.lower():
            return p
    sys.exit(f"❌ 找不到題目「{key}」。用 python lc.py list 看看有哪些題目。")


# ---------------------------------------------------------------------------
# 2. list — 列出題目
# ---------------------------------------------------------------------------
def cmd_list(args):
    problems = get_problems()
    records = load_json(RECORDS_PATH, {})

    rows = []
    for p in problems:
        if args.free and p["paidOnly"]:
            continue
        if args.tag and args.tag not in p["tags"]:
            continue
        rec = records.get(p["slug"])
        solved = bool(rec and rec.get("solved"))
        attempted = bool(rec)
        if args.undone and solved:
            continue
        rows.append((p, solved, attempted))

    if args.limit:
        rows = rows[: args.limit]

    for p, solved, attempted in rows:
        mark = "✅" if solved else ("🔸" if attempted else "  ")
        lock = "🔒" if p["paidOnly"] else "  "
        print(f"{mark}{lock} {p['id']:>4}  {p['title']:<45} 通過率 {p['acRate']}%")
    print(f"\n共顯示 {len(rows)} 題。✅=已解 🔸=試過 🔒=付費題")


# ---------------------------------------------------------------------------
# 3. show — 顯示題目敘述
# ---------------------------------------------------------------------------
QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    codeSnippets { lang langSlug code }
    sampleTestCase
    exampleTestcases
  }
}
"""


def fetch_question_detail(slug: str) -> dict:
    """抓單一題的完整資料（題目敘述、程式碼範本、範例測資），並快取起來。"""
    cache_dir = DATA_DIR / "details"
    cache_path = cache_dir / f"{slug}.json"
    cached = load_json(cache_path, None)
    if cached:
        return cached
    session = make_session()
    data = graphql(session, QUESTION_QUERY, {"titleSlug": slug})
    q = data["question"]
    if q is None:
        sys.exit(f"❌ 抓不到題目 {slug}（可能是付費題，需要登入）。")
    save_json(cache_path, q)
    return q


def html_to_text(html: str) -> str:
    """把題目的 HTML 敘述轉成大致可讀的純文字（夠用就好）。"""
    text = html
    text = re.sub(r"</p>|</div>|<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<li>", "\n• ", text, flags=re.I)
    text = re.sub(r"<sup>", "^", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)  # 去掉其餘標籤
    # 還原常見 HTML 實體
    replaces = {
        "&nbsp;": " ", "&lt;": "<", "&gt;": ">", "&amp;": "&",
        "&quot;": '"', "&#39;": "'", "&le;": "≤", "&ge;": "≥",
    }
    for a, b in replaces.items():
        text = text.replace(a, b)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cmd_show(args):
    p = find_problem(args.problem)
    q = fetch_question_detail(p["slug"])
    print(f"\n{'='*60}")
    print(f"{q['questionFrontendId']}. {q['title']}  [{q['difficulty']}]")
    print(f"網址：{BASE}/problems/{p['slug']}/")
    print(f"{'='*60}\n")
    print(html_to_text(q["content"]))
    print()


# ---------------------------------------------------------------------------
# 4. new — 建立解題檔
# ---------------------------------------------------------------------------
def default_lang() -> str:
    lang = load_config().get("lang") or "python3"
    return lang if lang in LANGS else "python3"


def solution_path(p: dict, lang: str = None) -> Path:
    """解題檔路徑。沒指定語言時，優先找已經存在的檔案（任何語言），否則用設定的語言。"""
    stem = f"{int(p['id']):04d}-{p['slug']}"
    if lang is None:
        for code, (ext, _, _) in LANGS.items():
            f = SOLUTIONS_DIR / (stem + ext)
            if f.exists():
                return f
        lang = default_lang()
    return SOLUTIONS_DIR / (stem + LANGS.get(lang, LANGS["python3"])[0])


def get_snippet(q: dict, lang: str = "python3") -> str:
    for snip in q["codeSnippets"] or []:
        if snip["langSlug"] == lang:
            return snip["code"]
    return ""


def get_python_snippet(q: dict) -> str:
    return get_snippet(q, "python3") or (q["codeSnippets"][0]["code"] if q["codeSnippets"] else "")


def create_solution(p: dict, force: bool = False, lang: str = None):
    """建立解題檔。回傳 (路徑, 是否新建)。已存在且沒有 force 就不動它。"""
    existing = solution_path(p)
    if existing.exists() and not force:
        return existing, False
    lang = lang or default_lang()
    q = fetch_question_detail(p["slug"])
    snippet = get_snippet(q, lang)
    if not snippet:
        lang, snippet = "python3", get_python_snippet(q)
    ext, c, _ = LANGS[lang]
    path = solution_path(p, lang)
    header = "\n".join([
        f"{c} {q['questionFrontendId']}. {q['title']}  [{q['difficulty']}]",
        f"{c} {BASE}/problems/{p['slug']}/",
        f"{c}",
        f"{c} meta-slug: {p['slug']}",
        f"{c} meta-qid: {q['questionId']}",
        f"{c} meta-lang: {lang}",
        f"{c}",
        f"{c} 寫完後在遊戲畫面按「試招／出招」，或在 VS Code 按 Ctrl+Shift+B 直接提交這個檔案。",
        f"{c} 指令版：python lc.py test {p['id']}（試跑）、python lc.py submit {p['id']}（提交）",
        f"{c} {MARK}",
    ]) + "\n"
    SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    if force:
        for code, (e, _, _) in LANGS.items():  # 換語言重建時，清掉其他語言的舊檔
            old = solution_path(p, code)
            if old != path and old.exists():
                old.unlink()
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + snippet + "\n")
    return path, True


def cmd_new(args):
    p = find_problem(args.problem)
    path, created = create_solution(p, force=args.force, lang=args.lang)
    if not created:
        print(f"⚠️  檔案已存在：{path}\n   （要覆蓋請加 --force）")
        return
    print(f"✅ 已建立解題檔：{path}")
    print("   打開它，把你的解法寫在標記底下就可以了。")


# ---------------------------------------------------------------------------
# 共用：從解題檔讀出設定與程式碼
# ---------------------------------------------------------------------------
def read_solution(p: dict):
    path = solution_path(p)
    if not path.exists():
        sys.exit(
            f"❌ 找不到解題檔：{path}\n"
            f"   請先執行：python lc.py new {p['id']}"
        )
    raw = path.read_text(encoding="utf-8")
    meta = {}
    for line in raw.splitlines():
        m = re.match(r"\s*(?:#|//)\s*meta-(\w+):\s*(.+)", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()

    lines = raw.splitlines(keepends=True)
    cut = next((i for i, l in enumerate(lines) if MARK in l), None)
    code = "".join(lines[cut + 1:]) if cut is not None else raw  # 沒有標記就整份送

    qid = meta.get("qid") or p.get("questionId")
    ext_lang = next((k for k, v in LANGS.items() if path.suffix == v[0]), "python3")
    lang = meta.get("lang", ext_lang)
    if not code.strip():
        raise LcError("❌ 你的程式碼是空的，先寫點東西再提交吧 :)", "code")
    # 防呆：內容跟官方空白範本一模一樣 → 八成是在編輯器裡寫了但還沒存檔
    cached = load_json(DATA_DIR / "details" / f"{p['slug']}.json", None)
    if cached:
        squash = lambda t: re.sub(r"\s+", "", t or "")
        if squash(code) == squash(get_snippet(cached, lang)):
            raise LcError(f"❌ {path.name} 還是空白範本，看起來還沒存檔。\n"
                          "   在 VS Code 按 Ctrl+S 存檔後再試一次（分頁標題旁邊有白點 ● 就是還沒存）。", "code")
    return qid, lang, code, path


def solution_offset(path: Path) -> int:
    """解題檔裡「你的程式碼」前面有幾行（本地試跑用來對齊錯誤訊息的行號）。"""
    lines = path.read_text(encoding="utf-8").splitlines()
    cut = next((i for i, l in enumerate(lines) if MARK in l), None)
    return cut + 1 if cut is not None else 0


def test_mode() -> str:
    """試跑方式：auto＝先在自己電腦跑，跑不了才用 LeetCode；local＝只在本地；online＝只用 LeetCode。"""
    m = load_config().get("testMode", "auto")
    return m if m in ("auto", "local", "online") else "auto"


def poll_check(session: requests.Session, check_id: str, slug: str) -> dict:
    """輪詢判題結果，直到完成。"""
    waits = [0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0] + [4.0] * 20  # 越等越久，總共約 90 秒、不到 30 次請求
    set_progress("judge")
    for wait in waits:
        time.sleep(wait)
        PROGRESS["polls"] += 1
        result = lc_request(session, "GET", f"/submissions/detail/{check_id}/check/",
                            referer=f"/problems/{slug}/", action="取得判題結果")
        if result.get("state") == "SUCCESS":
            return result
        print("   …判題中", end="\r")
    raise LcError("❌ 等了 90 秒還沒有判題結果，LeetCode 可能很忙。\n"
                  "   程式碼可能已經送到了：先按「同步官網進度」看看，沒有紀錄再重送。", "timeout")


# ---------------------------------------------------------------------------
# 5. test — 用範例測資線上試跑（interpret，不算正式提交）
# ---------------------------------------------------------------------------
def run_test(p: dict, data_input=None, where: str = None) -> dict:
    """試跑。預設先在自己電腦上跑（快、不用登入），這題跑不了才改用 LeetCode 線上試跑。"""
    q = fetch_question_detail(p["slug"])
    qid, lang, code, path = read_solution(p)
    data_input = data_input if data_input else q["exampleTestcases"]
    where = where or test_mode()
    fallback = None
    if where != "online":
        from game import localrun
        try:
            return localrun.run_local(q, lang, code, solution_offset(path), path.name, data_input,
                                      DATA_DIR / "localrun")
        except localrun.Unsupported as e:
            if where == "local":
                raise LcError(f"❌ 這題沒辦法在本地試跑：{e}", "code")
            fallback = str(e)
    set_progress("send", "試跑")
    session = make_session(require_login=True)
    data = lc_request(session, "POST", f"/problems/{p['slug']}/interpret_solution/",
                      {"lang": lang, "question_id": qid, "typed_code": code, "data_input": data_input},
                      referer=f"/problems/{p['slug']}/", action="試跑")
    interpret_id = data.get("interpret_id")
    if not interpret_id:
        raise LcError(f"❌ 試跑失敗：{json.dumps(data, ensure_ascii=False)[:300]}")
    result = poll_check(session, interpret_id, p["slug"])
    set_progress("done")
    result["_input"] = data_input
    if fallback:
        result["_fallback"] = fallback
    return result


def cmd_test(args):
    p = find_problem(args.problem)
    q = fetch_question_detail(p["slug"])
    data_input = args.input if args.input else q["exampleTestcases"]
    where = "online" if args.online else "local" if args.local else None
    print(f"🧪 試跑第 {p['id']} 題（{p['title']}）…")
    result = run_test(p, data_input, where)
    print(" " * 30, end="\r")
    if result.get("local"):
        _print_local_result(result)
        return
    if result.get("_fallback"):
        print(f"   （這題沒辦法本地跑：{result['_fallback']}，改用 LeetCode 線上試跑）")
    print(f"   測資：\n{data_input}\n")
    _print_run_result(result, is_test=True)


def _print_local_result(r: dict):
    names = {"Accepted": "✅ 範例全對", "Wrong Answer": "❌ 答案不對", "Runtime Error": "💥 執行時錯誤",
             "Compile Error": "⛔ 編譯/語法錯誤", "Time Limit Exceeded": "⏱️ 超過時間", "Finished": "📋 跑完了（自訂測資沒有標準答案）"}
    print(f"📊 本地試跑（{r.get('engine')}，{r.get('elapsed_ms')} ms）：{names.get(r['status_msg'], r['status_msg'])}")
    if r.get("compile_error"):
        print(r["compile_error"])
        return
    for k, c in enumerate(r["cases"], 1):
        mark = {True: "✅", False: "❌", None: "・"}[c.get("ok")]
        print(f"\n{mark} 第 {k} 筆  輸入：{' | '.join(c['input'])}")
        if c.get("stdout"):
            print("   print 輸出：" + c["stdout"].rstrip().replace("\n", "\n               "))
        if c.get("error"):
            print("   錯誤：" + c["error"].replace("\n", "\n         "))
            continue
        print(f"   你的輸出：{c.get('output')}" + (f"   （{c['ms']} ms）" if c.get("ms") is not None else ""))
        if c.get("expected") is not None:
            print(f"   正確答案：{c['expected']}")


def _print_run_result(result: dict, is_test: bool):
    status = result.get("status_msg", "未知")
    print(f"📊 結果：{status}")

    if result.get("compile_error") or result.get("full_compile_error"):
        print("⛔ 編譯/語法錯誤：")
        print(result.get("full_compile_error") or result.get("compile_error"))
        return
    if result.get("runtime_error") or result.get("full_runtime_error"):
        print("⛔ 執行時錯誤：")
        print(result.get("full_runtime_error") or result.get("runtime_error"))

    if is_test:
        ans = result.get("code_answer")
        expected = result.get("expected_code_answer")
        if ans is not None:
            print(f"   你的輸出：{ans}")
        if expected:
            print(f"   正確答案：{expected}")
    else:
        total = result.get("total_testcases")
        correct = result.get("total_correct")
        if total is not None:
            print(f"   通過測資：{correct}/{total}")
        if result.get("status_runtime"):
            print(f"   執行時間：{result['status_runtime']}")
        if result.get("status_memory"):
            print(f"   記憶體：{result['status_memory']}")
        # 答錯時，LeetCode 會給出哪一筆測資錯了
        if result.get("last_testcase"):
            print(f"   出錯的輸入：{result['last_testcase']}")
            print(f"   你的輸出：{result.get('code_output')}")
            print(f"   正確答案：{result.get('expected_output')}")


# ---------------------------------------------------------------------------
# 6. submit — 正式提交判題
# ---------------------------------------------------------------------------
def run_submit(p: dict):
    """正式提交並寫進 records.json。回傳 (判題結果, 是否通過)。"""
    qid, lang, code, _ = read_solution(p)
    session = make_session(require_login=True)
    set_progress("send", "提交")
    data = lc_request(session, "POST", f"/problems/{p['slug']}/submit/",
                      {"lang": lang, "question_id": qid, "typed_code": code},
                      referer=f"/problems/{p['slug']}/", action="提交")
    submission_id = data.get("submission_id")
    if not submission_id:
        raise LcError(f"❌ 提交失敗：{json.dumps(data, ensure_ascii=False)[:300]}")

    result = poll_check(session, str(submission_id), p["slug"])
    set_progress("done")
    accepted = result.get("status_msg") == "Accepted"
    record_submission(p, lang, submission_id, result, accepted, code)
    return result, accepted


def cmd_submit(args):
    p = find_problem(args.problem)
    print(f"🚀 正在提交第 {p['id']} 題（{p['title']}）到 LeetCode…")
    result, accepted = run_submit(p)
    print(" " * 30, end="\r")
    _print_run_result(result, is_test=False)
    if accepted:
        print("🎉 通過了！紀錄已更新。繼續加油！")
    else:
        print("💪 還沒過沒關係，紀錄已存。看一下錯在哪，再改改！")


def record_submission(p, lang, submission_id, result, accepted, code=""):
    records = load_json(RECORDS_PATH, {})
    rec = records.get(p["slug"], {
        "id": p["id"],
        "title": p["title"],
        "difficulty": p["difficulty"],
        "solved": False,
        "attempts": [],
    })
    rec["attempts"].append(
        {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": result.get("status_msg"),
            "passed": f"{result.get('total_correct')}/{result.get('total_testcases')}",
            "runtime": result.get("status_runtime"),
            "memory": result.get("status_memory"),
            "lang": lang,
            "submission_id": submission_id,
            "accepted": accepted,
        }
    )
    if accepted:
        rec["solved"] = True
        rec.setdefault("solved_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    records[p["slug"]] = rec
    save_json(RECORDS_PATH, records)
    try:  # 錯題本：沒過就記下來，過了就把這題的舊錯題標成已解決（壞掉也不能影響提交紀錄）
        from game import mistakes
        if accepted:
            mistakes.resolve(DATA_DIR, p["slug"])
        else:
            mistakes.add(DATA_DIR, p, lang, result, code)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  錯題本沒有記到：{e}")


# ---------------------------------------------------------------------------
# 8. pdf — 把題目匯出成排版乾淨的 PDF
# ---------------------------------------------------------------------------
PDF_DIR = ROOT / "pdf"

# PDF 的樣式：等寬字呈現範例與程式碼，保留 LeetCode 原本的排版
PDF_CSS = """
@page { size: a4 portrait; margin: 1.6cm; }
body { font-family: Helvetica; font-size: 11pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 17pt; margin: 0 0 2px 0; }
.meta { color: #777; font-size: 9pt; margin-bottom: 14px; }
.diff-Easy { color: #1a9c4c; }
.diff-Medium { color: #c98800; }
.diff-Hard { color: #d33; }
pre { background-color: #f5f5f5; border: 1px solid #e2e2e2; padding: 8px;
      font-family: Courier; font-size: 9.5pt; }
code { font-family: Courier; background-color: #f0f0f0; font-size: 10pt; }
strong, b { color: #000; }
.pagebreak { page-break-after: always; }
img { max-width: 450px; }
"""


def _img_callback(uri, rel):
    """xhtml2pdf 用這個把題目裡的遠端圖片下載到本地，PDF 才看得到圖。"""
    if uri.startswith("http"):
        cache = DATA_DIR / "_imgcache"
        cache.mkdir(parents=True, exist_ok=True)
        name = re.sub(r"[^\w.-]", "_", uri.split("/")[-1]) or "img"
        path = cache / name
        if not path.exists():
            try:
                r = requests.get(uri, timeout=20)
                if r.ok:
                    path.write_bytes(r.content)
                else:
                    return uri
            except requests.RequestException:
                return uri
        return str(path)
    return uri


def _problem_fragment(p: dict, q: dict) -> str:
    """產生單一題目的 HTML 片段（標題 + 原始題目敘述）。"""
    diff = q["difficulty"]
    return (
        f"<h1>{q['questionFrontendId']}. {q['title']}</h1>"
        f"<div class='meta'>"
        f"<span class='diff-{diff}'>{diff}</span> &nbsp;|&nbsp; "
        f"Acceptance {p.get('acRate', '?')}% &nbsp;|&nbsp; "
        f"{BASE}/problems/{p['slug']}/"
        f"</div>"
        f"{q['content']}"
    )


def _selected_problems(args) -> list:
    """依使用者給的題號 / --range 找出要匯出的題目清單。"""
    problems = get_problems()
    by_key = {}
    for p in problems:
        by_key[p["id"]] = p
        by_key[p["slug"]] = p

    selected = []
    for key in args.problem:
        if str(key) in by_key:
            selected.append(by_key[str(key)])
        else:
            selected.append(find_problem(key))

    if args.range:
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", args.range)
        if not m:
            sys.exit("❌ --range 格式應為 起-迄，例如 1-20")
        lo, hi = int(m.group(1)), int(m.group(2))
        for p in problems:
            if lo <= int(p["id"]) <= hi:
                selected.append(p)

    # 去重並保持順序
    seen, uniq = set(), []
    for p in selected:
        if p["slug"] not in seen:
            seen.add(p["slug"])
            uniq.append(p)
    return uniq


def cmd_pdf(args):
    from xhtml2pdf import pisa  # 延後匯入，沒用到 pdf 就不必載入

    if not args.problem and not args.range:
        sys.exit("❌ 請指定題目，例如：python lc.py pdf 1   或   python lc.py pdf --range 1-20")

    targets = _selected_problems(args)
    if not targets:
        sys.exit("❌ 沒有符合的題目。")

    print(f"📄 準備匯出 {len(targets)} 題的題目敘述…")
    fragments = []
    for i, p in enumerate(targets):
        q = fetch_question_detail(p["slug"])
        print(f"   ✓ {p['id']}. {p['title']}")
        frag = _problem_fragment(p, q)
        if i < len(targets) - 1:
            frag += "<div class='pagebreak'></div>"
        fragments.append(frag)

    html = (
        "<html><head><meta charset='utf-8'>"
        f"<style>{PDF_CSS}</style></head><body>"
        + "".join(fragments)
        + "</body></html>"
    )

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = PDF_DIR / out_path
    elif len(targets) == 1:
        p = targets[0]
        out_path = PDF_DIR / f"{int(p['id']):04d}-{p['slug']}.pdf"
    else:
        out_path = PDF_DIR / f"leetcode-{len(targets)}題.pdf"

    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(html, dest=f, link_callback=_img_callback, encoding="utf-8")
    if result.err:
        sys.exit("❌ 產生 PDF 時發生錯誤。")
    print(f"✅ 完成！PDF 存到：{out_path}")


# ---------------------------------------------------------------------------
# 11. push — 把解過的題目推上 GitHub
# ---------------------------------------------------------------------------
def git(*args, check=True, capture=False):
    """執行 git 指令；找不到 git 時給友善提示。"""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=check,
            text=True,
            capture_output=capture,
            encoding="utf-8",
        )
    except FileNotFoundError:
        sys.exit("❌ 找不到 git。請先安裝 Git：https://git-scm.com/download/win")


def git_ok(*args):
    """執行 git 指令，回傳是否成功（exit code == 0），不丟例外。"""
    return git(*args, check=False, capture=True).returncode == 0


def generate_solved_md():
    """從 records.json 產生一份漂亮的 SOLVED.md（GitHub 上的解題清單）。"""
    records = load_json(RECORDS_PATH, {})
    solved = [r for r in records.values() if r.get("solved")]
    solved.sort(key=lambda r: int(r["id"]))

    lines = [
        "# 我的 LeetCode 解題紀錄",
        "",
        f"目前已解出 **{len(solved)}** 題。最後更新："
        f"{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "| # | 題目 | 難度 | 解出時間 | 我的解答 |",
        "|---|------|------|----------|----------|",
    ]
    for r in solved:
        slug = next((s for s, v in records.items() if v is r), None)
        link = f"https://leetcode.com/problems/{slug}/"
        sp = solution_path({"id": r["id"], "slug": slug})
        sol_file = sp.relative_to(ROOT).as_posix()
        sol_link = f"[解答]({sol_file})" if sp.exists() else "—"
        lines.append(
            f"| {r['id']} | [{r['title']}]({link}) | {r['difficulty']} "
            f"| {r.get('solved_at', r.get('solved_via', '—'))} | {sol_link} |"
        )
    lines.append("")
    (ROOT / "SOLVED.md").write_text("\n".join(lines), encoding="utf-8")
    return len(solved)


WORKSPACE_GITIGNORE = """# 絕對不要上傳：你的 LeetCode 登入 cookie
config.json

# 快取與雜物
data/details/
data/_imgcache/
data/problems.json
pdf/
assets/
browser-profile/
.vscode/
data/localrun/
backups/
logs/
mods/
"""


def cmd_push(args):
    """把你的工作區（解題檔、紀錄、遊戲存檔）備份到你自己的 GitHub 倉庫。"""
    # 1) 一定要先有 .gitignore，否則可能把 config.json（登入 cookie）推上去
    gi = ROOT / ".gitignore"
    if not gi.exists():
        gi.write_text(WORKSPACE_GITIGNORE, encoding="utf-8")
    elif "config.json" not in gi.read_text(encoding="utf-8").split():
        sys.exit("❌ 工作區的 .gitignore 沒有排除 config.json，為了安全先不推送。")

    # 2) 還不是 git repo 就初始化
    if not (ROOT / ".git").exists():
        print("📦 初始化 git 倉庫…")
        git("init")
        git("branch", "-M", "main")

    # 3) 保險起見，確保 config.json 沒有被 git 追蹤
    if git_ok("ls-files", "--error-unmatch", "config.json"):
        print("⚠️  config.json 之前被加入追蹤了，現在移除（檔案保留在本機）…")
        git("rm", "--cached", "config.json", check=False, capture=True)

    # 4) 設定遠端：優先用 --repo，其次 config.json 裡的 github_repo
    cfg = load_config()
    repo_url = args.repo or cfg.get("github_repo")
    has_origin = git_ok("remote", "get-url", "origin")
    if repo_url:
        if has_origin:
            git("remote", "set-url", "origin", repo_url)
        else:
            git("remote", "add", "origin", repo_url)
            has_origin = True
        print(f"🔗 遠端 origin → {repo_url}")

    # 5) 產生解題清單並把該追蹤的檔案加進來
    n = generate_solved_md()
    print(f"📝 已更新 SOLVED.md（已解 {n} 題）")
    for path in ["solutions", "data/records.json", "data/game.json", "data/profile.json",
                 "SOLVED.md", ".gitignore"]:
        if (ROOT / path).exists():
            git("add", path)

    # 6) 有變動才 commit
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("ℹ️  沒有新的變動需要提交。")
    else:
        msg = args.message or (
            f"Update LeetCode solutions ({n} solved) "
            f"- {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        git("commit", "-m", msg)
        print(f"✅ 已提交：{msg}")

    # 7) 推上去
    if not has_origin:
        print(
            "\n📌 還沒設定 GitHub 遠端，已先在本機存檔。要推上去，二選一：\n"
            "   (A) 已經有空的 GitHub repo：\n"
            "       python lc.py push --repo https://github.com/你的帳號/倉庫名.git\n"
            "   (B) 用 gh CLI 一鍵建立（需先在終端機執行一次 gh auth login）：\n"
            f"       cd \"{ROOT}\"\n"
            "       gh repo create my-leetcode-solutions --private --source . --remote origin --push"
        )
        return

    print("🚀 推送到 GitHub…")
    result = git("push", "-u", "origin", "HEAD", check=False, capture=True)
    if result.returncode == 0:
        print("🎉 推送成功！你的解題紀錄已經在 GitHub 上了。")
    else:
        err = (result.stderr or "").strip()
        print(f"❌ 推送失敗：\n{err}\n")
        if "Authentication" in err or "could not read" in err or "denied" in err.lower():
            print(
                "看起來是 GitHub 驗證問題。最簡單的解法：在終端機執行一次\n"
                "   gh auth login\n"
                "登入後再跑 python lc.py push 就會通了。"
            )


# ---------------------------------------------------------------------------
# 10. random — 隨機抽一題
# ---------------------------------------------------------------------------
def cmd_random(args):
    problems = get_problems()
    records = load_json(RECORDS_PATH, {})

    pool = []
    for p in problems:
        if not args.paid and p["paidOnly"]:
            continue
        if args.tag and args.tag not in p["tags"]:
            continue
        rec = records.get(p["slug"])
        solved = bool(rec and rec.get("solved"))
        if not args.done and solved:
            continue
        pool.append(p)

    if not pool:
        sys.exit("❌ 沒有符合條件的題目了！可以加 --done（含已解）或 --paid（含付費）放寬條件。")

    p = random.choice(pool)
    print(f"🎲 抽到了！（符合條件的還有 {len(pool)} 題可抽）\n")
    print(f"   {p['id']}. {p['title']}  [{p['difficulty']}]")
    print(f"   通過率 {p['acRate']}%　主題：{', '.join(p['tags']) or '無'}")
    print(f"   {BASE}/problems/{p['slug']}/\n")

    if args.new:
        cmd_new(argparse.Namespace(problem=str(p["id"]), force=False, lang=None))
    else:
        print(f"   下一步：python lc.py show {p['id']}　|　python lc.py new {p['id']}")


# ---------------------------------------------------------------------------
# 9. sync — 從 LeetCode 抓回你的真實進度
# ---------------------------------------------------------------------------
WHOAMI_QUERY = "query { userStatus { username isSignedIn } }"

USER_STATS_QUERY = """
query userProgress($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats: submitStatsGlobal {
      acSubmissionNum { difficulty count }
      totalSubmissionNum { difficulty count }
    }
  }
}
"""

RECENT_AC_QUERY = """
query recentAc($username: String!, $limit: Int!) {
  recentAcSubmissionList(username: $username, limit: $limit) {
    id title titleSlug timestamp
  }
}
"""


def cmd_sync(args):
    session = make_session(require_login=True)

    # 1) 用 cookie 問 LeetCode「我是誰」，順便確認登入有效
    who = graphql(session, WHOAMI_QUERY, {})["userStatus"]
    if not who or not who.get("isSignedIn"):
        sys.exit("❌ 登入資訊無效或已過期，請更新 config.json 裡的 LEETCODE_SESSION / csrftoken。")
    username = who["username"]
    print(f"👤 已登入：{username}")
    c = fetch_contest(username)
    if c and c.get("rating"):
        print(f"🏆 官方競賽分：{round(c['rating'])}（參加 {c['attended']} 場，前 {c.get('topPercentage')}%）")
    update_ratings()

    # 2) 各難度的解題統計
    stats = graphql(session, USER_STATS_QUERY, {"username": username})["matchedUser"]
    ac = {d["difficulty"]: d["count"] for d in stats["submitStats"]["acSubmissionNum"]}
    print(
        f"📊 LeetCode 統計：全部 {ac.get('All', 0)} 題　"
        f"(簡單 {ac.get('Easy', 0)} / 中等 {ac.get('Medium', 0)} / 困難 {ac.get('Hard', 0)})"
    )

    # 3) 掃過題庫，看哪些 status == 'ac'（已解出）
    #    題庫裡有中等/困難題（fetch --all）或加了 --all，就掃全部難度
    known = load_json(PROBLEMS_PATH, [])
    scan_all = getattr(args, "all", False) or any(p.get("difficulty") != "Easy" for p in known)
    filters = {} if scan_all else {"difficulty": "EASY"}
    print("🔄 正在比對" + ("全部難度" if scan_all else "簡單題") + "的完成狀態…")
    solved_easy = {}  # slug -> 題目資料
    skip, page = 0, 50
    while True:
        data = graphql(
            session,
            PROBLEM_LIST_QUERY,
            {"categorySlug": "", "skip": skip, "limit": page, "filters": filters},
        )
        block = data["problemsetQuestionList"]
        questions = block["questions"]
        if not questions:
            break
        for q in questions:
            if q.get("status") == "ac":
                solved_easy[q["titleSlug"]] = q
        skip += page
        if skip >= block["total"]:
            break
        time.sleep(0.3)

    # 4) 把已解狀態寫回 records.json
    records = load_json(RECORDS_PATH, {})
    new_solved = 0
    for slug, q in solved_easy.items():
        rec = records.get(slug)
        if rec is None:
            rec = {
                "id": q["frontendQuestionId"],
                "title": q["title"],
                "difficulty": q["difficulty"],
                "solved": False,
                "attempts": [],
            }
            records[slug] = rec
        if not rec.get("solved"):
            new_solved += 1
        rec["solved"] = True
        rec.setdefault("solved_via", "leetcode-sync")

    # 5) 抓最近的 AC 紀錄，併進每題的 attempts（用 submission id 去重）
    recent = graphql(session, RECENT_AC_QUERY, {"username": username, "limit": 20})
    recent_list = recent.get("recentAcSubmissionList") or []
    added_attempts = 0
    for sub in recent_list:
        slug = sub["titleSlug"]
        rec = records.get(slug)
        if rec is None:
            continue  # 不在掃描範圍內的題目，略過
        sid = int(sub["id"])
        if any(a.get("submission_id") == sid for a in rec["attempts"]):
            continue
        ts = datetime.fromtimestamp(int(sub["timestamp"]))
        rec["attempts"].append(
            {
                "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "Accepted",
                "lang": None,
                "submission_id": sid,
                "accepted": True,
                "source": "leetcode-sync",
            }
        )
        rec["attempts"].sort(key=lambda a: a.get("time", ""))
        added_attempts += 1

    save_json(RECORDS_PATH, records)
    print(
        f"✅ 同步完成！已解 {len(solved_easy)} 題"
        f"（本次新標記 {new_solved} 題），併入最近 AC 紀錄 {added_attempts} 筆。"
    )
    print("   用 python lc.py stats 看整理後的進度，或 python lc.py list --undone 找還沒寫的題目。")


# ---------------------------------------------------------------------------
# 題目難度分與官方競賽分（給遊戲的戰力系統用）
# ---------------------------------------------------------------------------
RATINGS_URL = "https://raw.githubusercontent.com/zerotrac/leetcode_problem_rating/main/ratings.txt"
CONTEST_QUERY = """
query contest($username: String!) {
  userContestRanking(username: $username) {
    attendedContestsCount rating globalRanking topPercentage badge { name }
  }
}
"""


def ratings_path() -> Path:
    return DATA_DIR / "ratings.json"


def load_ratings() -> dict:
    return (load_json(ratings_path(), {}) or {}).get("table", {})


def update_ratings(max_age_days: float = 7) -> int:
    """下載社群題目難度表（zerotrac/leetcode_problem_rating），一週更新一次。回傳題數，失敗回傳 0。"""
    cur = load_json(ratings_path(), {}) or {}
    if cur.get("table") and time.time() - cur.get("fetched", 0) < max_age_days * 86400:
        return len(cur["table"])
    try:
        resp = requests.get(RATINGS_URL, timeout=20)
        resp.raise_for_status()
    except requests.RequestException:
        return len(cur.get("table", {}))
    table = {}
    for line in resp.text.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) >= 5:
            try:
                table[cols[4]] = round(float(cols[0]), 1)
            except ValueError:
                pass
    if table:
        save_json(ratings_path(), {"fetched": time.time(), "source": RATINGS_URL, "table": table})
    return len(table)


def fetch_contest(username: str):
    """抓官方競賽分（公開資料，不用登入）。存到 data/contest.json，失敗回傳 None。"""
    try:
        data = graphql(make_session(), CONTEST_QUERY, {"username": username})
    except (requests.RequestException, RuntimeError):
        return None
    r = data.get("userContestRanking") or {}
    info = {
        "username": username,
        "rating": r.get("rating"),
        "attended": r.get("attendedContestsCount") or 0,
        "globalRanking": r.get("globalRanking"),
        "topPercentage": r.get("topPercentage"),
        "badge": (r.get("badge") or {}).get("name"),
        "fetched": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_json(DATA_DIR / "contest.json", info)
    return info


# ---------------------------------------------------------------------------
# 7. stats — 進度統計
# ---------------------------------------------------------------------------
def cmd_stats(args):
    records = load_json(RECORDS_PATH, {})
    problems = load_json(PROBLEMS_PATH, [])
    total_easy = len(problems)
    solved = [r for r in records.values() if r.get("solved")]
    attempted = len(records)
    total_attempts = sum(len(r.get("attempts", [])) for r in records.values())

    print(f"\n📈 刷題進度")
    print(f"{'-'*40}")
    print(f"   簡單題總數：{total_easy}")
    print(f"   已解出　　：{len(solved)} 題")
    print(f"   嘗試過　　：{attempted} 題")
    print(f"   總提交次數：{total_attempts}")
    if solved:
        print(f"\n   最近解出的題目：")
        recent = sorted(solved, key=lambda r: r.get("solved_at", ""), reverse=True)[:5]
        for r in recent:
            print(f"     ✅ {r['id']}. {r['title']}  ({r.get('solved_at', '')})")
    print()


# ---------------------------------------------------------------------------
# 12. game — 開啟刷題遊戲
# ---------------------------------------------------------------------------
def cmd_game(args):
    from game.server import serve
    serve(port=args.port, open_browser=not args.no_browser)


# ---------------------------------------------------------------------------
# 13. vscode — 安裝 VS Code 任務（Ctrl+Shift+B 提交、打開資料夾自動開遊戲）
# ---------------------------------------------------------------------------
def vscode_tasks() -> dict:
    """依執行方式產生 VS Code 任務：EXE 版呼叫 EXE，原始碼版呼叫 python lc.py。"""
    if FROZEN:
        run = f'"{sys.executable}"'
    else:
        run = f'python "{REPO_DIR / "lc.py"}"'
    shared = {"reveal": "always", "panel": "shared", "clear": True}
    return {
        "version": "2.0.0",
        "tasks": [
            {"label": "🎮 開心刷題：開始遊戲", "type": "shell", "command": f"{run} game",
             "isBackground": True, "problemMatcher": [],
             "presentation": {"reveal": "always", "panel": "dedicated", "focus": False},
             "runOptions": {"runOn": "folderOpen"}},
            {"label": "🚀 出招：提交目前這題", "type": "shell",
             "command": f"{run} submit ${{fileBasenameNoExtension}}",
             "group": {"kind": "build", "isDefault": True}, "problemMatcher": [], "presentation": shared},
            {"label": "🧪 試招：用範例測資試跑目前這題", "type": "shell",
             "command": f"{run} test ${{fileBasenameNoExtension}}",
             "group": {"kind": "test", "isDefault": True}, "problemMatcher": [], "presentation": shared},
            {"label": "🔄 同步官網進度", "type": "shell", "command": f"{run} sync", "problemMatcher": []},
        ],
    }


def install_vscode(force=False, target: Path = None):
    """在工作區（或指定資料夾）安裝 .vscode/tasks.json。回傳寫入的路徑，已存在且不覆蓋時回傳 None。"""
    dst = (target or ROOT) / ".vscode"
    dst.mkdir(parents=True, exist_ok=True)
    # 開啟自動存檔：寫完不用按 Ctrl+S，出招時一定送出最新的程式碼
    sf = dst / "settings.json"
    try:
        settings = load_json(sf, {}) if sf.exists() else {}
    except ValueError:
        settings = None  # 使用者自己寫了含註解的設定，就不動它
    if settings is not None and "files.autoSave" not in settings:
        settings.update({"files.autoSave": "afterDelay", "files.autoSaveDelay": 500})
        save_json(sf, settings)
    f = dst / "tasks.json"
    if f.exists() and not force:
        return None
    save_json(f, vscode_tasks())
    return f


def cmd_vscode(args):
    f = install_vscode(force=args.force)
    if f is None:
        print(f"⚠️  {ROOT / '.vscode' / 'tasks.json'} 已經存在，沒有覆蓋（要覆蓋請加 --force）")
        return
    print(f"✅ 已安裝 {f}")
    print(
        f"\n用 VS Code 打開工作區資料夾：{ROOT}\n"
        "   • VS Code 會問「允許自動任務？」→ 允許，之後打開資料夾就自動啟動遊戲\n"
        "   • 已開啟自動存檔，寫完不用按 Ctrl+S\n"
        "   • Ctrl+Shift+B：提交目前打開的解題檔（出招）\n"
        "   • Ctrl+Shift+P → Tasks: Run Test Task：試跑目前的解題檔（試招）\n"
        "   不想自動啟動：把 .vscode/tasks.json 裡的 \"runOn\": \"folderOpen\" 那行刪掉就好。"
    )


# ---------------------------------------------------------------------------
# 命令列介面
# ---------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        description="開心每日刷題 — LeetCode 簡單題練習工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    pf = sub.add_parser("fetch", help="抓取簡單題清單")
    pf.add_argument("--all", action="store_true", help="抓全部難度（簡單＋中等＋困難），技能樹會長得更完整")

    pl = sub.add_parser("list", help="列出題目與完成狀態")
    pl.add_argument("--undone", action="store_true", help="只看還沒解出的")
    pl.add_argument("--free", action="store_true", help="只看免費題")
    pl.add_argument("--tag", help="只看某個主題標籤，例如 array")
    pl.add_argument("--limit", type=int, help="最多顯示幾題")

    ps = sub.add_parser("show", help="顯示題目敘述")
    ps.add_argument("problem", help="題號或 slug，例如 1 或 two-sum")

    pn = sub.add_parser("new", help="建立解題檔")
    pn.add_argument("problem", help="題號或 slug")
    pn.add_argument("--force", action="store_true", help="覆蓋已存在的檔案")
    pn.add_argument("--lang", choices=list(LANGS), help="解題語言（預設用 config.json 的 lang）")

    pt = sub.add_parser("test", help="用範例測資試跑（預設在自己電腦跑，跑不了才用 LeetCode）")
    pt.add_argument("problem", help="題號或 slug")
    pt.add_argument("--input", help="自訂測資（預設用官方範例）")
    pt.add_argument("--local", action="store_true", help="只在自己電腦跑")
    pt.add_argument("--online", action="store_true", help="只用 LeetCode 線上試跑")

    psub = sub.add_parser("submit", help="正式提交到 LeetCode 判題")
    psub.add_argument("problem", help="題號或 slug")

    pp = sub.add_parser("pdf", help="把題目匯出成 PDF（排版乾淨、不跑版）")
    pp.add_argument("problem", nargs="*", help="一或多個題號 / slug，例如 1 9 two-sum")
    pp.add_argument("--range", help="連續題號範圍，例如 1-20")
    pp.add_argument("--out", help="輸出檔名（預設放在 pdf/ 資料夾）")

    pr = sub.add_parser("random", help="隨機抽一題（預設：免費且還沒解過）")
    pr.add_argument("--tag", help="限定主題，例如 array")
    pr.add_argument("--paid", action="store_true", help="也納入付費題")
    pr.add_argument("--done", action="store_true", help="也納入已解過的題")
    pr.add_argument("--new", action="store_true", help="抽完直接建立解題檔")

    psy = sub.add_parser("sync", help="從 LeetCode 抓回你的真實進度（需登入）")
    psy.add_argument("--all", action="store_true", help="掃描全部難度（題庫有中等/困難題時會自動開啟）")

    pg = sub.add_parser("push", help="把你的工作區（解題檔、紀錄、存檔）備份到你自己的 GitHub 倉庫")
    pg.add_argument("--repo", help="你的個人備份倉庫網址（第一次設定用）")
    pg.add_argument("-m", "--message", help="自訂 commit 訊息")

    sub.add_parser("stats", help="看刷題進度")

    pgm = sub.add_parser("game", help="🎮 開啟刷題遊戲（技能樹、戰力、肉鴿遠征）")
    pgm.add_argument("--port", type=int, default=8765, help="本機埠號（預設 8765）")
    pgm.add_argument("--no-browser", action="store_true", help="不要自動開瀏覽器")

    pvs = sub.add_parser("vscode", help="在工作區安裝 VS Code 任務（Ctrl+Shift+B 提交、自動開遊戲）")
    pvs.add_argument("--force", action="store_true", help="覆蓋已存在的設定")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    handlers = {
        "fetch": cmd_fetch,
        "list": cmd_list,
        "show": cmd_show,
        "new": cmd_new,
        "test": cmd_test,
        "submit": cmd_submit,
        "pdf": cmd_pdf,
        "random": cmd_random,
        "sync": cmd_sync,
        "push": cmd_push,
        "stats": cmd_stats,
        "game": cmd_game,
        "vscode": cmd_vscode,
    }
    ensure_home()
    if not args.command:
        parser.print_help()
        print(f"\n工作區：{ROOT}")
        return
    try:
        handlers[args.command](args)
    except requests.RequestException as e:
        sys.exit(f"❌ 網路錯誤：{e}")
    except KeyboardInterrupt:
        sys.exit("\n已取消。")


if __name__ == "__main__":
    main()
