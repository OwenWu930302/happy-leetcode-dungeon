# -*- coding: utf-8 -*-
"""
遊戲的演算法核心（純函式，不碰網路、不碰檔案）
================================================

1. build_tree()     依題庫的 LeetCode 標籤自動長出技能樹（DAG）
                    - 已知標籤：用手寫的前置關係
                    - 新標籤：用「共現機率」推斷前置技能，保證不會產生環
                    - Kahn 拓撲排序算層數，重心法（barycenter）排版減少交叉
2. compute_power()  類 Elo 戰力：依提交紀錄逐筆更新總戰力與各技能戰力
3. recommend()      依戰力與技能弱點，替每題打分，挑出「剛好打得贏」的題目
"""

import math
import random
from collections import defaultdict

# ---------------------------------------------------------------------------
# 標籤資料：中文名稱、圖示字、手寫前置關係
# ---------------------------------------------------------------------------
TAG_INFO = {
    # slug: (中文名, 圖示字, [前置標籤])
    "array": ("陣列", "陣", []),
    "string": ("字串", "字", ["array"]),
    "hash-table": ("雜湊表", "雜", ["array"]),
    "math": ("數學", "數", []),
    "sorting": ("排序", "排", ["array"]),
    "simulation": ("模擬", "模", ["array"]),
    "enumeration": ("枚舉", "枚", ["array"]),
    "matrix": ("矩陣", "矩", ["array"]),
    "prefix-sum": ("前綴和", "前", ["array"]),
    "counting": ("計數", "計", ["hash-table"]),
    "two-pointers": ("雙指標", "雙", ["array"]),
    "stack": ("堆疊", "疊", ["array"]),
    "queue": ("佇列", "列", ["array"]),
    "bit-manipulation": ("位元操作", "位", ["math"]),
    "greedy": ("貪婪", "貪", ["sorting"]),
    "binary-search": ("二分搜尋", "分", ["sorting"]),
    "sliding-window": ("滑動視窗", "窗", ["two-pointers", "hash-table"]),
    "linked-list": ("鏈結串列", "鏈", ["two-pointers"]),
    "doubly-linked-list": ("雙向鏈結", "鍊", ["linked-list"]),
    "recursion": ("遞迴", "遞", ["stack"]),
    "tree": ("樹", "樹", ["recursion"]),
    "binary-tree": ("二元樹", "枝", ["tree"]),
    "binary-search-tree": ("二元搜尋樹", "搜", ["binary-tree", "binary-search"]),
    "depth-first-search": ("深度優先", "深", ["recursion"]),
    "breadth-first-search": ("廣度優先", "廣", ["queue"]),
    "heap-priority-queue": ("堆積", "堆", ["binary-tree"]),
    "trie": ("字典樹", "典", ["tree", "string"]),
    "backtracking": ("回溯", "溯", ["recursion"]),
    "divide-and-conquer": ("分治", "治", ["recursion"]),
    "memoization": ("記憶化", "憶", ["recursion"]),
    "dynamic-programming": ("動態規劃", "規", ["memoization"]),
    "graph": ("圖論", "圖", ["depth-first-search", "breadth-first-search"]),
    "topological-sort": ("拓撲排序", "拓", ["graph"]),
    "union-find": ("並查集", "併", ["graph"]),
    "shortest-path": ("最短路徑", "徑", ["graph", "heap-priority-queue"]),
    "minimum-spanning-tree": ("最小生成樹", "生", ["union-find"]),
    "monotonic-stack": ("單調堆疊", "單", ["stack"]),
    "monotonic-queue": ("單調佇列", "調", ["queue", "sliding-window"]),
    "number-theory": ("數論", "論", ["math"]),
    "combinatorics": ("組合數學", "組", ["math"]),
    "geometry": ("幾何", "幾", ["math"]),
    "probability-and-statistics": ("機率統計", "機", ["math"]),
    "randomized": ("隨機化", "隨", ["math"]),
    "brainteaser": ("腦筋急轉彎", "腦", ["math"]),
    "game-theory": ("賽局", "賽", ["dynamic-programming"]),
    "bitmask": ("狀態壓縮", "壓", ["bit-manipulation", "dynamic-programming"]),
    "string-matching": ("字串匹配", "匹", ["string"]),
    "hash-function": ("雜湊函數", "函", ["hash-table"]),
    "rolling-hash": ("滾動雜湊", "滾", ["string-matching", "hash-function"]),
    "suffix-array": ("後綴陣列", "綴", ["string-matching"]),
    "design": ("設計", "設", ["hash-table"]),
    "data-stream": ("資料流", "流", ["design"]),
    "iterator": ("迭代器", "迭", ["design"]),
    "interactive": ("互動題", "互", ["binary-search"]),
    "segment-tree": ("線段樹", "線", ["divide-and-conquer"]),
    "binary-indexed-tree": ("樹狀陣列", "狀", ["prefix-sum"]),
    "ordered-set": ("有序集合", "序", ["binary-search-tree"]),
    "counting-sort": ("計數排序", "桶", ["sorting", "counting"]),
    "bucket-sort": ("桶排序", "斗", ["sorting"]),
    "radix-sort": ("基數排序", "基", ["sorting"]),
    "merge-sort": ("合併排序", "合", ["sorting", "divide-and-conquer"]),
    "quickselect": ("快速選擇", "快", ["sorting", "divide-and-conquer"]),
    "line-sweep": ("掃描線", "掃", ["sorting"]),
    "strongly-connected-component": ("強連通分量", "強", ["graph"]),
    "biconnected-component": ("雙連通分量", "連", ["graph"]),
    "eulerian-circuit": ("歐拉迴路", "歐", ["graph"]),
    "reservoir-sampling": ("蓄水池抽樣", "池", ["randomized"]),
    "rejection-sampling": ("拒絕抽樣", "拒", ["randomized"]),
}

# 不是 Python 演算法題（要寫 SQL / Bash / 多執行緒），不放進技能樹與推薦
EXCLUDED_TAGS = {"database", "shell", "concurrency"}

DIFF_BASE = {"Easy": 1150, "Medium": 1550, "Hard": 1950}
DIFF_PTS = {"Easy": 1, "Medium": 2, "Hard": 3}
DIFF_XP = {"Easy": 10, "Medium": 25, "Hard": 50}

# 技能等級門檻（加權解題分數：簡單 1、中等 2、困難 3）
LEVEL_STEPS = [2, 5, 9, 14, 20]

RANKS = [
    (0, "青銅"), (1100, "白銀"), (1300, "黃金"), (1500, "白金"),
    (1700, "鑽石"), (1900, "大師"), (2100, "傳說"),
]


def playable(p):
    """這題能不能拿來玩：免費、而且不是 SQL / Bash / 多執行緒題。"""
    return not p.get("paidOnly") and not (set(p.get("tags", [])) & EXCLUDED_TAGS)


def problem_rating(p):
    """估計題目難度分：官方難度定基準，通過率越低越難。"""
    base = DIFF_BASE.get(p.get("difficulty"), 1300)
    ac = p.get("acRate") or 50
    return int(round(base + (50 - ac) * 10))


def rank_of(rating):
    name = RANKS[0][1]
    for lo, n in RANKS:
        if rating >= lo:
            name = n
    return name


# ---------------------------------------------------------------------------
# 1. 技能樹
# ---------------------------------------------------------------------------
def kahn_topo(nodes, parents):
    """Kahn 拓撲排序。回傳 (順序, 層數)；層數 = 最長前置鏈長度。有環就丟例外。"""
    indeg = {n: len(parents[n]) for n in nodes}
    children = defaultdict(list)
    for n in nodes:
        for p in parents[n]:
            children[p].append(n)
    queue = sorted([n for n in nodes if indeg[n] == 0])
    layer = {n: 0 for n in queue}
    order, head = [], 0
    while head < len(queue):
        u = queue[head]
        head += 1
        order.append(u)
        for v in sorted(children[u]):
            layer[v] = max(layer.get(v, 0), layer[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    if len(order) != len(nodes):
        raise ValueError("技能樹出現環，無法拓撲排序")
    return order, layer, children


def _infer_parents(tag, present, tag_problems, freq):
    """新標籤的前置技能：挑「比它常見」且「一起出現機率最高」的 1~2 個標籤。

    只連向出現次數更多的標籤 → 邊永遠從常見指向罕見，一定不會有環。
    """
    mine = tag_problems[tag]
    scored = []
    for other in present:
        if other == tag:
            continue
        if (freq[other], other) <= (freq[tag], tag):
            continue
        both = len(mine & tag_problems[other])
        if both:
            scored.append((both / len(mine), freq[other], other))
    scored.sort(reverse=True)
    picked = [o for conf, _, o in scored[:2] if conf >= 0.2]
    if not picked and scored:
        picked = [scored[0][2]]
    return picked


def _resolve_known_parents(tag, present, seen=None):
    """手寫前置關係裡，前置標籤不在題庫時，往上找最近的、存在的祖先。"""
    seen = seen or set()
    out = []
    for p in TAG_INFO.get(tag, ("", "", []))[2]:
        if p in seen:
            continue
        if p in present:
            out.append(p)
        else:
            out.extend(_resolve_known_parents(p, present, seen | {p}))
    return sorted(set(out))


def build_tree(problems, records):
    """自動生成技能樹。題庫裡出現任何新標籤，都會自動長出新節點。"""
    solved = {slug for slug, r in records.items() if r.get("solved")}
    tag_problems = defaultdict(set)
    by_slug = {}
    for p in problems:
        if not playable(p):
            continue
        by_slug[p["slug"]] = p
        for t in p.get("tags", []):
            tag_problems[t].add(p["slug"])
    # 也把「已解但不在題庫」的題目算進來（例如 sync 抓回來的中等題）
    present = set(tag_problems)
    freq = {t: len(s) for t, s in tag_problems.items()}

    parents, inferred = {}, set()
    # 依出現次數由多到少處理，推斷新標籤時，比它常見的節點都已就位
    for t in sorted(present, key=lambda x: (-freq[x], x)):
        if t in TAG_INFO:
            parents[t] = _resolve_known_parents(t, present)
        else:
            parents[t] = _infer_parents(t, present, tag_problems, freq)
            inferred.add(t)

    order, layer, children = kahn_topo(sorted(present), parents)

    # --- 重心法排版：每層依「父節點平均位置」排序，來回掃兩次減少交叉 ---
    layers = defaultdict(list)
    for n in order:
        layers[layer[n]].append(n)
    for L in layers:
        layers[L].sort(key=lambda n: (-freq[n], n))
    pos = {}

    def assign(L):
        for i, n in enumerate(layers[L]):
            pos[n] = (i + 0.5) / len(layers[L])

    assign(0)
    for _ in range(2):
        for L in sorted(layers)[1:]:
            layers[L].sort(key=lambda n: sum(pos[p] for p in parents[n]) / max(1, len(parents[n])))
            assign(L)
        for L in sorted(layers, reverse=True)[1:]:
            kids = lambda n: [c for c in children[n] if c in pos]
            layers[L].sort(key=lambda n: (sum(pos[c] for c in kids(n)) / len(kids(n))) if kids(n) else pos[n])
            assign(L)

    # --- 依拓撲序做 DP：前置都點亮才解鎖，解題分數決定等級 ---
    nodes, state = [], {}
    for t in order:
        slugs = tag_problems[t]
        done = slugs & solved
        pts = sum(DIFF_PTS.get(by_slug[s]["difficulty"], 1) for s in done)
        lv = sum(1 for step in LEVEL_STEPS if pts >= step)
        unlocked = all(state[p]["lit"] for p in parents[t])
        lit = unlocked and lv >= 1
        st = "lock" if not unlocked else ("max" if lv >= 5 else "lit" if lit else "part" if pts else "open")
        state[t] = {"lit": lit, "unlocked": unlocked}
        name, glyph, _ = TAG_INFO.get(t, (t.replace("-", " ").title(), t[:1].upper(), []))
        nxt = next((s for s in LEVEL_STEPS if pts < s), None)
        nodes.append({
            "id": t, "name": name, "glyph": glyph, "parents": parents[t],
            "layer": layer[t], "x": round(pos[t], 4), "inferred": t in inferred,
            "total": len(slugs), "solved": len(done), "pts": pts, "level": lv,
            "next": nxt, "state": st, "unlocked": unlocked, "lit": lit,
        })
    return {"nodes": nodes, "order": order, "layers": max(layer.values()) + 1 if layer else 0}


# ---------------------------------------------------------------------------
# 2. 戰力（類 Elo）
# ---------------------------------------------------------------------------
def _events(problems_by_slug, records):
    """把提交紀錄攤平成時間序列的 (時間, 題目, 是否通過)。"""
    evs = []
    for slug, r in records.items():
        p = problems_by_slug.get(slug) or {
            "slug": slug, "difficulty": r.get("difficulty", "Easy"), "acRate": 50, "tags": [],
        }
        atts = r.get("attempts") or []
        for a in atts:
            evs.append((a.get("time") or "", p, bool(a.get("accepted"))))
        if r.get("solved") and not any(a.get("accepted") for a in atts):
            evs.append(("", p, True))  # sync 抓回來、沒有提交細節的已解題
    evs.sort(key=lambda e: e[0])
    return evs


def _elo(events, start=1000.0):
    R, n = start, 0
    for _, p, win in events:
        pr = problem_rating(p)
        expect = 1 / (1 + 10 ** ((pr - R) / 400))
        k = 48 if n < 15 else 32 if n < 50 else 20
        R += k * ((1 if win else 0) - expect)
        n += 1
    return R, n


def compute_power(problems, records):
    by_slug = {p["slug"]: p for p in problems}
    evs = _events(by_slug, records)
    R, n = _elo(evs)
    per_tag = {}
    tags = defaultdict(list)
    for e in evs:
        for t in e[1].get("tags", []):
            if t not in EXCLUDED_TAGS:
                tags[t].append(e)
    for t, es in tags.items():
        # 該技能的「超額表現」：實際勝率減去以總戰力預估的勝率，樣本少時打折
        resid = 0.0
        for _, p, win in es:
            expect = 1 / (1 + 10 ** ((problem_rating(p) - R) / 400))
            resid += (1 if win else 0) - expect
        tn = len(es)
        shrink = tn / (tn + 3)
        per_tag[t] = {
            "rating": int(round(R + 400 * (resid / tn) * shrink)),
            "events": tn,
            "wins": sum(1 for e in es if e[2]),
        }
    solved = [s for s, r in records.items() if r.get("solved")]
    xp = sum(DIFF_XP.get((by_slug.get(s) or records[s]).get("difficulty", "Easy"), 10) for s in solved)
    wins = sum(1 for e in evs if e[2])
    return {
        "rating": int(round(R)), "rank": rank_of(R), "events": n,
        "wins": wins, "accuracy": round(wins / n * 100) if n else 0,
        "solved": len(solved), "xp": xp, "per_tag": per_tag,
    }


# ---------------------------------------------------------------------------
# 3. 推薦
# ---------------------------------------------------------------------------
def score_problem(p, rating, tree_by_id, per_tag, offset=80, width=180):
    pr = problem_rating(p)
    target = rating + offset
    fit = math.exp(-((pr - target) / width) ** 2)
    bonus, why = 0.0, []
    for t in p.get("tags", []):
        node = tree_by_id.get(t)
        if not node:
            continue
        if node["unlocked"] and node["level"] < 2:
            bonus += 0.6
            why.append(("frontier", t))
        elif not node["unlocked"]:
            bonus -= 0.25
        tr = per_tag.get(t, {}).get("rating")
        if tr is not None and tr < rating - 30:
            bonus += min(0.6, (rating - tr) / 300)
            why.append(("weak", t))
    return fit * (1 + max(-0.5, bonus)), pr, why


def explain(p, pr, rating, why, tree_by_id):
    diff = pr - rating
    lines = []
    for kind, t in why:
        if kind == "frontier":
            node = tree_by_id[t]
            if node["level"] == 0:
                lines.append(f"解掉它就能點亮「{node['name']}」")
            else:
                lines.append(f"「{node['name']}」Lv{node['level']}，這題幫你往 Lv{node['level'] + 1} 推進")
            break
    for kind, t in why:
        if kind == "weak":
            lines.append(f"你的「{tree_by_id[t]['name']}」戰力比平均低，補一下")
            break
    if diff > 120:
        lines.append(f"難度 {pr}，比你高 {diff}，打贏會大漲戰力")
    elif diff > -60:
        lines.append(f"難度 {pr}，跟你的戰力 {rating} 剛好勢均力敵")
    else:
        lines.append(f"難度 {pr}，輕鬆拿經驗")
    return lines[:2]


def recommend(problems, records, tree, power, k=5, offset=80, width=180,
              exclude=(), seen=(), tag=None, seed=None):
    """挑出 k 題推薦。高分題機率高，但保留隨機性，每次推的不一樣。"""
    rng = random.Random(seed)
    solved = {s for s, r in records.items() if r.get("solved")}
    tree_by_id = {n["id"]: n for n in tree["nodes"]}
    rating, per_tag = power["rating"], power["per_tag"]
    seen = list(seen)
    cands = []
    for p in problems:
        if not playable(p) or p["slug"] in solved or p["slug"] in exclude:
            continue
        if tag and tag not in p.get("tags", []):
            continue
        s, pr, why = score_problem(p, rating, tree_by_id, per_tag, offset, width)
        if p["slug"] in seen:
            s *= 0.3
        cands.append((s, p, pr, why))
    cands.sort(key=lambda c: -c[0])
    pool = cands[: max(k * 6, 20)]
    picked = []
    while pool and len(picked) < k:
        weights = [c[0] ** 2 + 1e-9 for c in pool]
        i = rng.choices(range(len(pool)), weights=weights)[0]
        picked.append(pool.pop(i))
    out = []
    for s, p, pr, why in picked:
        out.append({
            "slug": p["slug"], "id": p["id"], "title": p["title"],
            "difficulty": p["difficulty"], "acRate": p.get("acRate"),
            "tags": [t for t in p.get("tags", []) if t in tree_by_id],
            "tagNames": [tree_by_id[t]["name"] for t in p.get("tags", []) if t in tree_by_id],
            "rating": pr, "score": round(s, 3), "xp": DIFF_XP.get(p["difficulty"], 10),
            "reasons": explain(p, pr, rating, why, tree_by_id),
        })
    return out
