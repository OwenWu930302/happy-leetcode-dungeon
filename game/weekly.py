"""週報：一週解了幾題、實力分變化、新點亮的技能、最弱的標籤、最常犯的錯，加上下週建議。

週的範圍是週一 00:00 到下週一 00:00。每週第一次開遊戲時，跳出「上週」的週報。
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from game import engine

DIFF_ZH = {"Easy": "簡單", "Medium": "中等", "Hard": "困難"}


def week_start(d: date | None = None) -> date:
    d = d or date.today()
    return d - timedelta(days=d.weekday())


def week_key(d: date | None = None) -> str:
    y, w, _ = (d or date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def as_of(records: dict, cutoff: str) -> dict:
    """某個時間點以前的紀錄（cutoff 是 'YYYY-MM-DD HH:MM:SS' 字串）。"""
    out = {}
    for slug, r in records.items():
        atts = [a for a in r.get("attempts", []) if (a.get("time") or "") < cutoff]
        dated_ac = any(a.get("accepted") and a.get("time") for a in r.get("attempts", []))
        # 從官網同步、沒有時間的已解題：當作很久以前就解了
        solved = any(a.get("accepted") for a in atts) or (
            bool(r.get("solved")) and not dated_ac and (r.get("solved_at") or "") < cutoff)
        if not atts and not solved:
            continue
        out[slug] = {**r, "attempts": atts, "solved": solved}
    return out


def report(problems: list, records: dict, mistakes_items: list, start: date | None = None) -> dict:
    start = start or week_start()
    end = start + timedelta(days=7)
    s, e = f"{start:%Y-%m-%d} 00:00:00", f"{end:%Y-%m-%d} 00:00:00"
    before, after = as_of(records, s), as_of(records, e)
    by_slug = {p["slug"]: p for p in problems}

    solved, attempts, accepted, days = [], 0, 0, set()
    for slug, r in records.items():
        win = [a for a in r.get("attempts", []) if s <= (a.get("time") or "") < e]
        attempts += len(win)
        accepted += sum(1 for a in win if a.get("accepted"))
        days.update(a["time"][:10] for a in win)
        if after.get(slug, {}).get("solved") and not before.get(slug, {}).get("solved"):
            p = by_slug.get(slug, {})
            solved.append({"slug": slug, "id": p.get("id") or r.get("id"), "title": p.get("title") or r.get("title"),
                           "difficulty": p.get("difficulty") or r.get("difficulty"),
                           "rating": engine.problem_rating(p) if p else None})
    solved.sort(key=lambda x: -(x["rating"] or 0))

    pw0 = engine.compute_power(problems, before)
    pw1 = engine.compute_power(problems, after)
    lit0 = {n["id"] for n in engine.build_tree(problems, before)["nodes"] if n["lit"]}
    tree1 = engine.build_tree(problems, after)
    lit_new = [n["name"] for n in tree1["nodes"] if n["lit"] and n["id"] not in lit0]
    names = {n["id"]: n["name"] for n in tree1["nodes"]}

    weak = sorted(((t, v) for t, v in pw1["per_tag"].items() if v["events"] >= 1 and t in names),
                  key=lambda tv: tv[1]["rating"])[:3]
    week_m = [m for m in mistakes_items if s <= m.get("time", "") < e]
    causes = Counter(m["cause"] for m in week_m if m.get("cause")).most_common(3)
    by_diff = Counter(x["difficulty"] for x in solved)

    tips = []
    if not attempts:
        tips.append("這週還沒開張。先從一題簡單題暖身，連續天數就會開始累積。")
    if weak:
        tips.append(f"最弱的是「{names[weak[0][0]]}」（實力分 {weak[0][1]['rating']}），下週挑 2–3 題這個標籤的題目。")
    if causes:
        tips.append(f"最常犯的錯是「{causes[0][0]}」，出招前先用自訂測資試試極端情況。")
    elif week_m:
        tips.append(f"這週有 {len(week_m)} 筆錯題還沒標錯因，到錯題本標一下，下次比較容易避開。")
    if attempts and accepted / attempts < 0.5:
        tips.append("通過率不到一半：出招前多按幾次「試招」，本地試跑幾乎不用等。")
    if by_diff.get("Medium", 0) + by_diff.get("Hard", 0) == 0 and len(solved) >= 3:
        tips.append("這週都是簡單題，下週試著挑一題中等題吧。")

    return {
        "week": week_key(start), "start": f"{start:%Y-%m-%d}", "end": f"{end - timedelta(days=1):%Y-%m-%d}",
        "solved": solved[:30], "solvedCount": len(solved),
        "byDiff": {DIFF_ZH.get(k, k): v for k, v in by_diff.items()},
        "attempts": attempts, "accepted": accepted,
        "accuracy": round(accepted / attempts * 100) if attempts else None,
        "activeDays": len(days),
        "ratingFrom": pw0["rating"], "ratingTo": pw1["rating"], "rankTo": pw1["rank"],
        "powerFrom": pw0["power"], "powerTo": pw1["power"],
        "litNew": lit_new,
        "weak": [{"tag": t, "name": names.get(t, t), "rating": v["rating"]} for t, v in weak],
        "mistakes": len(week_m), "causes": [{"cause": c, "n": n} for c, n in causes],
        "tips": tips[:3],
    }
