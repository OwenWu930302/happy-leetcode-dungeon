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
import random
import re
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
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
SOLUTIONS_DIR = ROOT / "solutions"
CONFIG_PATH = ROOT / "config.json"
PROBLEMS_PATH = DATA_DIR / "problems.json"
RECORDS_PATH = DATA_DIR / "records.json"

BASE = "https://leetcode.com"
GRAPHQL = f"{BASE}/graphql"

# 解題檔裡用來分隔「設定」與「你的程式碼」的標記
META_END = "# === 以下是你的程式碼 (YOUR CODE BELOW) ==="


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
        sys.exit(
            "❌ 這個動作需要登入資訊。\n"
            "   請建立 config.json，填入 LeetCode 的 csrftoken 與 LEETCODE_SESSION。\n"
            "   詳細步驟請看 README.md。"
        )
    return s


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
    m = re.match(r"^0*(\d+)-([a-z0-9-]+?)(\.py)?$", key)
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
def solution_path(p: dict) -> Path:
    return SOLUTIONS_DIR / f"{int(p['id']):04d}-{p['slug']}.py"


def get_python_snippet(q: dict) -> str:
    for snip in q["codeSnippets"]:
        if snip["langSlug"] == "python3":
            return snip["code"]
    # 萬一沒有 python3，退而求其次
    return q["codeSnippets"][0]["code"] if q["codeSnippets"] else ""


def create_solution(p: dict, force: bool = False):
    """建立解題檔。回傳 (路徑, 是否新建)。已存在且沒有 force 就不動它。"""
    q = fetch_question_detail(p["slug"])
    path = solution_path(p)
    if path.exists() and not force:
        return path, False

    snippet = get_python_snippet(q)
    header = (
        f"# {q['questionFrontendId']}. {q['title']}  [{q['difficulty']}]\n"
        f"# {BASE}/problems/{p['slug']}/\n"
        f"#\n"
        f"# meta-slug: {p['slug']}\n"
        f"# meta-qid: {q['questionId']}\n"
        f"# meta-lang: python3\n"
        f"#\n"
        f"# 提示：可先用 `python lc.py show {p['id']}` 看完整題目。\n"
        f"# 寫完後用 `python lc.py test {p['id']}` 試跑、`python lc.py submit {p['id']}` 提交。\n"
        f"# 🎮 遊戲模式：在遊戲畫面按「試招／出招」，或在 VS Code 按 Ctrl+Shift+B 直接提交這個檔案。\n"
        f"{META_END}\n"
    )
    SOLUTIONS_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + snippet + "\n")
    return path, True


def cmd_new(args):
    p = find_problem(args.problem)
    path, created = create_solution(p, force=args.force)
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
        m = re.match(r"#\s*meta-(\w+):\s*(.+)", line)
        if m:
            meta[m.group(1)] = m.group(2).strip()

    if META_END in raw:
        code = raw.split(META_END, 1)[1].lstrip("\n")
    else:
        code = raw  # 沒有標記就整份送

    qid = meta.get("qid") or p.get("questionId")
    lang = meta.get("lang", "python3")
    if not code.strip():
        sys.exit("❌ 你的程式碼是空的，先寫點東西再提交吧 :)")
    return qid, lang, code, path


def poll_check(session: requests.Session, check_id: str, slug: str) -> dict:
    """輪詢判題結果，直到完成。"""
    url = f"{BASE}/submissions/detail/{check_id}/check/"
    headers = {"Referer": f"{BASE}/problems/{slug}/"}
    for _ in range(60):  # 最多等約 60 秒
        resp = session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if result.get("state") == "SUCCESS":
            return result
        print("   …判題中", end="\r")
        time.sleep(1)
    sys.exit("❌ 等太久了，判題逾時。請稍後再試。")


# ---------------------------------------------------------------------------
# 5. test — 用範例測資線上試跑（interpret，不算正式提交）
# ---------------------------------------------------------------------------
def run_test(p: dict, data_input=None) -> dict:
    """線上試跑，回傳 LeetCode 的判題結果（dict）。"""
    q = fetch_question_detail(p["slug"])
    qid, lang, code, _ = read_solution(p)
    session = make_session(require_login=True)
    data_input = data_input if data_input else q["exampleTestcases"]
    resp = session.post(
        f"{BASE}/problems/{p['slug']}/interpret_solution/",
        json={"lang": lang, "question_id": qid, "typed_code": code, "data_input": data_input},
        headers={"Referer": f"{BASE}/problems/{p['slug']}/"},
        timeout=30,
    )
    if resp.status_code == 403:
        sys.exit("❌ 被拒絕（403）。多半是登入資訊過期了，請更新 config.json。")
    resp.raise_for_status()
    interpret_id = resp.json().get("interpret_id")
    if not interpret_id:
        sys.exit(f"❌ 試跑失敗：{resp.text}")
    result = poll_check(session, interpret_id, p["slug"])
    result["_input"] = data_input
    return result


def cmd_test(args):
    p = find_problem(args.problem)
    q = fetch_question_detail(p["slug"])
    data_input = args.input if args.input else q["exampleTestcases"]
    print(f"🧪 用範例測資試跑第 {p['id']} 題（{p['title']}）…")
    print(f"   測資：\n{data_input}\n")
    result = run_test(p, data_input)
    print(" " * 30, end="\r")
    _print_run_result(result, is_test=True)


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
    resp = session.post(
        f"{BASE}/problems/{p['slug']}/submit/",
        json={"lang": lang, "question_id": qid, "typed_code": code},
        headers={"Referer": f"{BASE}/problems/{p['slug']}/"},
        timeout=30,
    )
    if resp.status_code == 403:
        sys.exit("❌ 被拒絕（403）。多半是登入資訊過期了，請更新 config.json。")
    resp.raise_for_status()
    submission_id = resp.json().get("submission_id")
    if not submission_id:
        sys.exit(f"❌ 提交失敗：{resp.text}")

    result = poll_check(session, str(submission_id), p["slug"])
    accepted = result.get("status_msg") == "Accepted"
    record_submission(p, lang, submission_id, result, accepted)
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


def record_submission(p, lang, submission_id, result, accepted):
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
        f"目前已解出 **{len(solved)}** 題簡單題。最後更新："
        f"{datetime.now().strftime('%Y-%m-%d')}",
        "",
        "| # | 題目 | 難度 | 解出時間 | 我的解答 |",
        "|---|------|------|----------|----------|",
    ]
    for r in solved:
        slug = next((s for s, v in records.items() if v is r), None)
        link = f"https://leetcode.com/problems/{slug}/"
        sol_file = f"solutions/{int(r['id']):04d}-{slug}.py"
        sol_link = f"[解答]({sol_file})" if (ROOT / sol_file).exists() else "—"
        lines.append(
            f"| {r['id']} | [{r['title']}]({link}) | {r['difficulty']} "
            f"| {r.get('solved_at', r.get('solved_via', '—'))} | {sol_link} |"
        )
    lines.append("")
    (ROOT / "SOLVED.md").write_text("\n".join(lines), encoding="utf-8")
    return len(solved)


def cmd_push(args):
    # 1) 一定要先有 .gitignore，否則可能把 config.json（登入 cookie）推上去
    if not (ROOT / ".gitignore").exists():
        sys.exit("❌ 找不到 .gitignore。為了安全請先建立它（至少要忽略 config.json）。")

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
    for path in ["solutions", "data/records.json", "data/problems.json", "data/game.json",
                 "game", "SOLVED.md", "README.md", "lc.py", "requirements.txt",
                 "config.example.json", ".gitignore"]:
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
            "       gh repo create leetcode-practice --public --source . --remote origin --push"
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
        cmd_new(argparse.Namespace(problem=str(p["id"]), force=False))
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
def cmd_vscode(args):
    import shutil
    src = ROOT / "game" / "vscode"
    dst = ROOT / ".vscode"
    dst.mkdir(exist_ok=True)
    for name in ("tasks.json", "extensions.json"):
        target = dst / name
        if target.exists() and not args.force:
            print(f"⚠️  {target} 已經存在，沒有覆蓋（要覆蓋請加 --force）")
            continue
        shutil.copyfile(src / name, target)
        print(f"✅ 已安裝 {target}")
    print(
        "\n裝好了！重新打開這個資料夾後：\n"
        "   • VS Code 會問「允許自動任務？」→ 允許，之後打開資料夾就自動啟動遊戲\n"
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

    pt = sub.add_parser("test", help="用範例測資線上試跑（不算正式提交）")
    pt.add_argument("problem", help="題號或 slug")
    pt.add_argument("--input", help="自訂測資（預設用官方範例）")

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

    pg = sub.add_parser("push", help="把解過的題目推上 GitHub")
    pg.add_argument("--repo", help="GitHub 倉庫網址（第一次設定用）")
    pg.add_argument("-m", "--message", help="自訂 commit 訊息")

    sub.add_parser("stats", help="看刷題進度")

    pgm = sub.add_parser("game", help="🎮 開啟刷題遊戲（技能樹、戰力、肉鴿遠征）")
    pgm.add_argument("--port", type=int, default=8765, help="本機埠號（預設 8765）")
    pgm.add_argument("--no-browser", action="store_true", help="不要自動開瀏覽器")

    pvs = sub.add_parser("vscode", help="安裝 VS Code 任務（Ctrl+Shift+B 提交、自動開遊戲）")
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
    if not args.command:
        parser.print_help()
        return
    try:
        handlers[args.command](args)
    except requests.RequestException as e:
        sys.exit(f"❌ 網路錯誤：{e}")
    except KeyboardInterrupt:
        sys.exit("\n已取消。")


if __name__ == "__main__":
    main()
