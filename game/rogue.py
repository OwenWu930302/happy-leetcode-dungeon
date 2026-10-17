# -*- coding: utf-8 -*-
"""
肉鴿遠征（Roguelike）
=====================

每一局都會用種子隨機生成一張「演算法地城」：
  戰鬥 → 精英 → 寶箱 → 篝火 → 商店 → 神秘事件 → 最後是 Boss。

- 戰鬥節點會端出 2~3 題「剛好打得贏」的題目讓你挑（由 engine.recommend 決定）
- 提交答錯 = 被怪物打，扣 HP；通過 = 擊敗怪物，拿金幣、經驗、遺物
- 試跑（test）不扣血，放心試
- HP 歸零這局就結束，但會留下「靈魂結晶」可以買永久強化
"""

import hashlib
import random
from datetime import datetime

from . import engine

ROWS, COLS = 10, 7
NOW = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

NODE_TYPES = {
    "fight": {"name": "戰鬥", "atk": 10, "offset": 40, "k": 3},
    "elite": {"name": "精英", "atk": 16, "offset": 230, "k": 2},
    "boss": {"name": "Boss", "atk": 22, "offset": 330, "k": 2},
    "chest": {"name": "寶箱"},
    "camp": {"name": "篝火"},
    "shop": {"name": "商店"},
    "mystery": {"name": "神秘事件"},
}

RELICS = {
    "rubber_duck": ("小黃鴨", "鴨", "每場戰鬥第一次答錯不扣血。對著它講解程式就會發現 bug。"),
    "coffee": ("濃縮咖啡", "啡", "每次擊敗怪物回復 6 HP。"),
    "golden_keyboard": ("黃金鍵盤", "鍵", "獲得的金幣 +50%。"),
    "stack_amulet": ("溢位護符", "溢", "最大 HP +15，並回復 15 HP。"),
    "big_o": ("大 O 之書", "書", "遠征經驗 +30%。"),
    "debugger": ("除錯器", "錯", "答錯受到的傷害 -30%。"),
    "hash_charm": ("雜湊護符", "雜", "擊敗帶「雜湊表」標籤的怪物，額外 +15 金幣。"),
    "recursion_mirror": ("遞迴之鏡", "鏡", "篝火休息的回復量加倍。"),
    "leet_crown": ("1337 冠冕", "冠", "Boss 對你的傷害減半。"),
    "two_pointer_boots": ("雙指標戰靴", "靴", "每走到一個新節點回復 3 HP。"),
    "lucky_cat": ("招財貓", "貓", "每場戰鬥可以免費換一次題目。"),
    "compiler_heart": ("編譯器之心", "芯", "精英戰勝利多拿 25 金幣。"),
}

UPGRADES = {
    "vitality": ("強健體魄", "每級最大 HP +10", 5, lambda lv: 30 * (lv + 1)),
    "scholar": ("學者之魂", "每級遠征經驗 +10%", 3, lambda lv: 40 * (lv + 1)),
    "starter": ("傳家寶", "每局開場隨機帶一個遺物", 1, lambda lv: 80),
    "purse": ("鼓鼓的錢包", "每級開場多 25 金幣", 3, lambda lv: 25 * (lv + 1)),
}

EVENTS = [
    ("迷途的 Debugger", "一位老工程師幫你看了 log，你覺得神清氣爽。", {"heal": 15}),
    ("Stack Overflow 寶箱", "你在古老的討論串裡找到了被遺忘的答案。", {"gold": 35}),
    ("古老的面試題卷", "卷軸裡夾著一件遺物。", {"relic": 1}),
    ("鬼魂般的 Segfault", "一個 Segfault 從背後咬了你一口，但牠掉了一袋金幣。", {"heal": -8, "gold": 50}),
    ("時間複雜度之井", "你從 O(n²) 進化成 O(n log n)，體質提升了。", {"maxhp": 5, "heal": 5}),
    ("橡皮鴨的低語", "「你有試過把它印出來嗎？」你突然想通了很多事。", {"xp": 20}),
]


# ---------------------------------------------------------------------------
# 流派技能：每位看板娘一招，一局只能用一次
# 適用時機：any 隨時；battle 戰鬥中（選題前後都行）；pick 還沒選題時；fight 普通戰鬥中
# ---------------------------------------------------------------------------
SKILLS = {
    "p0": ("星之指引", "免費換一批題目，新題目的難度下修約 100 分。", "pick"),
    "p1": ("全力應援", "這場戰鬥的下一次答錯不扣血，也不會中斷連勝。", "battle"),
    "p2": ("節拍回復", "立刻回復 25% 最大 HP。", "any"),
    "p3": ("冰霜試煉", "這場戰鬥的經驗 ×2，但答錯的傷害 ×1.5。", "battle"),
    "p4": ("學者之眼", "這場戰鬥的提示第 1、2 階免費，不扣獎勵。", "battle"),
    "p5": ("月影步", "悄悄繞過這場普通戰鬥：不扣血，也沒有獎勵（精英、Boss 不行）。", "fight"),
    "p6": ("鬥志全開", "這場戰鬥在開戰 15 分鐘內通過的話，金幣與經驗 ×1.5。", "battle"),
    "p7": ("時光回溯", "回復這局累計受到傷害的一半（最多 30 HP）。", "any"),
}

# Boss 規則：進 Boss 房就公開，全部由遊戲自己判定（時間、語言、提交次數）
BOSS_RULES = {
    "timed": ("限時 25 分鐘", "開戰 25 分鐘內通過拿全額獎勵，超時只拿一半。"),
    "lang": ("語言封印", "這場只能用 {lang} 出招，用其他語言出招會被當成答錯。"),
    "fury": ("狂暴", "答錯的傷害 ×2，但擊敗後的獎勵 ×1.5。"),
    "first": ("一擊必殺", "第一次出招就通過，獎勵 ×2。"),
}
LANG_NAMES = {"python3": "Python 3", "cpp": "C++"}

# 飛升難度：通關一次解鎖下一級，效果會累加
ASCENSION = [
    None,
    ("難度上升", "推薦題目的難度 +50"),
    ("虛弱開局", "開場最大 HP -10"),
    ("篝火微弱", "篝火休息的回復量減半"),
    ("物價上漲", "商店價格 +25%"),
    ("精英強化", "精英的傷害 +25%"),
    ("拮据", "擊敗怪物拿到的金幣 -25%"),
    ("Boss 暴怒", "Boss 的傷害 +25%"),
    ("難度再上升", "推薦題目的難度再 +50"),
    ("換題代價", "換題目要扣 10 HP（招財貓仍可免費一次）"),
    ("最終試煉", "每場戰鬥少一個題目可以挑"),
]
ASC_MAX = len(ASCENSION) - 1

# 遺物組合技：兩件遺物湊齊就發動
SYNERGIES = {
    "debug_duo": ("除錯雙人組", ("rubber_duck", "debugger"), "答錯的傷害再 -20%。"),
    "caffeine_rush": ("咖啡因衝刺", ("coffee", "two_pointer_boots"), "擊敗怪物再回復 4 HP。"),
    "tycoon": ("富可敵國", ("golden_keyboard", "lucky_cat"), "商店所有東西打 8 折。"),
    "deep_stack": ("深層堆疊", ("recursion_mirror", "stack_amulet"), "篝火修練的最大 HP 提升從 6 變成 12。"),
    "constant_time": ("O(1) 查表", ("hash_charm", "big_o"), "擊敗帶「雜湊表」標籤的怪物，經驗再 +20%。"),
    "kings_return": ("王者歸來", ("leet_crown", "compiler_heart"), "擊敗 Boss 時額外獲得 30 結晶。"),
}

# 資料包（mods/）加進來的內容；只放資料，效果用固定的幾種欄位描述
MOD_RELICS = {}   # id -> {"name", "glyph", "desc", "effect": {...}, "mod"}
MOD_EVENTS = []   # (title, text, effects, mod)
MOD_SYNERGIES = {}  # id -> (name, (relic, relic), desc, effect)
EFFECT_KEYS = {"heal_on_win": int, "gold_mult": float, "xp_mult": float, "dmg_mult": float,
               "max_hp": int, "camp_mult": float}


def relic_info(rid):
    if rid in RELICS:
        n, g, d = RELICS[rid]
        return {"name": n, "glyph": g, "desc": d}
    m = MOD_RELICS.get(rid)
    if m:
        return {"name": m["name"], "glyph": m["glyph"], "desc": m["desc"], "mod": m.get("mod")}
    return {"name": "失落的遺物", "glyph": "？", "desc": "這件遺物來自已經移除的資料包，沒有效果。"}


def new_save():
    return {
        "meta": {"shards": 0, "bonus_xp": 0, "upgrades": {}, "history": [],
                 "ads_seen": [], "bounties": {}, "runs_started": 0},
        "run": None,
    }


# ---------------------------------------------------------------------------
# 地圖生成：多條路徑由下往上隨機走，避免路線交叉，再依規則分配節點種類
# ---------------------------------------------------------------------------
def _crosses(edges, r, c, d):
    for (r1, a), (_, b) in edges:
        if r1 == r and ((a < c and b > d) or (a > c and b < d)):
            return True
    return False


def gen_map(rng, mystery_boost=False):
    edges = set()
    starts = []
    for i in range(6):
        c = rng.randrange(COLS)
        if i == 1:
            while c == starts[0]:
                c = rng.randrange(COLS)
        starts.append(c)
        for r in range(ROWS - 1):
            options = [d for d in (c - 1, c, c + 1) if 0 <= d < COLS and not _crosses(edges, r, c, d)]
            d = rng.choice(options) if options else c
            edges.add(((r, c), (r + 1, d)))
            c = d
    cells = {e[0] for e in edges} | {e[1] for e in edges}
    parents = {}
    for a, b in edges:
        parents.setdefault(b, []).append(a)

    types = {}
    for r, c in sorted(cells):
        if r == 0:
            t = "fight"
        elif r == ROWS // 2:
            t = "chest"
        elif r == ROWS - 1:
            t = "camp"
        else:
            bag = [("fight", 45), ("mystery", 34 if mystery_boost else 20)]
            if r >= 2:
                bag.append(("shop", 9))
            if r >= 3:
                bag += [("elite", 15), ("camp", 10)]
            for _ in range(8):
                t = rng.choices([b[0] for b in bag], weights=[b[1] for b in bag])[0]
                bad = any(types.get(p) == t for p in parents.get((r, c), [])) and t in ("elite", "camp", "shop")
                if not bad:
                    break
            else:
                t = "fight"
        types[(r, c)] = t

    key = lambda rc: f"{rc[0]}-{rc[1]}"
    nodes = {key(rc): {"r": rc[0], "c": rc[1], "type": t} for rc, t in types.items()}
    nodes["boss"] = {"r": ROWS, "c": COLS // 2, "type": "boss"}
    links = sorted([key(a), key(b)] for a, b in edges)
    links += [[key(rc), "boss"] for rc in sorted(cells) if rc[0] == ROWS - 1]
    return {"rows": ROWS + 1, "cols": COLS, "nodes": nodes, "edges": links}


# ---------------------------------------------------------------------------
# 一局的生命週期
# ---------------------------------------------------------------------------
def _has(run, relic):
    return relic in run["relics"]


def _asc(run):
    return run.get("asc", 0)


def _syn(run, sid):
    pair = (SYNERGIES.get(sid) or MOD_SYNERGIES.get(sid) or (None, ()))[1]
    return bool(pair) and all(r in run["relics"] for r in pair)


def active_synergies(run):
    return [sid for sid in list(SYNERGIES) + list(MOD_SYNERGIES) if _syn(run, sid)]


def _eff_mult(run, key):
    """資料包遺物與資料包組合技的乘數效果（沒有就是 1）。"""
    m = 1.0
    for rid in run["relics"]:
        v = (MOD_RELICS.get(rid) or {}).get("effect", {}).get(key)
        if v:
            m *= v
    for sid, (_, _, _, eff) in MOD_SYNERGIES.items():
        if _syn(run, sid) and eff.get(key):
            m *= eff[key]
    return m


def _eff_sum(run, key):
    total = 0
    for rid in run["relics"]:
        total += (MOD_RELICS.get(rid) or {}).get("effect", {}).get(key, 0)
    for sid, (_, _, _, eff) in MOD_SYNERGIES.items():
        if _syn(run, sid):
            total += eff.get(key, 0)
    return total


def _hurt(run, dmg):
    """受到傷害（記下累計傷害，時光回溯會用到）。"""
    got = -_heal(run, -dmg)
    run["dmg_taken"] = run.get("dmg_taken", 0) + got
    return got


def _log(run, text):
    run["log"].insert(0, {"t": NOW(), "text": text})
    del run["log"][30:]


def _heal(run, amount):
    before = run["hp"]
    run["hp"] = max(0, min(run["max_hp"], run["hp"] + amount))
    return run["hp"] - before


def _gain_gold(run, amount):
    if _has(run, "golden_keyboard") and amount > 0:
        amount = int(amount * 1.5)
    run["gold"] += amount
    return amount


def _relic_options(run, rng, n=3):
    pool = [r for r in list(RELICS) + sorted(MOD_RELICS) if r not in run["relics"]]
    rng.shuffle(pool)
    return pool[:n]


def _add_relic(run, rid):
    if rid in run["relics"]:
        return
    before = set(active_synergies(run))
    run["relics"].append(rid)
    if rid == "stack_amulet":
        run["max_hp"] += 15
        _heal(run, 15)
    extra = (MOD_RELICS.get(rid) or {}).get("effect", {}).get("max_hp", 0)
    if extra:
        run["max_hp"] += extra
        _heal(run, extra)
    _log(run, f"獲得遺物「{relic_info(rid)['name']}」")
    for sid in active_synergies(run):
        if sid not in before:
            name = (SYNERGIES.get(sid) or MOD_SYNERGIES.get(sid))[0]
            _log(run, f"組合技發動：{name}！")


def _price(run, base):
    p = base * (1.25 if _asc(run) >= 4 else 1) * (0.8 if _syn(run, "tycoon") else 1)
    return int(round(p))


def daily_seed(day: str) -> int:
    """每日挑戰的種子：同一天所有玩家都一樣。day 是 'YYYY-MM-DD'。"""
    return int(hashlib.sha256(f"lcd-daily-{day}".encode()).hexdigest()[:7], 16)


def _result_code(run, won, floors) -> str:
    """每日挑戰的成績碼：日期、勝負、層數、剩餘血量、用時，加 4 碼檢查碼。"""
    t0 = datetime.strptime(run["started_at"], "%Y-%m-%d %H:%M:%S")
    minutes = max(1, round((datetime.now() - t0).total_seconds() / 60))
    day = run["daily"].replace("-", "")
    body = f"{day}-{'W' if won else 'L'}{floors:02d}-{max(0, run['hp'])}HP-{minutes}M"
    chk = hashlib.sha256(f"{body}|{run['seed']}".encode()).hexdigest()[:4].upper()
    return f"LCD-{body}-{chk}"


def _better(a, b) -> bool:
    """a 是否比 b 好：先比勝負，再比層數、剩餘血量、用時。"""
    if b is None:
        return True
    ka = (a["won"], a["floors"], a["hp"], -a["minutes"])
    kb = (b["won"], b["floors"], b["hp"], -b["minutes"])
    return ka > kb


def start_run(save, seed=None, persona="p0", daily=None, asc=0, skill=None):
    meta = save["meta"]
    asc = 0 if daily else int(asc or 0)
    if not 0 <= asc <= min(ASC_MAX, meta.get("asc_max", 0)):
        raise ValueError("還沒解鎖這個飛升等級")
    if daily:
        seed = daily_seed(daily)
    seed = seed if seed is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    ups = meta["upgrades"]
    max_hp = 60 + 10 * ups.get("vitality", 0) - (10 if asc >= 2 else 0)
    run = {
        "seed": seed, "started_at": NOW(), "status": "active",
        "hp": max_hp, "max_hp": max_hp, "gold": 25 * ups.get("purse", 0),
        # 每日挑戰：地圖只看日期，不受看板娘影響，大家才會拿到同一張
        "relics": [], "map": gen_map(rng, mystery_boost=(persona == "p5" and not daily)), "pos": None, "cleared": [],
        "current": None, "pending": None, "xp": 0, "kills": 0, "log": [], "used_slugs": [],
        "persona": persona, "streak": 0, "dayStreak": 0, "daily": daily,
        "asc": asc, "skill": skill if skill in SKILLS else (persona if persona in SKILLS else "p0"),
        "skill_used": False, "dmg_taken": 0,
    }
    if ups.get("starter"):
        _add_relic(run, rng.choice(list(RELICS)))
    meta["runs_started"] = meta.get("runs_started", 0) + 1
    _log(run, f"每日挑戰 {daily} 開始！今天的地圖大家都一樣" if daily
         else f"第 {meta['runs_started']} 次遠征開始！種子 #{seed}" + (f"（飛升 {asc}）" if asc else ""))
    save["run"] = run
    return run


def moves(run):
    """現在可以走的節點。"""
    if not run or run["status"] != "active" or run["current"] or run["pending"]:
        return []
    m = run["map"]
    if run["pos"] is None:
        return sorted(k for k, n in m["nodes"].items() if n["r"] == 0)
    return sorted(b for a, b in m["edges"] if a == run["pos"])


def _rng(run, salt):
    return random.Random(f"{run['seed']}:{salt}:{len(run['cleared'])}")


def _offers(run, ctx, ntype, salt="", easier=0):
    spec = dict(NODE_TYPES[ntype])
    a = _asc(run)
    spec["offset"] = spec["offset"] + (50 if a >= 1 else 0) + (50 if a >= 8 else 0) - easier
    spec["k"] = max(1, spec["k"] - (1 if a >= 10 else 0))
    tag = None
    if ntype == "boss":
        # Boss 從你最弱、但已解鎖的技能出題
        cands = [n for n in ctx["tree"]["nodes"] if n["unlocked"] and n["total"] - n["solved"] >= 2]
        if cands:
            per = ctx["power"]["per_tag"]
            weakest = min(cands, key=lambda n: (n["level"], per.get(n["id"], {}).get("rating", ctx["power"]["rating"]), -n["total"]))
            tag = weakest["id"]
    mode = ctx.get("mode", "balanced")
    if mode == "review":
        mode = "balanced"  # 遠征打的是新怪，複習留給酒館
    recs = engine.recommend(
        ctx["problems"], ctx["records"], ctx["tree"], ctx["power"],
        k=spec["k"], offset=spec["offset"], width=160 if ntype == "fight" else 220,
        exclude=set(run["used_slugs"]), tag=tag,
        seed=f"{run['seed']}:{run['pos']}:{salt}", mode=mode,
    )
    if not recs and tag:
        recs = engine.recommend(ctx["problems"], ctx["records"], ctx["tree"], ctx["power"],
                                k=spec["k"], offset=spec["offset"], exclude=set(run["used_slugs"]),
                                seed=f"{run['seed']}:{salt}")
    return recs, tag


def enter(save, key, ctx):
    run = save["run"]
    if key not in moves(run):
        raise ValueError("現在不能走到那裡")
    node = run["map"]["nodes"][key]
    run["pos"] = key
    if _has(run, "two_pointer_boots"):
        _heal(run, 3)
    t = node["type"]
    rng = _rng(run, key)
    events = []
    if t in ("fight", "elite", "boss"):
        offers, tag = _offers(run, ctx, t)
        run["current"] = {
            "key": key, "type": t, "offers": offers, "chosen": None, "started_at": None,
            "seen": [], "wrong": 0, "rerolled": False, "boss_tag": tag,
        }
        if t == "boss":
            rules = ["timed", "fury", "first"]
            lang = ctx.get("lang")
            if lang in LANG_NAMES:
                rules.append("lang")
            rule = rng.choice(rules)
            run["current"]["rule"] = rule
            if rule == "lang":
                run["current"]["rule_lang"] = "cpp" if lang == "python3" else "python3"
            _log(run, f"Boss 規則：{BOSS_RULES[rule][0]}")
        _log(run, f"遭遇{NODE_TYPES[t]['name']}！")
    elif t == "chest":
        run["pending"] = {"kind": "relic", "title": "寶箱", "options": _relic_options(run, rng), "gold": 20}
        _log(run, "打開了寶箱")
    elif t == "camp":
        run["pending"] = {"kind": "camp"}
    elif t == "shop":
        opts = _relic_options(run, rng, 3)
        items = [{"kind": "relic", "id": r, "base": rng.choice([55, 65, 75, 85])} for r in opts]
        items.append({"kind": "heal", "amount": 20, "base": 30})
        for it in items:
            it["price"] = _price(run, it["base"])
        run["pending"] = {"kind": "shop", "items": items}
    elif t == "mystery":
        title, text, eff = rng.choice(EVENTS + [e[:3] for e in MOD_EVENTS])
        parts = []
        if eff.get("maxhp"):
            run["max_hp"] += eff["maxhp"]
            parts.append(f"最大 HP +{eff['maxhp']}")
        if eff.get("heal"):
            got = _heal(run, eff["heal"]) if eff["heal"] > 0 else -_hurt(run, -eff["heal"])
            parts.append(f"HP {'+' if got >= 0 else ''}{got}")
        if eff.get("gold"):
            parts.append(f"金幣 +{_gain_gold(run, eff['gold'])}")
        if eff.get("xp"):
            run["xp"] += eff["xp"]
            parts.append(f"經驗 +{eff['xp']}")
        if eff.get("relic"):
            opts = _relic_options(run, rng, 1)
            if opts:
                _add_relic(run, opts[0])
                parts.append(f"遺物「{RELICS[opts[0]][0]}」")
        run["pending"] = {"kind": "event", "title": title, "text": text, "effects": parts}
        _log(run, f"{title}：{'、'.join(parts)}")
        if run["hp"] <= 0:
            events += _die(save)
    return events


def choose(save, slug):
    cur = save["run"]["current"]
    if not cur or slug not in [o["slug"] for o in cur["offers"]]:
        raise ValueError("這題不在選項裡")
    cur["chosen"] = slug
    cur["started_at"] = NOW()
    save["run"]["used_slugs"].append(slug)
    _log(save["run"], f"向「{next(o['title'] for o in cur['offers'] if o['slug'] == slug)}」發起挑戰")


def reroll(save, ctx):
    run = save["run"]
    cur = run["current"]
    if not cur or cur["chosen"]:
        raise ValueError("已經開戰了，不能換題")
    free = _has(run, "lucky_cat") and not cur["rerolled"]
    cost = 10 if _asc(run) >= 9 else 5
    if not free:
        _hurt(run, cost)
    cur["rerolled"] = True
    run["used_slugs"] += [o["slug"] for o in cur["offers"]]
    cur["offers"], _ = _offers(run, ctx, cur["type"], salt=f"reroll{len(run['used_slugs'])}")
    _log(run, "換了一批題目" + ("（招財貓免費）" if free else f"，HP -{cost}"))
    return _die(save) if run["hp"] <= 0 else []


def _damage(run, cur):
    atk = NODE_TYPES[cur["type"]]["atk"]
    if _has(run, "debugger"):
        atk *= 0.7
    if cur["type"] == "boss" and _has(run, "leet_crown"):
        atk *= 0.5
    persona = run.get("persona")
    if persona == "p3":  # 雪奈：嚴格，答錯更痛
        atk *= 1.2
    if persona == "p6" and cur["type"] == "boss":  # 珂可：Boss 戰老手
        atk *= 0.7
    a = _asc(run)
    if cur["type"] == "elite" and a >= 5:
        atk *= 1.25
    if cur["type"] == "boss" and a >= 7:
        atk *= 1.25
    if cur.get("rule") == "fury":
        atk *= 2
    if cur.get("frost"):  # 雪奈的冰霜試煉
        atk *= 1.5
    if _syn(run, "debug_duo"):
        atk *= 0.8
    atk *= _eff_mult(run, "dmg_mult")
    if _has(run, "rubber_duck") and cur["wrong"] == 0:
        atk = 0
    if cur.get("shield"):  # 米菈的全力應援
        atk = 0
    return int(round(atk))


def _scholar(save):
    return 1 + 0.1 * save["meta"]["upgrades"].get("scholar", 0)


def _minutes_since(start, at):
    try:
        t0 = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(at, "%Y-%m-%d %H:%M:%S") if at else datetime.now()
    except (TypeError, ValueError):
        return 0
    return (t1 - t0).total_seconds() / 60


def _win(save, cur, problem, at=None):
    run = save["run"]
    rng = _rng(run, "win")
    t = cur["type"]
    base_xp = engine.DIFF_XP.get(problem.get("difficulty"), 10)
    mult = {"fight": 1, "elite": 2, "boss": 3}[t] * (1.3 if _has(run, "big_o") else 1) * _scholar(save)
    bonus = 1.0  # 同時乘在經驗和金幣上
    notes = []
    mins = _minutes_since(cur.get("started_at"), at)
    rule = cur.get("rule")
    if rule == "timed" and mins > 25:
        bonus *= 0.5
        notes.append("超過 25 分鐘，獎勵減半")
    elif rule == "fury":
        bonus *= 1.5
    elif rule == "first" and cur.get("wrong", 0) == 0 and len(cur.get("seen", [])) <= 1:
        bonus *= 2
        notes.append("一擊必殺！獎勵 ×2")
    if cur.get("blitz") and mins <= 15:
        bonus *= 1.5
        notes.append("鬥志全開：15 分鐘內擊敗，獎勵 ×1.5")
    if cur.get("frost"):
        mult *= 2
    if _syn(run, "constant_time") and "hash-table" in problem.get("tags", []):
        mult *= 1.2
    mult *= _eff_mult(run, "xp_mult")
    hint = cur.get("hint_level", 0) - cur.get("free_hints", 0)
    if hint > 0:
        mult *= max(0.0, 1 - 0.15 * hint)
        notes.append(f"用了 {hint} 階提示，經驗 -{15 * hint}%")
    persona = run.get("persona")
    run["streak"] = run.get("streak", 0) + 1 if cur.get("wrong", 0) == 0 else 0
    if persona == "p1":  # 米菈：連勝加成
        mult *= 1 + min(0.3, 0.1 * run["streak"])
    elif persona == "p2":  # 夏音：連續天數加成
        mult *= 1 + min(0.21, 0.03 * run.get("dayStreak", 0))
    elif persona == "p3":  # 雪奈：經驗 +25%
        mult *= 1.25
    elif persona == "p6" and t == "boss":  # 珂可：Boss 經驗 +30%
        mult *= 1.3
    xp = int(round(base_xp * mult * bonus))
    run["xp"] += xp
    gold = {"fight": rng.randint(14, 24), "elite": rng.randint(30, 42), "boss": 80}[t]
    if t == "elite" and _has(run, "compiler_heart"):
        gold += 25
    if _has(run, "hash_charm") and "hash-table" in problem.get("tags", []):
        gold += 15
    gold = gold * bonus * (0.75 if _asc(run) >= 6 else 1) * _eff_mult(run, "gold_mult")
    gold = _gain_gold(run, int(round(gold)))
    if _has(run, "coffee"):
        _heal(run, 6)
    if _syn(run, "caffeine_rush"):
        _heal(run, 4)
    if _eff_sum(run, "heal_on_win"):
        _heal(run, _eff_sum(run, "heal_on_win"))
    run["kills"] += 1
    run["cleared"].append(cur["key"])
    run["current"] = None
    ev = [{"kind": "win", "type": t, "title": problem.get("title"), "xp": xp, "gold": gold, "notes": notes}]
    _log(run, f"擊敗「{problem.get('title')}」！經驗 +{xp}、金幣 +{gold}" + (f"（{'；'.join(notes)}）" if notes else ""))
    if t == "elite":
        run["pending"] = {"kind": "relic", "title": "精英掉落", "options": _relic_options(run, rng)}
    if t == "boss":
        ev += _finish(save, won=True)
    return ev


def _finish(save, won):
    run = save["run"]
    meta = save["meta"]
    floors = len(run["cleared"])
    shards = floors * 3 + run["gold"] // 10 + (60 if won else 0)
    if won and _syn(run, "kings_return"):
        shards += 30
    shards = int(round(shards * (1 + 0.1 * _asc(run))))
    meta["shards"] += shards
    if won and not run.get("daily"):
        meta["asc_max"] = max(meta.get("asc_max", 0), min(ASC_MAX, _asc(run) + 1))
    meta["synergies_seen"] = sorted(set(meta.get("synergies_seen", [])) | set(active_synergies(run)))
    meta["bonus_xp"] += run["xp"]
    run["status"] = "won" if won else "dead"
    run["current"] = None
    run["pending"] = None
    run["result"] = {"won": won, "floors": floors, "shards": shards, "xp": run["xp"], "kills": run["kills"],
                     "asc": _asc(run), "unlocked": meta.get("asc_max", 0) if won and not run.get("daily") else None}
    if run.get("daily"):
        code = _result_code(run, won, floors)
        mins = int(code.split("-")[4][:-1])
        res = {"day": run["daily"], "code": code, "won": won, "floors": floors,
               "hp": max(0, run["hp"]), "minutes": mins, "at": NOW()}
        daily = meta.setdefault("daily", {})
        prev = daily.get(run["daily"])
        res["tries"] = (prev or {}).get("tries", 0) + 1
        if _better(res, prev):
            daily[run["daily"]] = res
        else:
            prev["tries"] = res["tries"]
        for old in sorted(daily)[:-30]:  # 只留最近 30 天
            del daily[old]
        run["result"]["code"] = code
    meta["history"].insert(0, {
        "ended_at": NOW(), "won": won, "floors": floors, "kills": run["kills"],
        "xp": run["xp"], "shards": shards, "relics": list(run["relics"]), "seed": run["seed"],
        "asc": _asc(run), "daily": run.get("daily"),
    })
    del meta["history"][20:]
    _log(run, "征服了演算法地城！" if won else "倒下了……結晶會留下來。")
    return [{"kind": "won" if won else "dead", "shards": shards}]


def _die(save):
    return _finish(save, won=False)


def resolve(save, records, problems_by_slug):
    """看提交紀錄判定戰果：開戰後每一筆答錯扣血，第一筆通過就獲勝。

    不管是在遊戲畫面按「出招」，還是在終端機跑 python lc.py submit，都會被這裡判到。
    """
    run = save.get("run")
    events = []
    if not run or run["status"] != "active" or not run["current"] or not run["current"]["chosen"]:
        return events
    cur = run["current"]
    run["dayStreak"] = engine.day_streak(records)
    slug = cur["chosen"]
    rec = records.get(slug) or {}
    problem = problems_by_slug.get(slug) or {"title": rec.get("title", slug), "difficulty": rec.get("difficulty", "Easy"), "tags": []}
    for a in sorted(rec.get("attempts", []), key=lambda a: a.get("time") or ""):
        sid = a.get("submission_id")
        if sid in cur["seen"] or (a.get("time") or "") < cur["started_at"]:
            continue
        cur["seen"].append(sid)
        sealed = cur.get("rule") == "lang" and a.get("lang") and a.get("lang") != cur.get("rule_lang")
        if a.get("accepted") and not sealed:
            return events + _win(save, cur, problem, a.get("time"))
        dmg = _damage(run, cur)
        shielded = cur.pop("shield", False)
        cur["wrong"] += 1
        if not shielded:
            run["streak"] = 0
        _hurt(run, dmg)
        status = f"語言封印（要用 {LANG_NAMES[cur['rule_lang']]}）" if sealed else (a.get("status") or "答錯")
        events.append({"kind": "hit", "dmg": dmg, "status": status})
        if dmg:
            _log(run, f"{status}！受到 {dmg} 點傷害")
        else:
            _log(run, f"{status}……" + ("米菈的應援擋下了這一擊" if shielded else "小黃鴨幫你擋下這一擊"))
        if run["hp"] <= 0:
            return events + _die(save)
    return events


def flee(save):
    run = save["run"]
    cur = run["current"]
    if not cur:
        raise ValueError("現在沒有在戰鬥")
    dmg = int(NODE_TYPES[cur["type"]]["atk"] * 1.5)
    run["streak"] = 0
    _hurt(run, dmg)
    run["cleared"].append(cur["key"])
    run["current"] = None
    _log(run, f"撤退了，受到 {dmg} 點傷害")
    if cur["type"] == "boss" and run["hp"] > 0:
        # 從 Boss 撤退 = 遠征失敗，但不算死亡
        return _finish(save, won=False)
    return _die(save) if run["hp"] <= 0 else [{"kind": "flee", "dmg": dmg}]


def act(save, action, arg=None):
    """處理寶箱、篝火、商店、事件的選擇。"""
    run = save["run"]
    pend = run["pending"]
    if not pend:
        raise ValueError("沒有待處理的事件")
    kind = pend["kind"]
    if kind == "relic":
        if pend.get("gold"):
            _gain_gold(run, pend["gold"])
        if action == "pick" and arg in pend["options"]:
            _add_relic(run, arg)
        run["pending"] = None
    elif kind == "camp":
        if action == "rest":
            amt = int(run["max_hp"] * 0.3) * (2 if _has(run, "recursion_mirror") else 1)
            if run.get("persona") == "p7":  # 星璃：篝火回血 ×1.5
                amt = int(amt * 1.5)
            if _asc(run) >= 3:
                amt //= 2
            amt = int(amt * _eff_mult(run, "camp_mult"))
            got = _heal(run, amt)
            _log(run, f"在篝火旁休息，HP +{got}")
        elif action == "train":
            gain = 12 if _syn(run, "deep_stack") else 6
            run["max_hp"] += gain
            _heal(run, gain)
            _log(run, f"在篝火旁修練，最大 HP +{gain}")
        else:
            raise ValueError("篝火只能休息或修練")
        run["pending"] = None
    elif kind == "shop":
        if action == "buy":
            item = pend["items"][int(arg)]
            if item.get("sold"):
                raise ValueError("已經賣掉了")
            if run["gold"] < item["price"]:
                raise ValueError("金幣不夠")
            run["gold"] -= item["price"]
            item["sold"] = True
            if item["kind"] == "relic":
                _add_relic(run, item["id"])
            else:
                _heal(run, item["amount"])
                _log(run, f"買了回復藥水，HP +{item['amount']}")
            for it in pend["items"]:  # 剛湊齊「富可敵國」的話，剩下的東西馬上打折
                if not it.get("sold"):
                    it["price"] = _price(run, it.get("base", it["price"]))
            return []
        run["pending"] = None
    elif kind == "event":
        run["pending"] = None
    if run["pending"] is None and run["pos"]:
        if run["pos"] not in run["cleared"]:
            run["cleared"].append(run["pos"])
    return []


def use_skill(save, ctx):
    """發動流派技能（一局一次）。回傳事件。"""
    run = save.get("run")
    if not run or run["status"] != "active":
        raise ValueError("沒有進行中的遠征")
    if run.get("skill_used"):
        raise ValueError("這局已經用過技能了")
    sid = run.get("skill") or "p0"
    name, _, when = SKILLS[sid]
    cur = run.get("current")
    if when in ("battle", "pick", "fight") and not cur:
        raise ValueError(f"「{name}」要在戰鬥中才能用")
    if when == "pick" and cur.get("chosen"):
        raise ValueError(f"「{name}」要在選題之前用")
    if when == "fight" and cur["type"] != "fight":
        raise ValueError(f"「{name}」只能用在普通戰鬥")
    if sid == "p2" and run["hp"] >= run["max_hp"]:
        raise ValueError("HP 是滿的，先留著吧")
    if sid == "p7" and run.get("dmg_taken", 0) < 2:
        raise ValueError("這局還沒受過傷，先留著吧")
    events = [{"kind": "skill", "name": name}]
    if sid == "p0":
        run["used_slugs"] += [o["slug"] for o in cur["offers"]]
        cur["offers"], _ = _offers(run, ctx, cur["type"], salt=f"star{len(run['used_slugs'])}", easier=100)
        msg = "星之指引：換了一批比較好打的題目"
    elif sid == "p1":
        cur["shield"] = True
        msg = "全力應援：下一次答錯不扣血"
    elif sid == "p2":
        msg = f"節拍回復：HP +{_heal(run, int(run['max_hp'] * 0.25))}"
    elif sid == "p3":
        cur["frost"] = True
        msg = "冰霜試煉：這場經驗 ×2，傷害 ×1.5"
    elif sid == "p4":
        cur["free_hints"] = 2
        msg = "學者之眼：提示第 1、2 階免費"
    elif sid == "p5":
        run["cleared"].append(cur["key"])
        run["current"] = None
        msg = "月影步：悄悄繞過了這場戰鬥"
    elif sid == "p6":
        cur["blitz"] = True
        msg = "鬥志全開：15 分鐘內擊敗，獎勵 ×1.5"
    else:
        amt = min(30, run.get("dmg_taken", 0) // 2)
        msg = f"時光回溯：HP +{_heal(run, amt)}"
    run["skill_used"] = True
    _log(run, msg)
    return events


def note_hint(save, slug, level):
    """打開了第 level 階提示：如果正在打這題，記到這場戰鬥上（影響經驗）。"""
    run = save.get("run")
    cur = (run or {}).get("current")
    if run and run["status"] == "active" and cur and cur.get("chosen") == slug:
        cur["hint_level"] = max(cur.get("hint_level", 0), level)


def abandon(save):
    if save.get("run") and save["run"]["status"] == "active":
        return _finish(save, won=False)
    return []


def buy_upgrade(save, uid):
    meta = save["meta"]
    name, _, cap, cost = UPGRADES[uid]
    lv = meta["upgrades"].get(uid, 0)
    if lv >= cap:
        raise ValueError("已經滿級了")
    price = cost(lv)
    if meta["shards"] < price:
        raise ValueError("結晶不夠")
    meta["shards"] -= price
    meta["upgrades"][uid] = lv + 1


# ---------------------------------------------------------------------------
# 賞金任務（廣告推薦接受後）：在期限內解掉就拿雙倍經驗與結晶
# ---------------------------------------------------------------------------
def accept_bounty(save, rec, was_solved=False):
    save["meta"]["bounties"][rec["slug"]] = {
        "title": rec["title"], "difficulty": rec["difficulty"], "accepted_at": NOW(), "xp": rec["xp"],
        "review": bool(was_solved),  # 複習題：一定要在接下之後重新通過一次才算
    }


def resolve_bounties(save, records):
    events = []
    b = save["meta"]["bounties"]
    for slug in list(b):
        r = records.get(slug) or {}
        if not r.get("solved"):
            continue
        ok = any(a.get("accepted") and (a.get("time") or "") >= b[slug]["accepted_at"] for a in r.get("attempts", []))
        if ok or (r.get("solved_via") and not b[slug].get("review")):
            info = b.pop(slug)
            used = (save["meta"].get("hints") or {}).get(slug, 0)  # 開過提示，賞金照比例減少
            bonus = int(info["xp"] * _scholar(save) * max(0.0, 1 - 0.15 * used))
            save["meta"]["bonus_xp"] += bonus
            save["meta"]["shards"] += 5
            events.append({"kind": "bounty", "title": info["title"], "xp": bonus, "shards": 5})
    return events


def public_relics():
    out = {k: {"name": v[0], "glyph": v[1], "desc": v[2]} for k, v in RELICS.items()}
    for k, m in MOD_RELICS.items():
        out[k] = {"name": m["name"], "glyph": m["glyph"], "desc": m["desc"], "mod": m.get("mod")}
    return out


def public_skills():
    return {k: {"name": v[0], "desc": v[1], "when": v[2]} for k, v in SKILLS.items()}


def public_rules():
    return {k: {"name": v[0], "desc": v[1]} for k, v in BOSS_RULES.items()}


def public_ascension(save):
    top = save["meta"].get("asc_max", 0)
    return {"max": top, "levels": [{"level": i, "name": a[0], "desc": a[1], "unlocked": i <= top}
                                   for i, a in enumerate(ASCENSION) if a]}


def public_synergies(save):
    seen = set(save["meta"].get("synergies_seen", []))
    run = save.get("run")
    if run:
        seen |= set(active_synergies(run))
    out = []
    for sid, (name, pair, desc) in SYNERGIES.items():
        out.append({"id": sid, "name": name, "relics": list(pair), "desc": desc, "seen": sid in seen})
    for sid, (name, pair, desc, _) in MOD_SYNERGIES.items():
        out.append({"id": sid, "name": name, "relics": list(pair), "desc": desc, "seen": sid in seen, "mod": True})
    return out


def public_upgrades(save):
    out = []
    for uid, (name, desc, cap, cost) in UPGRADES.items():
        lv = save["meta"]["upgrades"].get(uid, 0)
        out.append({"id": uid, "name": name, "desc": desc, "level": lv, "cap": cap,
                    "price": cost(lv) if lv < cap else None})
    return out
