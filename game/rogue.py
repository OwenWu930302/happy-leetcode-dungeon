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
    pool = [r for r in RELICS if r not in run["relics"]]
    rng.shuffle(pool)
    return pool[:n]


def _add_relic(run, rid):
    if rid in run["relics"]:
        return
    run["relics"].append(rid)
    if rid == "stack_amulet":
        run["max_hp"] += 15
        _heal(run, 15)
    _log(run, f"獲得遺物「{RELICS[rid][0]}」")


def start_run(save, seed=None, persona="p0"):
    meta = save["meta"]
    seed = seed if seed is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    ups = meta["upgrades"]
    max_hp = 60 + 10 * ups.get("vitality", 0)
    run = {
        "seed": seed, "started_at": NOW(), "status": "active",
        "hp": max_hp, "max_hp": max_hp, "gold": 25 * ups.get("purse", 0),
        "relics": [], "map": gen_map(rng, mystery_boost=(persona == "p5")), "pos": None, "cleared": [],
        "current": None, "pending": None, "xp": 0, "kills": 0, "log": [], "used_slugs": [],
        "persona": persona, "streak": 0, "dayStreak": 0,
    }
    if ups.get("starter"):
        _add_relic(run, rng.choice(list(RELICS)))
    meta["runs_started"] = meta.get("runs_started", 0) + 1
    _log(run, f"第 {meta['runs_started']} 次遠征開始！種子 #{seed}")
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


def _offers(run, ctx, ntype, salt=""):
    spec = NODE_TYPES[ntype]
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
        _log(run, f"遭遇{NODE_TYPES[t]['name']}！")
    elif t == "chest":
        run["pending"] = {"kind": "relic", "title": "寶箱", "options": _relic_options(run, rng), "gold": 20}
        _log(run, "打開了寶箱")
    elif t == "camp":
        run["pending"] = {"kind": "camp"}
    elif t == "shop":
        opts = _relic_options(run, rng, 3)
        run["pending"] = {"kind": "shop", "items": [
            {"kind": "relic", "id": r, "price": rng.choice([55, 65, 75, 85])} for r in opts
        ] + [{"kind": "heal", "amount": 20, "price": 30}]}
    elif t == "mystery":
        title, text, eff = rng.choice(EVENTS)
        parts = []
        if eff.get("maxhp"):
            run["max_hp"] += eff["maxhp"]
            parts.append(f"最大 HP +{eff['maxhp']}")
        if eff.get("heal"):
            got = _heal(run, eff["heal"])
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
    if not free:
        _heal(run, -5)
    cur["rerolled"] = True
    run["used_slugs"] += [o["slug"] for o in cur["offers"]]
    cur["offers"], _ = _offers(run, ctx, cur["type"], salt=f"reroll{len(run['used_slugs'])}")
    _log(run, "換了一批題目" + ("（招財貓免費）" if free else "，HP -5"))
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
    if _has(run, "rubber_duck") and cur["wrong"] == 0:
        atk = 0
    return int(round(atk))


def _scholar(save):
    return 1 + 0.1 * save["meta"]["upgrades"].get("scholar", 0)


def _win(save, cur, problem):
    run = save["run"]
    rng = _rng(run, "win")
    t = cur["type"]
    base_xp = engine.DIFF_XP.get(problem.get("difficulty"), 10)
    mult = {"fight": 1, "elite": 2, "boss": 3}[t] * (1.3 if _has(run, "big_o") else 1) * _scholar(save)
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
    xp = int(round(base_xp * mult))
    run["xp"] += xp
    gold = {"fight": rng.randint(14, 24), "elite": rng.randint(30, 42), "boss": 80}[t]
    if t == "elite" and _has(run, "compiler_heart"):
        gold += 25
    if _has(run, "hash_charm") and "hash-table" in problem.get("tags", []):
        gold += 15
    gold = _gain_gold(run, gold)
    if _has(run, "coffee"):
        _heal(run, 6)
    run["kills"] += 1
    run["cleared"].append(cur["key"])
    run["current"] = None
    ev = [{"kind": "win", "type": t, "title": problem.get("title"), "xp": xp, "gold": gold}]
    _log(run, f"擊敗「{problem.get('title')}」！經驗 +{xp}、金幣 +{gold}")
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
    meta["shards"] += shards
    meta["bonus_xp"] += run["xp"]
    run["status"] = "won" if won else "dead"
    run["current"] = None
    run["pending"] = None
    run["result"] = {"won": won, "floors": floors, "shards": shards, "xp": run["xp"], "kills": run["kills"]}
    meta["history"].insert(0, {
        "ended_at": NOW(), "won": won, "floors": floors, "kills": run["kills"],
        "xp": run["xp"], "shards": shards, "relics": list(run["relics"]), "seed": run["seed"],
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
        if a.get("accepted"):
            return events + _win(save, cur, problem)
        dmg = _damage(run, cur)
        cur["wrong"] += 1
        run["streak"] = 0
        _heal(run, -dmg)
        events.append({"kind": "hit", "dmg": dmg, "status": a.get("status")})
        _log(run, f"{a.get('status') or '答錯'}！受到 {dmg} 點傷害" if dmg else "答錯了，小黃鴨幫你擋下這一擊")
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
    _heal(run, -dmg)
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
            got = _heal(run, amt)
            _log(run, f"在篝火旁休息，HP +{got}")
        elif action == "train":
            run["max_hp"] += 6
            _heal(run, 6)
            _log(run, "在篝火旁修練，最大 HP +6")
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
            return []
        run["pending"] = None
    elif kind == "event":
        run["pending"] = None
    if run["pending"] is None and run["pos"]:
        if run["pos"] not in run["cleared"]:
            run["cleared"].append(run["pos"])
    return []


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
            bonus = int(info["xp"] * _scholar(save))
            save["meta"]["bonus_xp"] += bonus
            save["meta"]["shards"] += 5
            events.append({"kind": "bounty", "title": info["title"], "xp": bonus, "shards": 5})
    return events


def public_relics():
    return {k: {"name": v[0], "glyph": v[1], "desc": v[2]} for k, v in RELICS.items()}


def public_upgrades(save):
    out = []
    for uid, (name, desc, cap, cost) in UPGRADES.items():
        lv = save["meta"]["upgrades"].get(uid, 0)
        out.append({"id": uid, "name": name, "desc": desc, "level": lv, "cap": cap,
                    "price": cost(lv) if lv < cap else None})
    return out
