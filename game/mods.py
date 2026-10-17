"""資料包（mods）：在工作區的 mods/ 資料夾放 JSON（和圖片），就能新增看板娘、遺物、事件、組合技。

只讀資料、不執行任何程式碼，所以別人的資料包不會帶病毒進來。
格式說明在 docs/MODS.md，範例在 docs/example-mod/。格式錯了，設定頁會告訴你是哪一行。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from game import rogue

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
IMAGE_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
MAX_IMAGE = 2 * 1024 * 1024
MODES = {"balanced", "comfort", "daily", "weakest", "tree", "explore", "contest", "review"}
LINE_KEYS = {"greet", "idle", "recommend", "choose", "testOk", "testFail", "win", "hit", "levelup",
             "lit", "bounty", "dead", "won", "login"}
EFFECT_RANGE = {"heal_on_win": (0, 20), "gold_mult": (0.5, 2.0), "xp_mult": (0.5, 2.0), "dmg_mult": (0.5, 1.5),
                "max_hp": (0, 30), "camp_mult": (0.5, 3.0)}
EVENT_RANGE = {"heal": (-30, 30), "gold": (0, 100), "maxhp": (0, 15), "xp": (0, 60), "relic": (0, 1)}


class ModError(Exception):
    pass


def mods_dir(root: Path) -> Path:
    return Path(root) / "mods"


def _line_of(text: str, needle: str) -> int | None:
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else None


class _Checker:
    def __init__(self, text: str, label: str):
        self.text, self.label, self.errors = text, label, []

    def err(self, where: str, msg: str, item_id: str | None = None):
        line = _line_of(self.text, f'"{item_id}"') if item_id else None
        self.errors.append(f"{self.label}{f' 第 {line} 行附近' if line else ''}：{where} {msg}")

    def text_field(self, obj, key, where, item_id=None, max_len=200, required=True):
        v = obj.get(key)
        if v is None:
            if required:
                self.err(where, f"缺少「{key}」", item_id)
            return None
        if not isinstance(v, str) or not v.strip():
            self.err(where, f"「{key}」要是一段文字", item_id)
            return None
        if len(v) > max_len:
            self.err(where, f"「{key}」太長了（最多 {max_len} 字）", item_id)
            return None
        return v.strip()

    def number(self, v, lo, hi, where, key, item_id, integer=False):
        ok = isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi
        if integer and ok and int(v) != v:
            ok = False
        if not ok:
            self.err(where, f"「{key}」要是 {lo} 到 {hi} 之間的{'整數' if integer else '數字'}", item_id)
        return ok

    def effects(self, eff, ranges, where, item_id):
        if eff is None:
            return {}
        if not isinstance(eff, dict):
            self.err(where, "效果（effect）要是一個物件", item_id)
            return {}
        out = {}
        for k, v in eff.items():
            if k not in ranges:
                self.err(where, f"不認得的效果「{k}」，可以用：{'、'.join(ranges)}", item_id)
                continue
            lo, hi = ranges[k]
            integer = isinstance(lo, int) and isinstance(hi, int)
            if self.number(v, lo, hi, where, k, item_id, integer):
                out[k] = int(v) if integer else float(v)
        return out


def _load_one(path: Path, folder: Path | None):
    """讀一個資料包，回傳 (資訊, 角色, 遺物, 事件, 組合技)。只要有錯就整包不載入。"""
    label = path.name if folder is None else f"{folder.name}/{path.name}"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise ModError(f"{label}：讀不到檔案（{e}）")
    if len(text) > 1_000_000:
        raise ModError(f"{label}：檔案太大了（最多 1 MB）")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ModError(f"{label} 第 {e.lineno} 行第 {e.colno} 個字：JSON 格式錯誤（{e.msg}）")
    if not isinstance(data, dict):
        raise ModError(f"{label}：最外層要是一個物件 {{ … }}")
    c = _Checker(text, label)
    pack = data.get("id")
    if not isinstance(pack, str) or not ID_RE.match(pack):
        c.err("資料包", "的「id」要是 1～32 個小寫英文、數字、- 或 _")
        raise ModError("\n".join(c.errors))
    info = {"id": pack, "name": c.text_field(data, "name", "資料包", max_len=40) or pack,
            "version": str(data.get("version", "1.0"))[:16], "author": str(data.get("author", ""))[:40],
            "description": str(data.get("description", ""))[:300], "file": label}

    companions, relics, events, synergies = [], {}, [], {}
    for i, ch in enumerate(data.get("companions") or []):
        where = f"companions[{i}]"
        cid = ch.get("id") if isinstance(ch, dict) else None
        if not isinstance(cid, str) or not ID_RE.match(cid):
            c.err(where, "的「id」要是小寫英文、數字、- 或 _", None)
            continue
        item = {"id": f"mod-{pack}-{cid}", "mod": pack}
        for key, n in (("name", 12), ("title", 20), ("intro", 300), ("style", 120), ("perk", 120)):
            item[key] = c.text_field(ch, key, where, cid, n, required=key in ("name", "title", "intro"))
        item["perk"] = item["perk"] or "沒有特殊加成"
        item["style"] = item["style"] or "依她的推薦策略挑題"
        st = ch.get("strategy") or {}
        mode = st.get("mode", "balanced")
        if mode not in MODES:
            c.err(where, f"的 strategy.mode 要是其中之一：{'、'.join(sorted(MODES))}", cid)
        off, width = st.get("offset", 80), st.get("width", 180)
        c.number(off, -300, 400, where, "strategy.offset", cid, True)
        c.number(width, 80, 400, where, "strategy.width", cid, True)
        item["strategy"] = {"mode": mode, "offset": off, "width": width}
        skill = ch.get("skill", "p0")
        if skill not in rogue.SKILLS:
            c.err(where, f"的「skill」要是 p0～p7 其中之一（沿用那位看板娘的流派技能）", cid)
        item["skill"] = skill
        lines = ch.get("lines") or {}
        if not isinstance(lines, dict):
            c.err(where, "的「lines」要是一個物件", cid)
            lines = {}
        clean = {}
        for k, v in lines.items():
            if k not in LINE_KEYS:
                c.err(where, f"的台詞種類「{k}」不認得，可以用：{'、'.join(sorted(LINE_KEYS))}", cid)
            elif not isinstance(v, list) or not all(isinstance(x, str) and 0 < len(x) <= 120 for x in v):
                c.err(where, f"的台詞「{k}」要是文字清單，每句 120 字以內", cid)
            else:
                clean[k] = v[:20]
        item["lines"] = clean
        img = ch.get("image")
        if img:
            if folder is None:
                c.err(where, "有圖片的話，資料包要放在自己的資料夾裡（mods/你的資料包/mod.json）", cid)
            else:
                f = (folder / str(img)).resolve()
                if folder.resolve() not in f.parents or f.suffix.lower() not in IMAGE_EXT or not f.is_file():
                    c.err(where, f"的圖片「{img}」找不到，或不是 PNG／JPG／WebP／GIF", cid)
                elif f.stat().st_size > MAX_IMAGE:
                    c.err(where, f"的圖片「{img}」太大了（最多 2 MB）", cid)
                else:
                    item["image"] = f"/mod-asset/{pack}/{f.relative_to(folder.resolve()).as_posix()}"
        companions.append(item)

    for i, r in enumerate(data.get("relics") or []):
        where = f"relics[{i}]"
        rid = r.get("id") if isinstance(r, dict) else None
        if not isinstance(rid, str) or not ID_RE.match(rid):
            c.err(where, "的「id」要是小寫英文、數字、- 或 _")
            continue
        name = c.text_field(r, "name", where, rid, 16)
        glyph = c.text_field(r, "glyph", where, rid, 2)
        desc = c.text_field(r, "desc", where, rid, 120)
        eff = c.effects(r.get("effect"), EFFECT_RANGE, where, rid)
        if not eff:
            c.err(where, "至少要有一個效果（effect）", rid)
        relics[f"mod-{pack}-{rid}"] = {"name": name, "glyph": glyph, "desc": desc, "effect": eff, "mod": pack}

    for i, ev in enumerate(data.get("events") or []):
        where = f"events[{i}]"
        if not isinstance(ev, dict):
            c.err(where, "要是一個物件")
            continue
        title = c.text_field(ev, "title", where, None, 30)
        text_ = c.text_field(ev, "text", where, None, 200)
        eff = c.effects(ev.get("effects"), EVENT_RANGE, where, None)
        if not eff:
            c.err(where, "至少要有一個效果（effects）")
        events.append((title, text_, eff, pack))

    for i, sy in enumerate(data.get("synergies") or []):
        where = f"synergies[{i}]"
        sid = sy.get("id") if isinstance(sy, dict) else None
        if not isinstance(sid, str) or not ID_RE.match(sid):
            c.err(where, "的「id」要是小寫英文、數字、- 或 _")
            continue
        name = c.text_field(sy, "name", where, sid, 16)
        desc = c.text_field(sy, "desc", where, sid, 120)
        pair = sy.get("relics")
        ids = []
        if not isinstance(pair, list) or len(pair) != 2:
            c.err(where, "的「relics」要剛好列出兩件遺物", sid)
        else:
            for rid in pair:
                full = rid if rid in rogue.RELICS else f"mod-{pack}-{rid}"
                if full not in rogue.RELICS and full not in relics:
                    c.err(where, f"用到的遺物「{rid}」不存在（可以用內建遺物，或這個資料包自己的遺物）", sid)
                ids.append(full)
        eff = c.effects(sy.get("effect"), EFFECT_RANGE, where, sid)
        if not eff:
            c.err(where, "至少要有一個效果（effect）", sid)
        synergies[f"mod-{pack}-{sid}"] = (name, tuple(ids), desc, eff)

    if not (companions or relics or events or synergies) and not c.errors:
        c.err("資料包", "裡沒有任何內容（companions、relics、events、synergies 都是空的）")
    if c.errors:
        raise ModError("\n".join(c.errors[:20]))
    info["counts"] = {"companions": len(companions), "relics": len(relics), "events": len(events),
                      "synergies": len(synergies)}
    return info, companions, relics, events, synergies


def load_all(root: Path) -> dict:
    """重新讀取全部資料包，註冊到遊戲裡。回傳 {"mods": [...], "companions": [...], "dir": ...}。"""
    rogue.MOD_RELICS.clear()
    rogue.MOD_EVENTS.clear()
    rogue.MOD_SYNERGIES.clear()
    d = mods_dir(root)
    out = {"mods": [], "companions": [], "dir": str(d), "folders": {}}
    if not d.is_dir():
        return out
    files = [(f, None) for f in sorted(d.glob("*.json"))]
    files += [(sub / "mod.json", sub) for sub in sorted(p for p in d.iterdir() if p.is_dir()) if (sub / "mod.json").is_file()]
    seen = set()
    for f, folder in files[:50]:
        try:
            info, comps, relics, events, syns = _load_one(f, folder)
            if info["id"] in seen:
                raise ModError(f"{info['file']}：資料包 id「{info['id']}」跟另一個資料包重複了")
            seen.add(info["id"])
        except ModError as e:
            out["mods"].append({"file": f.name if folder is None else f"{folder.name}/mod.json",
                                "ok": False, "errors": str(e).split("\n")})
            continue
        rogue.MOD_RELICS.update(relics)
        rogue.MOD_EVENTS.extend(events)
        rogue.MOD_SYNERGIES.update(syns)
        out["companions"].extend(comps)
        if folder is not None:
            out["folders"][info["id"]] = folder
        out["mods"].append({**info, "ok": True, "errors": []})
    return out


def asset_path(loaded: dict, pack: str, rel: str) -> Path | None:
    """資料包圖片的實際路徑；不在那個資料夾裡、或副檔名不對就回傳 None。"""
    folder = loaded.get("folders", {}).get(pack)
    if not folder:
        return None
    f = (Path(folder) / rel).resolve()
    if Path(folder).resolve() not in f.parents or f.suffix.lower() not in IMAGE_EXT or not f.is_file():
        return None
    return f
