# -*- coding: utf-8 -*-
"""
遊戲的演算法核心（純函式，不碰網路、不碰檔案）
================================================

1. build_tree()     依題庫的 LeetCode 標籤自動長出技能樹（DAG）
                    - 已知標籤：用手寫的前置關係
                    - 新標籤：用「共現機率」推斷前置技能，保證不會產生環
                    - Kahn 拓撲排序算層數，重心法（barycenter）排版減少交叉
2. compute_power()  實力分（看解過最難的幾題）、段位、戰力、各技能實力
3. recommend()      依實力分與技能弱點，替每題打分，挑出「剛好打得贏」的題目
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

DIFF_PTS = {"Easy": 1, "Medium": 2, "Hard": 3}
DIFF_XP = {"Easy": 10, "Medium": 25, "Hard": 50}

# 技能等級門檻（加權解題分數：簡單 1、中等 2、困難 3）
LEVEL_STEPS = [2, 5, 9, 14, 20]

# 段位：跟 LeetCode 競賽分同一個尺度（Knight 約 1850、Guardian 約 2200）
# 每一階再分 IV、III、II、I 四個小段
TIERS = [
    (0, "青銅"), (1200, "白銀"), (1400, "黃金"), (1600, "白金"), (1800, "鑽石"),
    (2000, "大師"), (2200, "宗師"), (2400, "傳說"), (2700, "神話"),
]
DIVS = ["IV", "III", "II", "I"]

# 社群題目難度表（zerotrac/leetcode_problem_rating）：slug → 難度分。由 lc.py 下載後設定。
RATINGS = {}


def set_ratings(table):
    global RATINGS
    RATINGS = dict(table or {})


def playable(p):
    """這題能不能拿來玩：免費、而且不是 SQL / Bash / 多執行緒題。"""
    return not p.get("paidOnly") and not (set(p.get("tags", [])) & EXCLUDED_TAGS)


def problem_rating(p):
    """題目難度分（跟 LeetCode 競賽分同尺度）。

    有收錄在社群難度表（競賽題）就直接用；沒有的話，用官方難度與通過率估計。
    估計公式是拿社群難度表裡的簡單題回歸出來的（誤差約 ±85 分）。
    """
    r = RATINGS.get(p.get("slug"))
    if r:
        return int(round(r))
    ac = p.get("acRate") or 50
    d = p.get("difficulty")
    if d == "Easy":
        est = 1454 - 2.64 * ac
    elif d == "Medium":
        est = 1950 - 6.0 * ac
    else:
        est = 2550 - 12.0 * ac
    return int(round(est))


def rank_info(rating):
    """段位：回傳 (名稱含小段, 階名, 下一段的名稱, 還差幾分)。"""
    i = max(k for k, (lo, _) in enumerate(TIERS) if rating >= lo)
    lo, name = TIERS[i]
    if i == len(TIERS) - 1:
        return {"rank": name, "tier": name, "next": None, "need": 0}
    hi = TIERS[i + 1][0]
    lo = max(lo, 1000) if i == 0 else lo
    step = (hi - lo) / 4
    div = min(3, max(0, int((rating - lo) // step)))
    if div < 3:
        nxt, need = f"{name} {DIVS[div + 1]}", lo + step * (div + 1) - rating
    else:
        nxt, need = f"{TIERS[i + 1][1]} {DIVS[0]}", hi - rating
    return {"rank": f"{name} {DIVS[div]}", "tier": name, "next": nxt, "need": int(max(1, round(need)))}


def rank_of(rating):
    return rank_info(rating)["rank"]


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
# 2. 實力分、段位、戰力
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


def skill_from(ratings, k=10, prior=1000.0, shrink=3.0):
    """實力分：看你解掉的「最難的那幾題」。

    取難度最高的 k 題做加權平均（越難權重越高），再依解題數往新手基準 1000 打折。
    跟解題順序無關，狂刷簡單題也不會灌分；解過 2800 分的題目，實力分就會接近 2800。
    """
    if not ratings:
        return prior
    top = sorted(ratings, reverse=True)[:k]
    w = [0.85 ** i for i in range(len(top))]
    peak = sum(r * x for r, x in zip(top, w)) / sum(w)
    n = len(ratings)
    return prior + (peak - prior) * n / (n + shrink)


def power_score(ratings):
    """戰力：會一直成長的遊戲數字。每題貢獻 (難度分/1000)^3 × 100，越難的題目加越多。"""
    return int(round(sum((r / 1000) ** 3 * 100 for r in ratings)))


def compute_power(problems, records, contest=None):
    by_slug = {p["slug"]: p for p in problems}
    evs = _events(by_slug, records)
    wins = sum(1 for e in evs if e[2])

    solved = []  # (slug, problem)
    for slug, r in records.items():
        if r.get("solved"):
            p = by_slug.get(slug) or {"slug": slug, "difficulty": r.get("difficulty", "Easy"), "acRate": 50, "tags": []}
            solved.append(p)
    rated = [problem_rating(p) for p in solved]
    est = skill_from(rated)

    # 一次通過率微調（有足夠提交紀錄才算）：最多 ±40 分
    tried = [e for e in evs if e[0]]
    if len(tried) >= 10:
        acc = sum(1 for e in tried if e[2]) / len(tried)
        est += max(-40.0, min(40.0, (acc - 0.7) * 130))

    official = None
    if contest and contest.get("rating") and contest.get("attended", 0) >= 1:
        official = int(round(contest["rating"]))
    rating = max(est, official or 0)

    per_tag = {}
    tag_r = defaultdict(list)
    for p in solved:
        for t in p.get("tags", []):
            if t not in EXCLUDED_TAGS:
                tag_r[t].append(problem_rating(p))
    for t, rs in tag_r.items():
        # 技能實力分：只看這個技能的題目，取最難的 5 題，題數少時往 1000 打折
        n = len(rs)
        per_tag[t] = {"rating": int(round(skill_from(rs, k=5, shrink=2))), "events": n, "wins": n}

    xp = sum(DIFF_XP.get(p.get("difficulty"), 10) for p in solved)
    ri = rank_info(rating)
    return {
        "rating": int(round(rating)), "estimate": int(round(est)), "official": official,
        "contest": contest or None,
        "rank": ri["rank"], "tier": ri["tier"], "nextRank": ri["next"], "needRank": ri["need"],
        "power": power_score(rated), "hardest": max(rated) if rated else None,
        "events": len(evs), "wins": wins, "accuracy": round(wins / len(evs) * 100) if evs else 0,
        "solved": len(solved), "xp": xp, "per_tag": per_tag,
        "ratedBy": "zerotrac" if RATINGS else "estimate",
    }


# ---------------------------------------------------------------------------
# 3. 推薦
# ---------------------------------------------------------------------------
# 琥珀（系統化策略）推題時附上的觀念提示
CONCEPTS = {
    "array": "用索引直接存取，常搭配一次走訪 O(n)",
    "string": "字元走訪、切片與比較，注意不可變的成本",
    "hash-table": "用空間換時間：O(1) 查詢「看過沒」",
    "math": "先找規律或公式，避免硬算",
    "sorting": "排序後很多問題會變簡單（O(n log n)）",
    "two-pointers": "左右夾擊或快慢指標，把 O(n²) 壓到 O(n)",
    "sliding-window": "維護一段連續區間，右邊擴張、左邊收縮",
    "stack": "後進先出，處理配對與「下一個更大」",
    "monotonic-stack": "維持單調性，一次找出每個元素的下一個更大/更小",
    "queue": "先進先出，常用在 BFS",
    "linked-list": "指標操作，畫圖比想像可靠",
    "binary-search": "每次砍一半；也能「對答案二分」",
    "tree": "遞迴：先想清楚子樹要回傳什麼",
    "binary-tree": "前中後序與層序走訪",
    "binary-search-tree": "左小右大，中序走訪是排序好的",
    "depth-first-search": "一路走到底再回頭，常用遞迴",
    "breadth-first-search": "一層一層往外擴，求最短步數",
    "graph": "點與邊：先決定用鄰接表還是矩陣",
    "heap-priority-queue": "隨時拿到最大或最小值（O(log n)）",
    "greedy": "每步拿當下最好的，要能說服自己局部最佳會導向全域最佳",
    "dynamic-programming": "定義狀態、寫出轉移、設好初始值",
    "backtracking": "選了再撤銷，搭配剪枝",
    "bit-manipulation": "XOR 自我抵銷、lowbit、位元遮罩",
    "prefix-sum": "預先累加，任意區間和 O(1)",
    "matrix": "二維走訪，注意邊界與方向陣列",
    "simulation": "照題目一步步做，細心處理每種情況",
    "counting": "先數每種東西出現幾次",
    "recursion": "相信遞迴：假設小問題已經解好",
    "design": "先決定資料結構，再實作每個操作",
    "trie": "把字串拆成路徑的樹，前綴查詢很快",
    "union-find": "合併集合、查同一群，記得路徑壓縮",
    "enumeration": "列舉所有可能，確認規模夠小",
    "geometry": "座標、向量與面積公式",
    "number-theory": "質數、最大公因數、同餘",
}


def day_streak(records, today=None):
    """連續幾天有通過的提交（今天還沒刷的話，從昨天往回算）。"""
    from datetime import date, timedelta
    days = set()
    for r in records.values():
        for a in r.get("attempts", []):
            if a.get("accepted") and a.get("time"):
                days.add(a["time"][:10])
    d = today or date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def score_problem(p, rating, tree_by_id, per_tag, offset=80, width=180, mode="balanced", max_layer=1):
    """替一題打分。mode 是看板娘的推薦策略，決定各種加成的權重。"""
    pr = problem_rating(p)
    target = rating + offset
    fit = math.exp(-((pr - target) / width) ** 2)
    w_front, w_weak, w_lock = 0.6, 1.0, -0.25
    if mode == "comfort":
        w_front, w_weak = 0.3, 0.3
    elif mode == "weakest":
        w_front, w_weak = 0.3, 2.2
    elif mode == "tree":
        w_front, w_lock = 1.0, -0.9
    elif mode == "explore":
        w_weak = 0.4
    bonus, why = 0.0, []
    tags = [t for t in p.get("tags", []) if t in tree_by_id]
    for t in tags:
        node = tree_by_id[t]
        if node["unlocked"] and node["level"] < 2:
            bonus += w_front
            why.append(("frontier", t))
        elif not node["unlocked"]:
            bonus += w_lock
        tr = per_tag.get(t, {}).get("rating")
        if tr is not None and tr < rating - 30:
            bonus += w_weak * min(0.6, (rating - tr) / 300)
            why.append(("weak", t))
    ac = p.get("acRate") or 50
    if mode == "comfort":
        bonus += (ac - 55) / 40
        if ac >= 65:
            why.insert(0, ("easywin", ac))
    elif mode == "daily":
        bonus += (0.5 if p.get("difficulty") == "Easy" else -0.6) + (ac - 55) / 60
        why.insert(0, ("daily", ac))
    elif mode == "tree":
        layers = [tree_by_id[t]["layer"] for t in tags if tree_by_id[t]["unlocked"]]
        if layers:
            bonus += 0.6 * (1 - min(layers) / max(1, max_layer))
        if any(t in CONCEPTS for t in tags):
            why.insert(0, ("concept", next(t for t in tags if t in CONCEPTS)))
    elif mode == "explore":
        unseen = [t for t in tags if tree_by_id[t]["solved"] == 0]
        bonus += min(1.6, 0.8 * len(unseen))
        if unseen:
            why.insert(0, ("unseen", unseen[0]))
    elif mode == "contest":
        if p.get("slug") in RATINGS:
            bonus += 1.0
            why.insert(0, ("contest", None))
        else:
            bonus -= 0.6
    return fit * (1 + max(-0.7, bonus)), pr, why


def explain(p, pr, rating, why, tree_by_id):
    diff = pr - rating
    lines = []
    for kind, t in why:
        if kind == "easywin":
            lines.append(f"通過率 {t}%，很好拿下")
        elif kind == "daily":
            lines.append("短小好上手，今天就能打卡")
        elif kind == "concept":
            lines.append(f"觀念：{CONCEPTS[t]}")
        elif kind == "unseen":
            lines.append(f"你還沒碰過「{tree_by_id[t]['name']}」")
        elif kind == "contest":
            lines.append("LeetCode 週賽真題")
        else:
            continue
        break
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
            lines.append(f"你的「{tree_by_id[t]['name']}」實力比平均低，補一下")
            break
    if diff > 120:
        lines.append(f"難度 {pr}，比你高 {diff}，打贏會提升實力分")
    elif diff > -60:
        lines.append(f"難度 {pr}，跟你的實力分 {rating} 剛好勢均力敵")
    else:
        lines.append(f"難度 {pr}，輕鬆拿經驗")
    return lines[:2]


def _item(p, pr, s, reasons, tree_by_id, review=False):
    return {
        "slug": p["slug"], "id": p["id"], "title": p["title"],
        "difficulty": p["difficulty"], "acRate": p.get("acRate"),
        "tags": [t for t in p.get("tags", []) if t in tree_by_id],
        "tagNames": [tree_by_id[t]["name"] for t in p.get("tags", []) if t in tree_by_id],
        "rating": pr, "score": round(s, 3), "xp": DIFF_XP.get(p["difficulty"], 10),
        "reasons": reasons, "review": review,
    }


def _weighted_pick(rng, pool, k):
    picked = []
    pool = list(pool)
    while pool and len(picked) < k:
        weights = [c[0] ** 2 + 1e-9 for c in pool]
        i = rng.choices(range(len(pool)), weights=weights)[0]
        picked.append(pool.pop(i))
    return picked


MISTAKES = {}  # slug -> 錯題本裡還沒解決的筆數（伺服器每次算推薦前更新）


def set_mistakes(m):
    MISTAKES.clear()
    MISTAKES.update(m or {})


def review_candidates(problems, records, exclude=(), now=None):
    """星璃的複習清單：錯題本裡還沒解決的、以前答錯過的、很久沒碰的已解題（間隔重複）。"""
    from datetime import datetime
    now = now or datetime.now()
    by_slug = {p["slug"]: p for p in problems}
    out = []
    for slug, r in records.items():
        p = by_slug.get(slug)
        open_m = MISTAKES.get(slug, 0)
        if not p or not playable(p) or slug in exclude or not (r.get("solved") or open_m):
            continue
        times = [a.get("time") for a in r.get("attempts", []) if a.get("time")]
        try:
            last = datetime.strptime(max(times), "%Y-%m-%d %H:%M:%S") if times else None
        except ValueError:
            last = None
        days = (now - last).days if last else 30
        wrong = sum(1 for a in r.get("attempts", []) if a.get("accepted") is False)
        if days < 3 and not wrong and not open_m:
            continue
        s = min(1.0, days / 14) * 0.7 + min(0.6, wrong * 0.2) + min(0.9, open_m * 0.45) + 0.1
        why = (f"錯題本裡還有 {open_m} 筆沒解決，把它拿下吧" if open_m
               else f"以前答錯 {wrong} 次，再練一次會更穩" if wrong else f"{days} 天前解過，該複習了")
        out.append((s, p, problem_rating(p), why))
    out.sort(key=lambda c: -c[0])
    return out


def recommend(problems, records, tree, power, k=5, offset=80, width=180,
              exclude=(), seen=(), tag=None, seed=None, mode="balanced"):
    """挑出 k 題推薦。高分題機率高，但保留隨機性，每次推的不一樣。

    mode 是看板娘的推薦策略：balanced 均衡、comfort 舒適、daily 打卡、weakest 弱點、
    tree 技能樹順序、explore 探索、contest 競賽、review 複習。
    """
    rng = random.Random(seed)
    solved = {s for s, r in records.items() if r.get("solved")}
    tree_by_id = {n["id"]: n for n in tree["nodes"]}
    rating, per_tag = power["rating"], power["per_tag"]
    max_layer = max([n["layer"] for n in tree["nodes"]] or [1])
    seen = list(seen)

    out = []
    if mode == "review" and not tag:
        rev = review_candidates(problems, records, exclude)
        n_rev = min(len(rev), (k * 2 + 2) // 3)
        for s, p, pr, why in _weighted_pick(rng, rev[: max(n_rev * 4, 8)], n_rev):
            out.append(_item(p, pr, s, [why, f"難度 {pr}"], tree_by_id, review=True))
        k -= len(out)
        mode = "balanced"
        if k <= 0:
            return out

    cands = []
    for p in problems:
        if not playable(p) or p["slug"] in solved or p["slug"] in exclude:
            continue
        if tag and tag not in p.get("tags", []):
            continue
        s, pr, why = score_problem(p, rating, tree_by_id, per_tag, offset, width, mode, max_layer)
        if p["slug"] in seen:
            s *= 0.3
        cands.append((s, p, pr, why))
    cands.sort(key=lambda c: -c[0])
    for s, p, pr, why in _weighted_pick(rng, cands[: max(k * 6, 20)], k):
        out.append(_item(p, pr, s, explain(p, pr, rating, why, tree_by_id), tree_by_id))
    return out
