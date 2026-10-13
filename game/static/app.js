/* 開心每日刷題 · 演算法地城 —— 前端 */
"use strict";

const TOKEN = document.querySelector('meta[name="game-token"]').content;
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let S = null;                 // 伺服器狀態
let tab = "home";
let focusSlug = null;         // 目前在看的題目
let selNode = null;           // 技能樹選中的節點
let lastResult = {};          // slug -> {kind, result, accepted}
const probCache = {};
let tagRecs = {};
let firstLoad = true;
let prevLit = new Set();
let prevLevel = 0;

try { focusSlug = localStorage.getItem("focusSlug") || null; tab = localStorage.getItem("tab") || "home"; } catch (e) {}

/* ================= API ================= */
const OFFLINE_MSG = "遊戲斷線了，請重新開啟遊戲後再試一次。";
let offlineTimer = null, lastNetError = "";

function setOffline(on) {
  let bar = document.getElementById("offline");
  if (!on) {
    if (bar) bar.remove();
    clearInterval(offlineTimer); offlineTimer = null;
    return;
  }
  if (!bar) {
    bar = document.createElement("div");
    bar.id = "offline";
    bar.className = "offline";
    bar.setAttribute("role", "alert");
    bar.innerHTML = `<div class="offline-main"><b>遊戲斷線了</b><span>請重新開啟遊戲後再試一次。<i class="offline-retry">正在自動重新連線…</i></span></div>
      <details class="offline-tech"><summary>技術細節</summary>
        <div>原始錯誤：<code id="offlineErr"></code></div>
        <div>連線位址：<code>${esc(location.origin)}</code></div>
        <div>可能原因：遊戲程式（LeetCodeDungeon.exe 的黑色視窗，或執行 <code>python lc.py game</code> 的終端機）被關閉，或電腦睡眠後連線中斷。</div>
      </details>`;
    document.body.prepend(bar);
  }
  bar.querySelector("#offlineErr").textContent = lastNetError || "Failed to fetch";
  if (!offlineTimer) offlineTimer = setInterval(reconnect, 3000);
}

async function reconnect() {
  let res;
  try { res = await fetch("/api/state", { headers: { "X-Game-Token": TOKEN } }); } catch (e) { return; }
  if (res.status === 403) return location.reload(); // 遊戲重新啟動過，換了新的連線權杖
  if (!res.ok) return;
  setOffline(false);
  try { applyState(await res.json()); toast("info", "重新連上了"); } catch (e) {}
}

async function api(path, body) {
  const opt = { headers: { "X-Game-Token": TOKEN } };
  if (body !== undefined) {
    opt.method = "POST";
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, opt);
  } catch (e) {
    lastNetError = (e && e.message) || "Failed to fetch";
    setOffline(true);
    throw new Error(OFFLINE_MSG);
  }
  if (res.status === 403) {
    // 遊戲重新啟動過：舊頁面的權杖失效，重新整理就好
    toast("info", "遊戲重新啟動過了", "正在重新整理頁面…");
    setTimeout(() => location.reload(), 1200);
    throw new Error("正在重新整理頁面…");
  }
  const data = await res.json().catch(() => ({ error: `伺服器回應怪怪的（${res.status}），請重新整理頁面。` }));
  if (!res.ok || data.error) throw new Error(data.error || `錯誤 ${res.status}`);
  return data;
}

async function act(path, body, busyText) {
  if (busyText) busy(true, busyText);
  try {
    const st = await api(path, body ?? {});
    if (st.player) applyState(st);
    return st;
  } catch (e) {
    toast("info", "出了點狀況", e.message);
    if (e.message !== OFFLINE_MSG) say(`唔……<em>${esc(e.message).slice(0, 80)}</em>`);
    else say("連不上遊戲了……重新開啟遊戲後我就回來！");
    return null;
  } finally {
    if (busyText) busy(false);
  }
}

/* ================= 看板娘／頭像 ================= */
// 每一款都是用同一套參數化畫法生成的原創角色：髮色、瞳色、配件不同
const AVATARS = [
  { id: "p0", name: "露緹", hair: ["#5d63a3", "#2c2f58"], bang: ["#7a80c4", "#454a86"], eye: ["#ffe2a0", "#e9ab47", "#8a4f12"], acc: "star", tie: "#e9ab47" },
  { id: "p1", name: "米菈", hair: ["#f29cbc", "#b4507a"], bang: ["#ffc2d8", "#d8739c"], eye: ["#d4f1ff", "#5fb7e8", "#1d5a8a"], acc: "ribbon", tie: "#ff7fae" },
  { id: "p2", name: "夏音", hair: ["#f0a04b", "#a9541b"], bang: ["#ffc177", "#d27a2c"], eye: ["#d9ffd9", "#5cc77c", "#1d6b3a"], acc: "phones", tie: "#5cc77c" },
  { id: "p3", name: "雪奈", hair: ["#e8eef7", "#a8b4c8"], bang: ["#ffffff", "#c6d0e0"], eye: ["#ffd0d0", "#e05a5a", "#7a1a1a"], acc: "cat", tie: "#e05a5a" },
  { id: "p4", name: "琥珀", hair: ["#8a5a3a", "#4a2a18"], bang: ["#a8744d", "#6a3f22"], eye: ["#fff0b0", "#e0a030", "#7a4a0a"], acc: "glasses", tie: "#c98626" },
  { id: "p5", name: "夜櫻", hair: ["#2a2438", "#0e0b16"], bang: ["#3e3654", "#1a1528"], eye: ["#ffd6ec", "#f06aa8", "#7a1f4e"], acc: "flower", tie: "#f06aa8" },
  { id: "p6", name: "珂可", hair: ["#3fb3a8", "#1a5f5a"], bang: ["#6fd6cb", "#2a8a80"], eye: ["#fff3c4", "#ffd27a", "#9a6a10"], acc: "horns", tie: "#ffd27a" },
  { id: "p7", name: "星璃", hair: ["#f5d97a", "#c49a2a"], bang: ["#fff0a8", "#e0bb4a"], eye: ["#efe0ff", "#a98be0", "#4a2a8a"], acc: "halo", tie: "#a98be0" },
];
const ACC = {
  star: (a) => `<path d="M71 26 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2 z" fill="#ffd27a"/>`,
  ribbon: (a) => `<path d="M62 22 l12 -8 -2 12 z M62 22 l14 4 -10 6 z" fill="${a.tie}"/><circle cx="63" cy="23" r="3" fill="#fff4"/>`,
  phones: (a) => `<path d="M24 50 C22 24 78 24 76 50" fill="none" stroke="#2a2f40" stroke-width="5"/><rect x="18" y="46" width="10" height="16" rx="4" fill="${a.tie}"/><rect x="72" y="46" width="10" height="16" rx="4" fill="${a.tie}"/>`,
  cat: (a) => `<path d="M26 30 L22 8 L42 22 Z M74 30 L78 8 L58 22 Z" fill="${a.hair[0]}"/><path d="M28 26 L26 14 L37 22 Z M72 26 L74 14 L63 22 Z" fill="#f4b6c2"/>`,
  glasses: () => `<g fill="none" stroke="#3a2a1a" stroke-width="1.6"><circle cx="41" cy="58" r="7"/><circle cx="59" cy="58" r="7"/><path d="M48 58 h4"/></g>`,
  flower: (a) => `<g transform="translate(68 28)">${[0, 72, 144, 216, 288].map((r) => `<ellipse rx="3.2" ry="5.5" cy="-5" fill="#ffc6de" transform="rotate(${r})"/>`).join("")}<circle r="2.6" fill="#ffd27a"/></g>`,
  horns: () => `<path d="M32 26 C26 16 28 8 34 4 C32 12 36 18 38 22 Z M68 26 C74 16 72 8 66 4 C68 12 64 18 62 22 Z" fill="#e8d9b0" stroke="#8a7a50" stroke-width=".8"/>`,
  halo: () => `<ellipse cx="50" cy="12" rx="17" ry="4.5" fill="none" stroke="#ffe7ad" stroke-width="2.5"/>`,
};
let uidN = 0;
function avatarSVG(id) {
  const a = AVATARS.find((x) => x.id === id) || AVATARS[0];
  const u = "a" + (++uidN);
  const eyes = [41, 59].map((x, i) => `<ellipse cx="${x}" cy="57" rx="5" ry="6.2" fill="#fff"/><ellipse cx="${x}" cy="58" rx="3.8" ry="5.2" fill="url(#${u}I)"/><ellipse cx="${x}" cy="59" rx="1.6" ry="2.4" fill="${a.eye[2]}"/><circle cx="${x - 1.4}" cy="55.6" r="1.4" fill="#fff"/>
    <path d="${i ? "M53.5 52.2 Q59 49.5 64.5 52.5" : "M35.5 52.5 Q41 49.5 46.5 52.2"}" stroke="${a.hair[1]}" stroke-width="1.8" fill="none" stroke-linecap="round"/>`).join("");
  const behind = a.acc === "halo" || a.acc === "phones" ? "" : "";
  return `<svg viewBox="0 0 100 100" role="img" aria-label="${esc(a.name)}">
<defs><linearGradient id="${u}H" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a.hair[0]}"/><stop offset="1" stop-color="${a.hair[1]}"/></linearGradient>
<linearGradient id="${u}B" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${a.bang[0]}"/><stop offset="1" stop-color="${a.bang[1]}"/></linearGradient>
<radialGradient id="${u}I" cx=".5" cy=".35" r=".7"><stop offset="0" stop-color="${a.eye[0]}"/><stop offset=".55" stop-color="${a.eye[1]}"/><stop offset="1" stop-color="${a.eye[2]}"/></radialGradient></defs>
<circle cx="50" cy="50" r="48" fill="#141826" stroke="#2b3245"/>${behind}
${a.acc === "cat" ? ACC.cat(a) : ""}${a.acc === "horns" ? ACC.horns(a) : ""}
<path d="M19 58 C14 26 34 11 50 11 C66 11 86 26 81 58 L83 92 L67 81 L50 88 L33 81 L17 92 Z" fill="url(#${u}H)"/>
<path d="M36 76 L64 76 L70 100 L30 100 Z" fill="#232a40"/><path d="M44 76 L50 86 L56 76 Z" fill="${a.tie}"/>
<ellipse cx="50" cy="53" rx="22" ry="24" fill="#f4dfcc"/>
<ellipse cx="37" cy="64" rx="4.5" ry="2.4" fill="#f19a9a" opacity=".45"/><ellipse cx="63" cy="64" rx="4.5" ry="2.4" fill="#f19a9a" opacity=".45"/>
${eyes}
<path d="M47 67.5 Q50 70 53 67.5" stroke="#b5605a" stroke-width="1.4" fill="none" stroke-linecap="round"/>
<path d="M27 52 C26 31 38 22 50 22 C62 22 74 31 73 52 C69 42 63 37 59 35 C58 41 55 45 51 47 C50 41 47 37 43 36 C39 41 33 46 27 52 Z" fill="url(#${u}B)"/>
<path d="M50 23 C51 15 57 12 61 10 C57 15 55 18 53 24 Z" fill="${a.hair[0]}"/>
${a.acc !== "cat" && a.acc !== "horns" ? ACC[a.acc](a) : ""}</svg>`;
}
const profile = () => (S && S.profile) || { avatar: "p0", companion: "露緹", name: "", bg: "dungeon", dim: 0.55, uploads: {} };
function avatarHTML(p = profile()) {
  if (p.avatar === "upload" && p.uploads && p.uploads.avatar) return `<img src="/user-asset/avatar?v=${esc(p.uploads.avatar.split("v=")[1] || "1")}" alt="頭像">`;
  return avatarSVG(p.avatar);
}
let avatarKey = "";
function applyLook() {
  const p = profile();
  const key = [p.avatar, p.uploads?.avatar, p.bg, p.dim, p.uploads?.bg].join("|");
  if (key === avatarKey) return;
  avatarKey = key;
  $("#mascotBox").innerHTML = avatarHTML(p);
  document.body.dataset.bg = p.bg === "upload" && !p.uploads?.bg ? "dungeon" : p.bg;
  if (p.bg === "upload" && p.uploads?.bg) {
    const d = Number(p.dim ?? 0.55);
    document.body.style.backgroundImage = `linear-gradient(rgba(10,12,18,${d}),rgba(10,12,18,${d})),url("/user-asset/bg?v=${encodeURIComponent(p.uploads.bg.split("v=")[1] || "1")}")`;
  } else document.body.style.backgroundImage = "";
}
document.body.dataset.bg = "dungeon";
$("#mascotBox").innerHTML = avatarSVG("p0");
$("#mascotBox").addEventListener("click", () => setTab("settings"));

function say(html, bounce = true) {
  $("#say").innerHTML = html;
  if (bounce) {
    const m = $("#mascotBox");
    m.classList.remove("bounce"); void m.offsetWidth; m.classList.add("bounce");
  }
}
const IDLE = [
  "今天的委託在酒館公告板上，挑一題暖身吧。",
  "遠征裡答錯會被怪物打，但<em>試招</em>不扣血，先試再出招！",
  "技能樹會跟著題庫自己長大，遇到新標籤就會冒出新技能喔。",
  "我會偷偷看你的實力分，挑剛好打得贏的題目推給你。",
  "寫完記得按<em>出招</em>，或在 VS Code 按 Ctrl+Shift+B 提交。",
];

/* ================= 小工具 ================= */
function busy(on, text) { $("#busy").hidden = !on; if (text) $("#busyTxt").textContent = text; }

function toast(kind, title, text = "") {
  if (text === OFFLINE_MSG || title === OFFLINE_MSG) return; // 斷線已經有上方提示條，不重複通知
  const t = document.createElement("div");
  t.className = `toast ${kind}`;
  t.innerHTML = `<b>${esc(title)}</b>${text ? `<span>${esc(text)}</span>` : ""}`;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), kind === "info" ? 4200 : 5200);
}

function hitFx() {
  const f = $("#flash"); f.classList.remove("on"); void f.offsetWidth; f.classList.add("on");
  document.body.classList.remove("shake"); void document.body.offsetWidth; document.body.classList.add("shake");
}

function confetti(n = 90) {
  const cv = $("#fx"), ctx = cv.getContext("2d");
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  cv.width = innerWidth; cv.height = innerHeight;
  const colors = ["#ffd27a", "#e9ab47", "#73bccd", "#a98be0", "#ece2ca", "#62c494"];
  const ps = Array.from({ length: n }, () => ({
    x: innerWidth / 2 + (Math.random() - .5) * 200, y: innerHeight * .35,
    vx: (Math.random() - .5) * 12, vy: -Math.random() * 12 - 4, s: Math.random() * 6 + 3,
    c: colors[(Math.random() * colors.length) | 0], r: Math.random() * 6, vr: (Math.random() - .5) * .3,
  }));
  let frame = 0;
  (function tick() {
    ctx.clearRect(0, 0, cv.width, cv.height);
    for (const p of ps) {
      p.vy += .35; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c;
      ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2); ctx.restore();
    }
    if (++frame < 120) requestAnimationFrame(tick); else ctx.clearRect(0, 0, cv.width, cv.height);
  })();
}

const diffChip = (d) => `<span class="diff ${esc(d)}">${d === "Easy" ? "Easy" : d === "Medium" ? "Med" : "Hard"}</span>`;
const lcUrl = (slug) => `https://leetcode.com/problems/${slug}/`;
const nodeName = (id) => (S?.tree.nodes.find((n) => n.id === id) || {}).name || id;

function setTab(t) {
  tab = t;
  try { localStorage.setItem("tab", t); } catch (e) {}
  document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.tab === t));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${t}`));
  render();
  scrollTo({ top: 0 });
}
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));

function setFocus(slug) {
  focusSlug = slug;
  try { localStorage.setItem("focusSlug", slug || ""); } catch (e) {}
}

/* ================= 狀態套用 ================= */
function applyState(st) {
  const old = S;
  S = st;
  const lit = new Set(st.tree.nodes.filter((n) => n.lit).map((n) => n.id));
  if (!firstLoad) {
    const newly = [...lit].filter((id) => !prevLit.has(id));
    newly.forEach((id, i) => setTimeout(() => toast("win", `技能點亮：${nodeName(id)}`, "下一環的技能解鎖了"), 400 + i * 500));
    if (newly.length) { confetti(60); say(`<em>${newly.map(nodeName).join("、")}</em> 點亮了！去技能樹看看吧。`); }
    if (st.player.level > prevLevel) { toast("win", `升級！LV ${st.player.level}`, st.player.title); confetti(120); }
  }
  prevLit = lit; prevLevel = st.player.level;
  handleEvents(st.events || [], old);
  firstLoad = false;
  render();
}

function handleEvents(evts) {
  for (const e of evts) {
    if (e.kind === "hit") {
      hitFx();
      toast("hit", e.dmg ? `受到 ${e.dmg} 點傷害` : "小黃鴨擋下了這一擊", e.status || "答錯了");
      say(e.status === "Time Limit Exceeded" ? "太慢了！想想看能不能少一層迴圈？" :
          e.status === "Runtime Error" ? "程式炸掉了，檢查一下索引和空輸入。" : "痛！再看一次邊界條件和題目要求……");
    } else if (e.kind === "win") {
      confetti();
      toast("win", `擊敗「${e.title}」！`, `經驗 +${e.xp}　金幣 +${e.gold}`);
      say(["漂亮！這一擊乾淨俐落。", "贏了！往下一個節點前進吧。", "好強……你的戰力又往上爬了。"][Math.floor(Math.random() * 3)]);
      setTimeout(() => maybeAd(true), 9000);
    } else if (e.kind === "flee") {
      toast("hit", `撤退，受到 ${e.dmg} 點傷害`);
      say("撤退也是一種戰術，下次再來。");
    } else if (e.kind === "dead") {
      hitFx();
      say(`倒下了……不過留下了 <em>${e.shards}</em> 顆結晶，可以買永久強化。`);
    } else if (e.kind === "won") {
      confetti(200);
      say(`你征服了演算法地城！帶回 <em>${e.shards}</em> 顆結晶！`);
    } else if (e.kind === "bounty") {
      confetti();
      toast("win", `賞金達成：${e.title}`, `額外經驗 +${e.xp}　結晶 +${e.shards}`);
      say("賞金到手！廣告推薦的題目果然沒騙你吧。");
    } else if (e.kind === "login") {
      confetti(60);
      toast("win", `登入成功：${e.user}`, "現在可以試招、出招、同步官網進度了");
      say(`歡迎，<em>${esc(e.user)}</em>！要不要先同步一下官網進度？`);
    } else if (e.kind === "bountyAccepted") {
      toast("info", "賞金任務已接下", "解題檔已在 VS Code 開啟，解完就能領雙倍經驗");
    }
  }
}

/* ================= 渲染 ================= */
let problemSig = "";
let mapPosKey = "";
function render() {
  if (!S) return;
  // 重畫前記住捲動位置，輪詢更新時畫面不會跳
  const keep = [...document.querySelectorAll(".mapwrap, .treewrap")].map((e) => [e.className, e.scrollTop, e.scrollLeft]);
  renderHud();
  renderTabsDots();
  if (tab === "home") renderHome();
  if (tab === "run") renderRun();
  if (tab === "tree") renderTree();
  if (tab === "power") renderPower();
  if (tab === "problem") renderProblem();
  if (tab === "settings") renderSettings();
  renderDock();
  renderModal();
  for (const [cls, top, left] of keep) {
    const e = document.querySelector("." + cls.split(" ")[0]);
    if (e && !e.dataset.fresh) { e.scrollTop = top; e.scrollLeft = left; }
  }
}

function renderHud() {
  const p = S.player;
  applyLook();
  $("#sayWho").textContent = profile().companion || "露緹";
  $("#hName").textContent = profile().name || "";
  $("#hLv").textContent = p.level;
  $("#hTitle").textContent = p.title;
  $("#hPow").textContent = (p.power || 0).toLocaleString("en-US");
  $("#hRank").textContent = p.rank;
  $("#hPowBox").title = `實力分 ${p.rating}${p.official ? `（官方競賽分 ${p.official}）` : ""}`;
  $("#hShards").textContent = p.shards;
  const pct = Math.max(0, Math.min(100, ((p.xp - p.base) / (p.next - p.base)) * 100));
  $("#hXp").style.width = pct + "%";
  $("#hXpTxt").textContent = `${p.xp - p.base} / ${p.next - p.base} XP`;
  document.documentElement.style.setProperty("--hud-h", $(".hud").offsetHeight + "px");
}

function renderTabsDots() {
  const run = S.run;
  const fighting = run && run.status === "active" && (run.current || run.pending);
  const b = document.querySelector('.tabs [data-tab="run"] span');
  b.innerHTML = "遠征" + (fighting ? '<i class="dot"></i>' : "");
}

function questCard(q, opts = {}) {
  const bounty = S.meta.bounties[q.slug];
  return `<div class="quest ${opts.cls || ""}">
    <div class="q-top"><span class="q-id">#${esc(q.id)}</span>${diffChip(q.difficulty)}</div>
    <div class="q-title">${esc(q.title)}</div>
    ${q.reasons?.length ? `<ul class="q-why">${q.reasons.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
    <div class="q-meta">難度分 <b>${q.rating}</b>${(q.tagNames || []).slice(0, 3).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
    <div class="q-act">
      ${opts.choose ? `<button class="btn primary" data-choose="${esc(q.slug)}">選這隻開戰</button>` : ""}
      <button class="btn" data-view="${esc(q.slug)}">看題</button>
      ${opts.choose ? "" : bounty ? `<span class="chip">賞金進行中</span>` : `<button class="btn rune" data-bounty="${esc(q.slug)}">接賞金 ×2 XP</button>`}
    </div>
  </div>`;
}

/* ---------- 酒館 ---------- */
function renderHome() {
  const el = $("#tab-home");
  const lib = S.library;
  const bounties = Object.entries(S.meta.bounties);
  const run = S.run;
  el.innerHTML = `
    ${S.login ? "" : `<div class="notice">還沒登入 LeetCode，<b>試招／出招／同步</b>需要登入。到 <button class="btn ghost" data-go="settings" style="padding:2px 10px">設定 → 帳號</button> 貼上兩個 cookie 就好，不用密碼。</div>`}
    <div class="panel">
      <div class="eyebrow">今日委託 · Daily Quests</div>
      <h2>${esc(profile().companion || "露緹")}替你挑的三題</h2>
      <p class="muted" style="margin:0 0 12px">依你的實力分 ${S.player.rating} 和技能樹的弱點挑的，難度剛好在你「努力一下打得贏」的範圍。</p>
      <div class="quests">${S.picks.map((q) => questCard(q)).join("") || `<div class="empty">題庫裡的題目都被你解完了！試試「擴充題庫」。</div>`}</div>
    </div>
    <div class="grid2">
      <div class="panel">
        <div class="eyebrow">Expedition</div>
        <h2>演算法地城</h2>
        <p class="muted" style="margin:0 0 12px">${run && run.status === "active"
          ? `遠征進行中：HP ${run.hp}/${run.max_hp}，已走過 ${run.cleared.length} 個節點。`
          : "隨機生成的地城，答錯會扣血、通過拿遺物，Boss 從你最弱的技能出題。"}</p>
        <button class="btn primary" data-go="run">${run && run.status === "active" ? "繼續遠征" : "開始遠征"}</button>
      </div>
      <div class="panel">
        <div class="eyebrow">Bounty Board</div>
        <h2>進行中的賞金</h2>
        ${bounties.length ? `<div class="history">${bounties.map(([slug, b]) => `<div><span>${esc(b.title)}</span>${diffChip(b.difficulty)}<span class="muted">接於 ${esc(b.accepted_at.slice(5, 16))}</span><button class="btn ghost" data-view="${esc(slug)}">看題</button></div>`).join("")}</div>`
          : `<div class="empty">還沒接任何賞金。右下角的廣告或今日委託都可以接。</div>`}
      </div>
    </div>
    <div class="grid2">
      <div class="panel">
        <div class="eyebrow">Library</div>
        <h2>題庫與同步</h2>
        <p class="muted" style="margin:0 0 10px">題庫 ${lib.total} 題，其中 ${lib.playable} 題能玩（排除付費、SQL、Shell）。${lib.allDifficulties ? "已包含中等與困難題。" : "目前只有簡單題，抓全部難度後技能樹會長出動態規劃、圖論等更深的分支。"}</p>
        <div class="row">
          <button class="btn" data-do="sync">同步官網進度</button>
          ${lib.allDifficulties ? `<button class="btn ghost" data-do="fetch">更新題庫</button>` : `<button class="btn rune" data-do="fetchAll">擴充題庫（全部難度）</button>`}
        </div>
      </div>
      <div class="panel">
        <div class="eyebrow">Recent Kills</div>
        <h2>最近解掉的題目</h2>
        ${S.recent.length ? `<div class="history">${S.recent.map((r) => `<div><span class="mono muted">#${esc(r.id)}</span><span>${esc(r.title)}</span>${diffChip(r.difficulty)}<span class="muted">${esc((r.at || "官網同步").slice(0, 16))}</span></div>`).join("")}</div>` : `<div class="empty">還沒有紀錄，先解一題吧！</div>`}
      </div>
    </div>
    <div class="panel">
      <div class="eyebrow">How to play in VS Code</div>
      <h2>邊寫邊玩</h2>
      <ol class="muted" style="margin:0;padding-left:20px">
        <li>在 VS Code 按 <b>Ctrl+Shift+P</b> → 輸入 <b>Simple Browser: Show</b> → 貼上 <span class="mono">${esc(location.origin)}</span>，遊戲就會開在編輯器旁邊。</li>
        <li>選題後，解題檔會自動在 VS Code 打開，游標停在要寫程式的地方。</li>
        <li>寫完在遊戲按「試招」（不扣血）或「出招」（正式提交）。也可以在 VS Code 按 <b>Ctrl+Shift+B</b> 直接提交目前的檔案，遊戲會自動判定戰果。</li>
      </ol>
    </div>`;
}

/* ---------- 遠征 ---------- */
const NODE_STYLE = {
  fight: { g: "戰", fill: "#262b3b", stroke: "#a9aec0", color: "#ece2ca" },
  elite: { g: "精", fill: "#3a1714", stroke: "#e3564a", color: "#ffb3a8" },
  chest: { g: "寶", fill: "#3a2a10", stroke: "#ffd27a", color: "#ffd27a" },
  camp: { g: "火", fill: "#3a2210", stroke: "#ff9a4a", color: "#ffc18f" },
  shop: { g: "商", fill: "#10303a", stroke: "#73bccd", color: "#a9e3ef" },
  mystery: { g: "？", fill: "#261d3d", stroke: "#a98be0", color: "#d6c4ff" },
  boss: { g: "王", fill: "#4a1410", stroke: "#ff8a7a", color: "#ffd9d2" },
};

function renderRun() {
  const el = $("#tab-run");
  const run = S.run;
  if (!run) { el.innerHTML = runLobby(); return; }
  const hpPct = (run.hp / run.max_hp) * 100;
  const cur = run.current;
  let battle = "";
  if (cur && !cur.chosen) {
    const t = cur.type;
    battle = `<div class="panel battle">
      <div><div class="eyebrow">${t === "boss" ? "Boss Battle" : t === "elite" ? "Elite Encounter" : "Encounter"}</div>
      <h2>${t === "boss" ? `Boss 現身！${cur.boss_tag ? `牠專攻你的弱點「${esc(nodeName(cur.boss_tag))}」` : ""}` : t === "elite" ? "精英怪擋住了去路" : "遇到怪物了"}</h2>
      <p class="muted" style="margin:0">從下面挑一隻來打。選了之後解題檔會自動在 VS Code 開啟。答錯一次扣 ${t === "boss" ? 22 : t === "elite" ? 16 : 10} HP。</p></div>
      <div class="quests">${cur.offers.map((q) => questCard(q, { choose: true, cls: `monster ${t}` })).join("")}</div>
      <div class="row">
        <button class="btn" data-run="reroll">${run.relics.includes("lucky_cat") && !cur.rerolled ? "換一批題目（招財貓免費）" : "換一批題目（-5 HP）"}</button>
        <button class="btn danger" data-run="flee">撤退</button>
      </div></div>`;
  } else if (cur && cur.chosen) {
    const ch = run.chosen || { title: cur.chosen, slug: cur.chosen };
    const off = cur.offers.find((o) => o.slug === cur.chosen) || {};
    const glyph = (off.tagNames && off.tagNames[0] ? (S.tree.nodes.find((n) => n.name === off.tagNames[0]) || {}).glyph : null) || "魔";
    battle = `<div class="panel battle">
      <div class="foe">
        <div class="foe-face ${cur.type}">${esc(glyph)}</div>
        <div>
          <div class="eyebrow">${cur.type === "boss" ? "Boss" : cur.type === "elite" ? "Elite" : "Foe"} · 難度分 ${off.rating || "?"}</div>
          <h3>#${esc(ch.id || "")} ${esc(ch.title)}</h3>
          <div class="row" style="margin-top:6px">${diffChip(ch.difficulty || off.difficulty)}${(off.tagNames || []).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}<span class="chip">已答錯 ${cur.wrong} 次</span></div>
        </div>
      </div>
      <div class="row">
        <button class="btn" data-view="${esc(cur.chosen)}">看題</button>
        <button class="btn" data-open="${esc(cur.chosen)}">在 VS Code 開檔</button>
        <button class="btn rune" data-test="${esc(cur.chosen)}">試招（不扣血）</button>
        <button class="btn primary" data-submit="${esc(cur.chosen)}">出招（提交）</button>
        <button class="btn danger" data-run="flee">撤退</button>
      </div>
      ${resultBlock(cur.chosen)}
    </div>`;
  }
  el.innerHTML = `
    <div class="panel run-hud">
      <div style="display:grid;gap:8px;min-width:0">
        <div class="hpbar"><i style="width:${hpPct}%"></i><span>HP ${run.hp} / ${run.max_hp}</span></div>
        <div class="relics">${run.relics.map((r) => `<span class="relic" title="${esc(S.relics[r].name)}：${esc(S.relics[r].desc)}">${esc(S.relics[r].glyph)}</span>`).join("") || `<span class="muted" style="font-size:12.5px">還沒有遺物。精英、寶箱、商店可以拿到。</span>`}</div>
      </div>
      <div style="display:grid;gap:6px;justify-items:end">
        <span class="gold"><span class="coin"></span>${run.gold}</span>
        <span class="muted" style="font-size:12px">第 ${run.cleared.length} 層 · 擊殺 ${run.kills} · 遠征經驗 ${run.xp}</span>
        ${run.status === "active" ? `<button class="btn ghost danger" data-run="abandon" style="padding:3px 10px;font-size:12px">放棄遠征</button>` : ""}
      </div>
    </div>
    ${battle}
    <div class="panel">
      <div class="row" style="justify-content:space-between;margin-bottom:10px">
        <div><div class="eyebrow">Dungeon Map · 種子 #${run.seed}</div><h2>${run.moves.length ? "選擇下一步" : cur ? "戰鬥中" : run.pending ? "處理事件中" : "地圖"}</h2></div>
        <div class="legend-map">${Object.entries(NODE_STYLE).map(([k, v]) => `<span><i style="background:${v.fill};border:1.5px solid ${v.stroke}"></i>${esc(S.nodeTypes[k])}</span>`).join("")}</div>
      </div>
      <div class="mapwrap" id="mapwrap">${mapSVG(run)}</div>
    </div>
    <div class="panel"><div class="eyebrow">Battle Log</div>
      <ul class="log">${run.log.map((l) => `<li><span>${esc(l.t.slice(11, 16))}</span>${esc(l.text)}</li>`).join("")}</ul></div>`;
  // 走到新位置時，自動捲到目前位置
  const wrap = $("#mapwrap");
  const key = run.seed + ":" + (run.pos || "start");
  if (key !== mapPosKey) {
    mapPosKey = key;
    const here = wrap.querySelector(".here") || wrap.querySelector(".can");
    if (here) {
      const m = /translate\(([\d.-]+) ([\d.-]+)\)/.exec(here.getAttribute("transform"));
      if (m) { wrap.dataset.fresh = "1"; requestAnimationFrame(() => { wrap.scrollTop = Math.max(0, +m[2] - wrap.clientHeight / 2); delete wrap.dataset.fresh; }); }
    }
  }
}

function runLobby() {
  const ups = S.meta.upgrades;
  const hist = S.meta.history;
  return `
    <div class="panel">
      <div class="eyebrow">Roguelike · 演算法地城</div>
      <h2>準備出發</h2>
      <ul class="muted" style="margin:6px 0 14px;padding-left:20px">
        <li>每局都會隨機生成一張 10 層地圖，最上面是 Boss。</li>
        <li><b>戰鬥／精英／Boss</b>：從 2~3 題裡挑一題打。<b>答錯扣血</b>，試招不扣血；通過拿金幣與經驗，精英還會掉遺物。</li>
        <li><b>寶箱、篝火、商店、神秘事件</b>：拿遺物、回血、花金幣。</li>
        <li>Boss 會從你<b>最弱的已解鎖技能</b>出題。HP 歸零就結束，但會留下<b>結晶</b>買永久強化。</li>
      </ul>
      <button class="btn primary" data-run="start">開始第 ${S.meta.runs + 1} 次遠征</button>
    </div>
    <div class="panel">
      <div class="eyebrow">Soul Forge · 結晶 ${S.player.shards}</div>
      <h2>永久強化</h2>
      <div class="upgrades">${ups.map((u) => `<div class="up">
        <b>${esc(u.name)}</b><span class="muted" style="font-size:12.5px">${esc(u.desc)}</span>
        <div class="pips">${Array.from({ length: u.cap }, (_, i) => `<i class="${i < u.level ? "on" : ""}"></i>`).join("")}</div>
        ${u.price == null ? `<span class="chip">已滿級</span>` : `<button class="btn" data-up="${u.id}" ${S.player.shards < u.price ? "disabled" : ""}><span class="gem"></span> ${u.price}</button>`}
      </div>`).join("")}</div>
    </div>
    <div class="panel">
      <div class="eyebrow">Chronicle</div>
      <h2>遠征紀錄</h2>
      ${hist.length ? `<div class="history">${hist.map((h) => `<div><span class="${h.won ? "w" : "l"}">${h.won ? "征服" : "倒下"}</span><span>${h.floors} 層</span><span>擊殺 ${h.kills}</span><span>經驗 ${h.xp}</span><span class="shards"><span class="gem"></span>${h.shards}</span><span class="muted">${esc(h.ended_at.slice(5, 16))}</span></div>`).join("")}</div>` : `<div class="empty">還沒有遠征紀錄。</div>`}
    </div>`;
}

function mapSVG(run) {
  const m = run.map;
  const colW = 62, rowH = 66, pad = 40;
  const W = pad * 2 + (m.cols - 1) * colW, H = pad * 2 + (m.rows - 1) * rowH + 20;
  const jit = (k) => { let h = 0; for (const c of k) h = (h * 31 + c.charCodeAt(0)) | 0; return ((h % 13) - 6); };
  const P = (k) => {
    const n = m.nodes[k];
    return { x: pad + n.c * colW + (k === "boss" ? 0 : jit(k)), y: pad + 10 + (m.rows - 1 - n.r) * rowH + (k === "boss" ? 0 : jit(k + "y") * .6) };
  };
  const visited = new Set([...run.cleared, run.pos].filter(Boolean));
  const can = new Set(run.moves);
  let s = `<svg class="map" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`;
  for (const [a, b] of m.edges) {
    const p = P(a), q = P(b);
    const walked = visited.has(a) && visited.has(b);
    s += `<path class="medge ${walked ? "walked" : ""}" d="M${p.x} ${p.y} L${q.x} ${q.y}"/>`;
  }
  for (const [k, n] of Object.entries(m.nodes)) {
    const p = P(k), st = NODE_STYLE[n.type];
    const r = k === "boss" ? 26 : 16;
    const cls = ["mnode", visited.has(k) && k !== run.pos ? "done" : "", k === run.pos ? "here" : "", can.has(k) ? "can" : "", !visited.has(k) && !can.has(k) ? "far" : ""].join(" ");
    s += `<g class="${cls}" ${can.has(k) ? `data-enter="${k}" tabindex="0" role="button" aria-label="${esc(S.nodeTypes[n.type])}"` : ""} transform="translate(${p.x} ${p.y})">
      <circle class="ring" r="${r + 6}" fill="none" stroke="${st.stroke}" stroke-width="1.5" opacity="0"/>
      <circle class="disc" r="${r}" fill="${st.fill}" stroke="${st.stroke}"/>
      <text fill="${st.color}" font-size="${k === "boss" ? 22 : 14}">${st.g}</text></g>`;
  }
  return s + "</svg>";
}

/* ---------- 技能樹 ---------- */
function renderTree() {
  const el = $("#tab-tree");
  const T = S.tree;
  const nodes = T.nodes;
  const byLayer = {};
  nodes.forEach((n) => (byLayer[n.layer] = (byLayer[n.layer] || 0) + 1));
  const maxW = Math.max(...Object.values(byLayer));
  const ROWH = 138;
  const W = Math.max(640, maxW * 84 + 60), H = T.layers * ROWH + 20;
  const pos = {};
  nodes.forEach((n) => (pos[n.id] = { x: 30 + n.x * (W - 60), y: 48 + n.layer * ROWH }));
  const R = 22, ARC = 2 * Math.PI * (R + 5);
  let svg = `<svg class="tree" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">
    <defs><radialGradient id="gEmber" cx=".45" cy=".35" r=".75"><stop offset="0" stop-color="#ffe7ad"/><stop offset=".5" stop-color="#f0b24f"/><stop offset="1" stop-color="#a8611a"/></radialGradient>
    <filter id="fGlow" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="7"/></filter></defs>`;
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  for (const n of nodes) for (const p of n.parents) {
    const a = pos[p], b = pos[n.id];
    svg += `<path class="tedge ${byId[p].lit ? "on" : ""} ${n.inferred ? "inf" : ""}" d="M${a.x} ${a.y + R + 40} C${a.x} ${a.y + R + 80}, ${b.x} ${b.y - R - 50}, ${b.x} ${b.y - R - 6}"/>`;
  }
  for (const n of nodes) {
    const { x, y } = pos[n.id];
    const frac = n.total ? Math.min(1, n.next ? n.pts / n.next : 1) : 0;
    svg += `<g class="tnode ${selNode === n.id ? "sel" : ""}" data-s="${n.state}" data-node="${esc(n.id)}" transform="translate(${x} ${y})" tabindex="0" role="button" aria-label="${esc(n.name)} Lv${n.level}">
      <circle class="halo" r="${R + 10}" filter="url(#fGlow)"/>
      <circle class="track" r="${R + 5}"/>
      <circle class="arc" r="${R + 5}" transform="rotate(-90)" stroke-dasharray="${ARC}" stroke-dashoffset="${ARC * (1 - frac)}" ${n.unlocked ? "" : 'style="stroke:#4a4f63"'}/>
      ${n.inferred ? `<circle class="auto" r="${R + 9}"/>` : ""}
      <g class="crown">${Array.from({ length: 10 }, (_, i) => { const a = i * Math.PI / 5, rr = R + 12; return `<path d="M${Math.cos(a) * rr} ${Math.sin(a) * rr} l${Math.cos(a) * 4} ${Math.sin(a) * 4}" stroke="#ffd27a" stroke-width="2" stroke-linecap="round"/>`; }).join("")}</g>
      <circle class="core" r="${R}"/>
      <text class="glyph" y="1">${esc(n.glyph)}</text>
      <text class="label" y="${R + 22}">${esc(n.name)}</text>
      <text class="cnt" y="${R + 35}">Lv${n.level} · ${n.solved}/${n.total}</text>
    </g>`;
  }
  svg += "</svg>";
  const litN = nodes.filter((n) => n.lit).length;
  const inf = nodes.filter((n) => n.inferred).length;
  el.innerHTML = `
    <div class="panel">
      <div class="row" style="justify-content:space-between">
        <div><div class="eyebrow">Skill Tree · 自動生成</div><h2>技能樹　<span class="mono" style="font-size:15px;color:var(--ember-hot)">${litN}</span><span class="muted" style="font-size:14px"> / ${nodes.length} 點亮</span></h2></div>
        <div class="legend-map"><span><i style="border:1px solid #3a4157;background:#151925"></i>封印</span><span><i style="border:1.5px solid var(--rune)"></i>可修練</span><span><i style="border:2px solid var(--ember);background:#2a2113"></i>修練中</span><span><i style="background:var(--ember)"></i>點亮</span>${inf ? `<span><i style="border:1px dashed var(--violet)"></i>自動推斷</span>` : ""}</div>
      </div>
      <p class="muted" style="margin:6px 0 12px;font-size:13px">節點來自題庫裡的 LeetCode 標籤。前置技能點亮後才會解鎖；加權解題分（簡單 1、中等 2、困難 3）到 2 分就點亮，最高 Lv5。題庫出現新標籤時，會用「一起出現的機率」自動推斷它的前置技能（虛線）。</p>
      <div class="treewrap">${svg}</div>
    </div>
    <div class="panel" id="nodeInfo">${nodeInfo()}</div>`;
}

function nodeInfo() {
  if (!selNode) return `<div class="empty">點任一個技能節點，看它的進度和推薦題目。</div>`;
  const n = S.tree.nodes.find((x) => x.id === selNode);
  if (!n) return "";
  const per = S.perTag.find((t) => t.id === n.id);
  const stars = `<span class="stars">${"★".repeat(n.level)}<i>${"★".repeat(5 - n.level)}</i></span>`;
  const recs = tagRecs[n.id];
  const stateTxt = { lock: "封印中", open: "可修練", part: "修練中", lit: "已點亮", max: "完全掌握" }[n.state];
  return `<div class="eyebrow">${esc(n.id)}${n.inferred ? " · 演算法自動推斷前置" : ""}</div>
    <h2>${esc(n.name)}　${stars}</h2>
    <div class="kv" style="margin:10px 0">
      <div><b>${stateTxt}</b><span>狀態</span></div>
      <div><b>${n.solved} / ${n.total}</b><span>已解 / 題數</span></div>
      <div><b>${n.pts}${n.next ? ` / ${n.next}` : ""}</b><span>${n.next ? `升到 Lv${n.level + 1} 需要的分數` : "已滿級"}</span></div>
      <div><b>${per ? per.rating : "—"}</b><span>這個技能的實力分</span></div>
    </div>
    ${n.parents.length ? `<div class="row" style="margin-bottom:10px"><span class="muted">前置：</span>${n.parents.map((p) => `<button class="chip" data-node="${esc(p)}">${esc(nodeName(p))}</button>`).join("")}</div>` : ""}
    ${!n.unlocked ? `<div class="notice" style="margin-bottom:10px">先點亮前置技能。這裡解的題目會先記著，前置點亮的瞬間一起燃起來。</div>` : ""}
    <div class="eyebrow" style="margin-bottom:8px">推薦修練</div>
    ${recs ? (recs.length ? `<div class="quests">${recs.map((q) => questCard(q)).join("")}</div>` : `<div class="empty">這個技能的題目都解完了！</div>`) : `<div class="empty">載入推薦中…</div>`}`;
}

async function selectNode(id) {
  selNode = id;
  renderTree();
  $("#nodeInfo").scrollIntoView({ behavior: "smooth", block: "nearest" });
  if (!tagRecs[id]) {
    try {
      const r = await api("/api/recommend", { tag: id, k: 4 });
      tagRecs[id] = r.items;
    } catch (e) { tagRecs[id] = []; }
    if (selNode === id && tab === "tree") $("#nodeInfo").innerHTML = nodeInfo();
  }
}

/* ---------- 戰力 ---------- */
const CORE = ["array", "string", "hash-table", "math", "two-pointers", "sorting", "stack", "binary-tree", "dynamic-programming", "greedy", "binary-search", "bit-manipulation"];
const TIER_COLOR = { 青銅: "#c58a5a", 白銀: "#c9d1e3", 黃金: "#ffd27a", 白金: "#7fe0d4", 鑽石: "#8ab8ff", 大師: "#c49bff", 宗師: "#ff8a7a", 傳說: "#ffb347", 神話: "#ff6fd8" };

function renderPower() {
  const el = $("#tab-power");
  const p = S.player;
  const tagMap = Object.fromEntries(S.perTag.map((t) => [t.id, t]));
  const present = new Set(S.tree.nodes.map((n) => n.id));
  let axes = S.perTag.filter((t) => t.events >= 1).sort((a, b) => b.events - a.events).slice(0, 8).map((t) => t.id);
  for (const c of CORE) if (axes.length < 6 && present.has(c) && !axes.includes(c)) axes.push(c);
  const rows = S.perTag.slice().sort((a, b) => b.rating - a.rating);
  const col = TIER_COLOR[p.tier] || "var(--ember-hot)";
  const c = p.contest;
  const lo = Math.min(...rows.map((r) => r.rating), p.rating) - 100, hi = Math.max(...rows.map((r) => r.rating), p.rating) + 50;
  el.innerHTML = `
    <div class="panel power-hero">
      <div>
        <div class="eyebrow">Rank · 段位</div>
        <div class="rank-big" style="color:${col};text-shadow:0 0 26px ${col}66">${esc(p.rank)}</div>
        <div class="muted" style="margin-top:4px">實力分 <b class="mono" style="color:var(--parch);font-size:22px">${p.rating}</b></div>
        ${p.nextRank ? `<div class="muted" style="font-size:12.5px">再 <b style="color:var(--ember-hot)">${p.needRank}</b> 分升上「${esc(p.nextRank)}」</div>` : `<div class="muted" style="font-size:12.5px">已達最高段位</div>`}
      </div>
      <div style="display:grid;gap:10px">
        <div class="kv">
          <div><b style="color:var(--ember-hot)">${(p.power || 0).toLocaleString("en-US")}</b><span>戰力（越難的題加越多）</span></div>
          <div><b>${p.solved}</b><span>已解題數</span></div>
          <div><b>${p.hardest ?? "—"}</b><span>解過最難的題</span></div>
          <div><b>${p.official ?? "—"}</b><span>${p.official ? `官方競賽分${c && c.topPercentage ? `・前 ${c.topPercentage}%` : ""}` : "官方競賽分（同步後顯示）"}</span></div>
        </div>
        <details><summary class="muted" style="cursor:pointer;font-size:13px">分數怎麼算？</summary>
          <ul class="muted" style="font-size:13px;margin:8px 0 0;padding-left:20px;display:grid;gap:4px">
            <li><b>題目難度分</b>：使用社群的 <a href="https://github.com/zerotrac/leetcode_problem_rating" target="_blank" rel="noopener">zerotrac 題目難度表</a>（跟 LeetCode 競賽分同尺度）${p.ratedBy === "zerotrac" ? "" : "，目前還沒下載成功，先用官方難度與通過率估計"}。沒收錄的題目用官方難度與通過率估計。</li>
            <li><b>實力分</b>：取你解過最難的 10 題做加權平均，解題數少時往 1000 打折。跟刷題順序無關，狂刷簡單題不會灌分。</li>
            <li><b>官方競賽分</b>：有參加 LeetCode 週賽的話，同步時會抓回來，實力分取兩者較高的那個。</li>
            <li><b>段位</b>：青銅、白銀、黃金、白金、鑽石、大師、宗師、傳說、神話，每階分 IV～I。大約 1850 相當於 LeetCode 的 Knight、2200 相當於 Guardian。</li>
            <li><b>戰力</b>：每題貢獻（難度分 ÷ 1000）³ × 100，會一直成長，越難的題目加越多。</li>
          </ul></details>
      </div>
    </div>
    <div class="grid2">
      <div class="panel"><div class="eyebrow">Radar</div><h2>技能雷達</h2>
        <div class="radar-wrap">${radarSVG(axes, tagMap, p.rating)}</div>
        <p class="muted" style="font-size:12.5px;margin:6px 0 0">外圈 ${radarRange[1]}、中心 ${radarRange[0]}。虛線是你的實力分；還沒解過的技能先用實力分代替（淡色）。</p></div>
      <div class="panel"><div class="eyebrow">Breakdown</div><h2>各技能實力分</h2>
        ${rows.length ? `<div class="tblwrap"><table class="tags"><thead><tr><th>技能</th><th>實力分</th><th></th><th>題數</th></tr></thead><tbody>
        ${rows.map((t) => `<tr><td><button class="chip" data-node-go="${esc(t.id)}">${esc(t.name)}</button></td><td class="n">${t.rating}</td>
          <td><div class="bar"><i class="${t.rating >= p.rating ? "hi" : ""}" style="width:${Math.max(4, Math.min(100, ((t.rating - lo) / (hi - lo)) * 100))}%"></i></div></td><td class="n">${t.events}</td></tr>`).join("")}
        </tbody></table></div>` : `<div class="empty">還沒有解題紀錄。解一題就會出現！</div>`}
      </div>
    </div>`;
}

let radarRange = [800, 1800];
function radarSVG(axes, tagMap, base) {
  const W = 320, C = W / 2, R = 118, n = axes.length;
  if (n < 3) return `<div class="empty">多解幾題不同類型的題目，雷達圖就會長出來。</div>`;
  const all = axes.map((a) => tagMap[a]?.rating ?? base).concat(base);
  const lo = Math.floor((Math.min(...all) - 120) / 100) * 100, hi = Math.ceil((Math.max(...all) + 120) / 100) * 100;
  radarRange = [lo, hi];
  const ang = (i) => -Math.PI / 2 + (i * 2 * Math.PI) / n;
  const rad = (v) => Math.max(0, Math.min(1, (v - lo) / (hi - lo))) * R;
  let s = `<svg class="radar" viewBox="0 0 ${W} ${W}" width="${W}" height="${W}" style="max-width:100%">`;
  for (const lv of [0.25, 0.5, 0.75, 1]) {
    s += `<polygon points="${axes.map((_, i) => `${C + Math.cos(ang(i)) * R * lv},${C + Math.sin(ang(i)) * R * lv}`).join(" ")}" fill="none" stroke="#2b3245"/>`;
  }
  axes.forEach((_, i) => (s += `<line x1="${C}" y1="${C}" x2="${C + Math.cos(ang(i)) * R}" y2="${C + Math.sin(ang(i)) * R}" stroke="#232838"/>`));
  s += `<polygon points="${axes.map((_, i) => `${C + Math.cos(ang(i)) * rad(base)},${C + Math.sin(ang(i)) * rad(base)}`).join(" ")}" fill="none" stroke="#73bccd" stroke-dasharray="3 4"/>`;
  const vals = axes.map((a) => tagMap[a]?.rating ?? base);
  s += `<polygon points="${vals.map((v, i) => `${C + Math.cos(ang(i)) * rad(v)},${C + Math.sin(ang(i)) * rad(v)}`).join(" ")}" fill="rgba(233,171,71,.25)" stroke="#ffd27a" stroke-width="2"/>`;
  vals.forEach((v, i) => (s += `<circle cx="${C + Math.cos(ang(i)) * rad(v)}" cy="${C + Math.sin(ang(i)) * rad(v)}" r="3.5" fill="${tagMap[axes[i]] ? "#ffd27a" : "#5b6178"}"/>`));
  axes.forEach((a, i) => {
    const x = C + Math.cos(ang(i)) * (R + 22), y = C + Math.sin(ang(i)) * (R + 16);
    s += `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="central" opacity="${tagMap[a] ? 1 : .5}">${esc(nodeName(a))}</text>`;
  });
  return s + "</svg>";
}

/* ---------- 題目 ---------- */
function resultBlock(slug) {
  const r = lastResult[slug];
  if (!r) return "";
  const x = r.result;
  const lines = [];
  const st = x.status_msg || "？";
  const good = r.kind === "submit" ? r.accepted : (st === "Accepted" && JSON.stringify(x.code_answer) === JSON.stringify(x.expected_code_answer));
  lines.push(`<span class="${good ? "ok" : "bad"}">${r.kind === "submit" ? "出招" : "試招"}結果：${esc(st)}</span>`);
  if (x.full_compile_error || x.compile_error) lines.push(`<span class="bad">${esc(x.full_compile_error || x.compile_error)}</span>`);
  if (x.full_runtime_error || x.runtime_error) lines.push(`<span class="bad">${esc(x.full_runtime_error || x.runtime_error)}</span>`);
  if (r.kind === "test") {
    if (x._input) lines.push(`<span class="dim">測資：</span>\n${esc(x._input)}`);
    if (x.code_answer) lines.push(`<span class="dim">你的輸出：</span>${esc((x.code_answer || []).join("  |  "))}`);
    if (x.expected_code_answer) lines.push(`<span class="dim">正確答案：</span>${esc((x.expected_code_answer || []).join("  |  "))}`);
    if (x.std_output_list && x.std_output_list.some((s) => s)) lines.push(`<span class="dim">print 輸出：</span>\n${esc(x.std_output_list.join("\n"))}`);
  } else {
    if (x.total_testcases != null) lines.push(`通過測資 ${x.total_correct}/${x.total_testcases}`);
    if (x.status_runtime) lines.push(`執行時間 ${esc(x.status_runtime)}　記憶體 ${esc(x.status_memory || "")}`);
    if (x.last_testcase) lines.push(`<span class="dim">出錯的輸入：</span>${esc(x.last_testcase)}\n<span class="dim">你的輸出：</span>${esc(x.code_output)}\n<span class="dim">正確答案：</span>${esc(x.expected_output)}`);
  }
  return `<div class="console">${lines.join("\n")}</div>`;
}

async function renderProblem() {
  const el = $("#tab-problem");
  const slug = targetSlug();
  if (!slug) {
    problemSig = "";
    el.innerHTML = `<div class="panel"><div class="eyebrow">Problem</div><h2>還沒選題目</h2><p class="muted">從酒館的今日委託、技能樹或遠征挑一題，題目就會出現在這裡。</p><div class="quests">${S.picks.map((q) => questCard(q)).join("")}</div></div>`;
    return;
  }
  const q = probCache[slug];
  if (!q) {
    el.innerHTML = `<div class="panel"><div class="empty">讀取題目中…</div></div>`;
    try { probCache[slug] = await api(`/api/problem?slug=${encodeURIComponent(slug)}`); }
    catch (e) { el.innerHTML = `<div class="panel"><div class="notice">讀不到題目：${esc(e.message)}</div><p><a href="${lcUrl(slug)}" target="_blank" rel="noopener">到 LeetCode 看題目</a></p></div>`; return; }
    if (tab === "problem" && targetSlug() === slug) renderProblem();
    return;
  }
  const run = S.run;
  const inBattle = run && run.current && run.current.chosen === slug;
  const bounty = S.meta.bounties[slug];
  const solvedNow = S.recent.some((r) => r.slug === slug) || q.solved;
  // 狀態沒變就不重畫（避免題目 iframe 一直重新載入）
  const sig = [slug, inBattle, !!bounty, solvedNow, JSON.stringify(lastResult[slug] || null)].join("|");
  if (sig === problemSig && el.querySelector("iframe")) return;
  problemSig = sig;
  const prevTc = $("#tc") ? $("#tc").value : null;
  const doc = `<!doctype html><meta charset="utf-8"><base target="_blank"><style>
    body{background:#0f121a;color:#ece2ca;font:14px/1.7 "Noto Sans TC","Microsoft JhengHei",sans-serif;padding:6px 16px 20px;margin:0}
    pre{background:#090b10;border:1px solid #2b3245;padding:10px 12px;border-radius:8px;white-space:pre-wrap;font:12.5px/1.6 "JetBrains Mono",Consolas,monospace}
    code{font-family:"JetBrains Mono",Consolas,monospace;color:#ffd27a;background:#1a1f2c;padding:1px 4px;border-radius:4px}
    pre code{background:none;padding:0;color:#c9d1e3} strong{color:#fff} a{color:#ffd27a}
    img{max-width:100%;height:auto;background:#fff;border-radius:6px} ul,ol{padding-left:22px}
  </style>${q.html}`;
  el.innerHTML = `
    <div class="panel" style="display:grid;gap:12px">
      <div class="prob-head">
        <span class="mono muted">#${esc(q.id)}</span><h2>${esc(q.title)}</h2>${diffChip(q.difficulty)}
        <span class="chip">難度分 ${q.rating}</span>${solvedNow ? `<span class="chip" style="color:var(--heal)">已解</span>` : ""}
        ${inBattle ? `<span class="chip" style="color:#ff8a7a;border-color:#6d342d">戰鬥中</span>` : bounty ? `<span class="chip" style="color:var(--rune)">賞金 ×2</span>` : ""}
      </div>
      <div class="row">${(q.tags || []).map((t) => `<button class="chip" data-node-go="${esc(t)}">${esc(nodeName(t))}</button>`).join("")}
        <a class="chip" href="${q.url}" target="_blank" rel="noopener">leetcode.com</a><a class="chip" href="${q.cnUrl}" target="_blank" rel="noopener">力扣中文</a></div>
      <div class="row">
        <button class="btn" data-open="${esc(slug)}">在 VS Code 開檔</button>
        <button class="btn rune" data-test="${esc(slug)}">試招（範例測資）</button>
        <button class="btn primary" data-submit="${esc(slug)}">出招（提交）</button>
        ${!inBattle && !bounty && !solvedNow ? `<button class="btn ghost" data-bounty="${esc(slug)}">接賞金 ×2 XP</button>` : ""}
      </div>
      ${resultBlock(slug)}
      <iframe class="statement" sandbox="allow-popups allow-popups-to-escape-sandbox" title="題目敘述" style="height:62vh"></iframe>
      <details><summary class="muted" style="cursor:pointer">自訂測資（試招用）</summary>
        <textarea class="tc" id="tc" spellcheck="false" aria-label="自訂測資">${esc(prevTc ?? q.examples)}</textarea></details>
    </div>`;
  el.querySelector("iframe").srcdoc = doc;
}

function targetSlug() {
  const run = S?.run;
  if (run && run.status === "active" && run.current && run.current.chosen) return run.current.chosen;
  return focusSlug;
}

/* ---------- 底部戰鬥列 ---------- */
function renderDock() {
  const slug = targetSlug();
  const dock = $("#dock");
  if (!slug || tab === "problem") { dock.hidden = true; return; }
  const run = S.run;
  const inBattle = run && run.current && run.current.chosen === slug;
  const title = probCache[slug]?.title || run?.chosen?.title || S.picks.find((p) => p.slug === slug)?.title || slug;
  dock.hidden = false;
  dock.innerHTML = `<div class="dock-in">
    <div class="dock-info"><span class="eyebrow">${inBattle ? `戰鬥中 · HP ${run.hp}/${run.max_hp}` : "目前目標"}</span><b>${esc(title)}</b></div>
    <div class="row">
      <button class="btn" data-view="${esc(slug)}">看題</button>
      <button class="btn rune" data-test="${esc(slug)}">試招</button>
      <button class="btn primary" data-submit="${esc(slug)}">出招</button>
    </div></div>`;
}

/* ---------- 彈窗：寶箱、篝火、商店、事件、結算 ---------- */
let modalKey = "";
function renderModal() {
  const run = S.run;
  const box = $("#modal"), card = $("#modalCard");
  let html = "", key = "";
  if (!profile().onboarded) {
    key = "ob" + obStep;
    html = onboardingHTML();
  } else if (run && run.status !== "active") {
    const r = run.result || {};
    key = "result" + run.seed;
    html = `<div class="eyebrow">${r.won ? "Victory" : "Defeat"}</div>
      <h2>${r.won ? "征服了演算法地城！" : "遠征結束"}</h2>
      <div class="kv"><div><b>${r.floors}</b><span>走過的節點</span></div><div><b>${r.kills}</b><span>擊殺</span></div><div><b>${r.xp}</b><span>遠征經驗</span></div><div><b style="color:var(--violet)">${r.shards}</b><span>獲得結晶</span></div></div>
      <p class="muted" style="margin:0">結晶可以在遠征頁買永久強化，下一局會更強。</p>
      <button class="btn primary" data-run="clear">回到營地</button>`;
  } else if (run && run.pending && tab === "run") {
    const pd = run.pending;
    key = "pend" + run.pos + pd.kind + run.gold + (pd.items || []).filter((i) => i.sold).length;
    if (pd.kind === "relic") {
      html = `<div class="eyebrow">${esc(pd.title)}</div><h2>選一件遺物帶走</h2>${pd.gold ? `<p class="muted" style="margin:0">寶箱裡還有 ${pd.gold} 枚金幣。</p>` : ""}
        <div class="choices">${pd.options.map((id) => relicCard(id, `data-act="pick" data-arg="${id}"`)).join("") || `<div class="empty">遺物都被你拿光了！</div>`}</div>
        <button class="btn ghost" data-act="skip">都不要</button>`;
    } else if (pd.kind === "camp") {
      const heal = Math.floor(run.max_hp * 0.3) * (run.relics.includes("recursion_mirror") ? 2 : 1);
      html = `<div class="eyebrow">Campfire</div><h2>篝火</h2><p class="muted" style="margin:0">火光很溫暖。要休息還是修練？</p>
        <div class="choices"><button class="btn" data-act="rest">休息：回復 ${heal} HP</button><button class="btn" data-act="train">修練：最大 HP +6</button></div>`;
    } else if (pd.kind === "shop") {
      html = `<div class="eyebrow">Merchant · 你有 ${run.gold} 金幣</div><h2>流浪商人</h2>
        <div class="choices">${pd.items.map((it, i) => it.kind === "relic"
          ? relicCard(it.id, `data-act="buy" data-arg="${i}" ${it.sold || run.gold < it.price ? "disabled" : ""}`, it.sold ? "已售出" : `${it.price} 金`)
          : `<button class="btn" data-act="buy" data-arg="${i}" ${it.sold || run.gold < it.price ? "disabled" : ""}>回復藥水：HP +${it.amount}（${it.price} 金）</button>`).join("")}</div>
        <button class="btn primary" data-act="leave">離開商店</button>`;
    } else if (pd.kind === "event") {
      html = `<div class="eyebrow">Mystery</div><h2>${esc(pd.title)}</h2><p style="margin:0">${esc(pd.text)}</p>
        <div class="row">${pd.effects.map((e) => `<span class="chip">${esc(e)}</span>`).join("")}</div>
        <button class="btn primary" data-act="ok">繼續前進</button>`;
    }
  }
  if (!html) { box.hidden = true; modalKey = ""; return; }
  if (key !== modalKey || box.hidden) { card.innerHTML = html; modalKey = key; }
  box.hidden = false;
}

function relicCard(id, attrs, price) {
  const r = S.relics[id];
  return `<button class="relic-card" ${attrs}><span class="relic">${esc(r.glyph)}</span><span><b>${esc(r.name)}</b>${price ? `　<span class="gold">${esc(price)}</span>` : ""}<p>${esc(r.desc)}</p></span></button>`;
}

/* ---------- 設定 ---------- */
const BG_NAMES = { dungeon: "地城夜幕", starry: "星空", sakura: "夜櫻", abyss: "深海", ember: "熔岩", forest: "森林", plain: "純黑" };
let settingsSig = "";
let obStep = 1;

function avatarPicker(p) {
  const up = p.uploads && p.uploads.avatar;
  return `<div class="avatars">
    ${AVATARS.map((a) => `<button class="av" data-avatar="${a.id}" aria-pressed="${p.avatar === a.id}">${avatarSVG(a.id)}<span>${esc(a.name)}</span></button>`).join("")}
    ${up ? `<button class="av" data-avatar="upload" aria-pressed="${p.avatar === "upload"}"><img src="/user-asset/avatar?v=${esc(up.split("v=")[1] || "1")}" alt=""><span>我的圖片</span></button>` : ""}
    <label class="av up" role="button" tabindex="0"><span>＋</span><span>上傳圖片</span><input type="file" accept="image/png,image/jpeg,image/gif,image/webp" data-upload="avatar" hidden></label>
  </div>`;
}

function loginForm() {
  const manual = `<ol class="steps">
      <li>用瀏覽器登入 <a href="https://leetcode.com" target="_blank" rel="noopener">leetcode.com</a></li>
      <li>按 <code>F12</code> → <b>Application（應用程式）</b> → 左邊 <b>Cookies</b> → <code>https://leetcode.com</code></li>
      <li>複製 <code>LEETCODE_SESSION</code> 和 <code>csrftoken</code> 的 Value，貼到下面</li>
    </ol>
    <div class="fields" style="margin-top:10px">
      <label class="field">LEETCODE_SESSION<input id="lcSession" type="password" autocomplete="off" spellcheck="false" placeholder="eyJ0eXAiOiJKV1Qi…"></label>
      <label class="field">csrftoken<input id="lcCsrf" type="password" autocomplete="off" spellcheck="false" placeholder="一長串英數字"></label>
    </div>
    <button class="btn" data-login style="margin-top:10px">驗證並登入</button>`;
  const viaBrowser = S && S.browserLogin;
  return `${viaBrowser ? `<div style="display:grid;gap:8px;margin-bottom:12px">
      <div><button class="btn primary" data-blogin>用瀏覽器登入 LeetCode</button></div>
      <p class="muted" style="font-size:12.5px;margin:0">會開一個獨立的登入視窗，在裡面正常登入（email、GitHub、Google 都可以），完成後視窗會自動關閉。密碼是直接輸入給 LeetCode，遊戲碰不到。</p>
      <div class="blogin-status"></div>
    </div>` : ""}
    <details ${viaBrowser ? "" : "open"}><summary class="muted" style="cursor:pointer;margin-bottom:8px">${viaBrowser ? "備案：手動貼 cookie" : "貼上 cookie 登入"}</summary>${manual}</details>
    <p class="muted" style="font-size:12.5px;margin:8px 0 0">登入資訊只存在你電腦上的 <span class="mono">config.json</span>，不會上傳到任何地方。大約兩週會過期，到時候再按一次登入就好。</p>`;
}

let bloginTimer = null;
function bloginShow(html) { document.querySelectorAll(".blogin-status").forEach((e) => (e.innerHTML = html)); }
async function startBrowserLogin() {
  let st;
  try { st = await api("/api/login/browser", {}); } catch (e) { return toast("info", "開不了登入視窗", e.message); }
  if (st.state === "error") return bloginShow(`<div class="notice">${esc(st.error)}</div>`);
  bloginShow(`<div class="notice">已開啟登入視窗（${esc(st.browser || "瀏覽器")}），請在視窗裡登入 LeetCode，登入完會自動回來。 <button class="btn ghost" data-bcancel style="padding:2px 10px">取消</button></div>`);
  say("登入視窗開好了！登入完我會自動接手。");
  clearInterval(bloginTimer);
  bloginTimer = setInterval(async () => {
    let s2;
    try { s2 = await api("/api/login/status"); } catch (e) { return; }
    if (s2.state === "waiting") return;
    clearInterval(bloginTimer);
    if (s2.state === "ok") {
      bloginShow("");
      settingsSig = ""; modalKey = "";
      const full = await api("/api/state");
      full.events = [{ kind: "login", user: s2.user }];
      applyState(full);
    } else if (s2.state === "error") {
      bloginShow(`<div class="notice">${esc(s2.error)}</div>`);
      say("登入沒有完成，可以再按一次，或改用手動貼 cookie。");
    } else bloginShow("");
  }, 1500);
}

function renderSettings() {
  const el = $("#tab-settings");
  const p = profile();
  const sig = JSON.stringify([p, S.login, S.lang, S.vscodeInstalled, S.library.total]);
  if (sig === settingsSig && el.childElementCount) return;
  settingsSig = sig;
  el.innerHTML = `
    <div class="panel">
      <div class="eyebrow">Account · LeetCode</div>
      <h2>帳號</h2>
      ${S.login ? `<div class="lc-user" style="margin:8px 0 12px">${p.lcAvatar ? `<img src="${esc(p.lcAvatar)}" alt="" referrerpolicy="no-referrer">` : ""}
          <div><b style="font-size:16px">${esc(p.lcUser || "已登入")}</b><div class="muted" style="font-size:12.5px">試招、出招、同步官網進度都會用這個帳號</div></div></div>
        <div class="row"><button class="btn" data-do="sync">同步官網進度</button><button class="btn ghost" data-relogin>換帳號</button><button class="btn danger" data-logout>登出</button></div>
        <div id="reloginBox" hidden style="margin-top:12px">${loginForm()}</div>`
      : `<p class="muted" style="margin:4px 0 10px">登入後才能試招、出招、同步你在官網的進度。不需要密碼，只要兩個 cookie。</p>${loginForm()}`}
    </div>
    <div class="panel">
      <div class="eyebrow">Companion</div>
      <h2>頭像與看板娘</h2>
      <p class="muted" style="margin:4px 0 12px">選一位陪你刷題的看板娘，或上傳自己的圖片（PNG、JPG、GIF、WebP，6 MB 以內）。<br><span style="font-size:12px">看板娘的圖像與名字由 AI 生成，如有雷同，純屬巧合。</span></p>
      ${avatarPicker(p)}
      <div class="fields" style="margin-top:14px">
        <label class="field">你的暱稱<input id="pfName" maxlength="24" value="${esc(p.name)}" placeholder="獵題人"></label>
        <label class="field">看板娘的名字<input id="pfComp" maxlength="24" value="${esc(p.companion)}" placeholder="露緹"></label>
      </div>
      <div class="row" style="margin-top:10px"><button class="btn primary" data-savename>儲存名字</button></div>
    </div>
    <div class="panel">
      <div class="eyebrow">Backdrop</div>
      <h2>背景</h2>
      <div class="bgs" style="margin-top:10px">
        ${S.backgrounds.map((b) => `<button class="bgsw" data-bg="${b}" data-bgpick="${b}" aria-pressed="${p.bg === b}">${BG_NAMES[b] || b}</button>`).join("")}
        ${p.uploads && p.uploads.bg ? `<button class="bgsw" data-bgpick="upload" aria-pressed="${p.bg === "upload"}" style="background-image:url('/user-asset/bg?v=${esc(p.uploads.bg.split("v=")[1] || "1")}')">我的圖片</button>` : ""}
        <label class="bgsw" style="border-style:dashed;cursor:pointer;justify-content:center;align-items:center;color:var(--ash);text-shadow:none" role="button" tabindex="0">＋ 上傳背景<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" data-upload="bg" hidden></label>
      </div>
      ${p.bg === "upload" ? `<label class="field" style="margin-top:12px;max-width:320px">背景暗化（讓文字更清楚）<input id="pfDim" type="range" min="0" max="0.9" step="0.05" value="${p.dim}"></label>` : ""}
    </div>
    <div class="panel">
      <div class="eyebrow">Language</div>
      <h2>解題語言</h2>
      <p class="muted" style="margin:4px 0 10px">新建立的解題檔會用這個語言的官方範本。已經建好的檔案不會被改動。</p>
      <label class="field" style="max-width:280px">語言<select id="pfLang">${S.langs.map((l) => `<option value="${l.id}" ${l.id === S.lang ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select></label>
    </div>
    <div class="panel">
      <div class="eyebrow">Workspace</div>
      <h2>工作區</h2>
      <p class="muted" style="margin:4px 0 8px">你的解題檔、紀錄、遊戲存檔和登入資訊都在這個資料夾，每個玩家各自一份。</p>
      <div class="path">${esc(S.workspace)}</div>
      <div class="row" style="margin-top:10px">
        <button class="btn" data-ws>在 VS Code 開啟工作區</button>
        <button class="btn ${S.vscodeInstalled ? "ghost" : "rune"}" data-vscode>${S.vscodeInstalled ? "重新安裝 VS Code 任務" : "安裝 VS Code 任務（Ctrl+Shift+B 提交）"}</button>
        ${S.library.allDifficulties ? "" : `<button class="btn ghost" data-do="fetchAll">擴充題庫（全部難度）</button>`}
      </div>
    </div>`;
}

function onboardingHTML() {
  const p = profile();
  if (obStep === 1) {
    return `<div class="eyebrow">Welcome · 1 / 2</div>
      <h2>歡迎來到 LeetCode 演算法地城</h2>
      <p class="muted" style="margin:0">在這裡刷題會長出技能樹、提升段位、打怪遠征。先選一位陪你冒險的看板娘吧。</p>
      ${avatarPicker(p)}
      <div class="fields">
        <label class="field">你的暱稱<input id="obName" maxlength="24" value="${esc(p.name)}" placeholder="獵題人"></label>
        <label class="field">解題語言<select id="obLang">${S.langs.map((l) => `<option value="${l.id}" ${l.id === S.lang ? "selected" : ""}>${esc(l.name)}</option>`).join("")}</select></label>
      </div>
      <button class="btn primary" data-ob="next">下一步</button>`;
  }
  return `<div class="eyebrow">Welcome · 2 / 2</div>
    <h2>登入你的 LeetCode 帳號</h2>
    ${S.login ? `<p>已登入：<b>${esc(p.lcUser || "")}</b></p>` : loginForm()}
    <div class="row"><button class="btn ${S.login ? "primary" : "ghost"}" data-ob="done">${S.login ? "開始冒險" : "先跳過，之後在設定登入"}</button></div>`;
}

async function uploadFile(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  if (f.size > 6 * 1024 * 1024) return toast("info", "圖片太大了", "請小於 6 MB");
  const data = await new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = rej; r.readAsDataURL(f); });
  const st = await act("/api/upload", { kind: input.dataset.upload, data }, "上傳中…");
  if (st) { settingsSig = ""; modalKey = ""; render(); toast("win", input.dataset.upload === "avatar" ? "頭像換好了" : "背景換好了"); }
}

async function doLogin() {
  const session = ($("#lcSession") || {}).value || "", csrftoken = ($("#lcCsrf") || {}).value || "";
  const st = await act("/api/login", { session, csrftoken }, "向 LeetCode 確認身分中…");
  if (st) { settingsSig = ""; modalKey = ""; render(); }
}

/* ================= 動作 ================= */
async function viewProblem(slug) {
  setFocus(slug);
  setTab("problem");
}

async function openFile(slug) {
  const r = await act("/api/open", { slug });
  if (r) {
    toast("info", r.created ? "解題檔已建立" : "打開解題檔", r.file + (r.opened === "none" ? "（找不到 VS Code，請手動開啟）" : ""));
    setFocus(slug);
  }
}

async function runTest(slug) {
  const tc = $("#tc") && targetSlug() === slug ? $("#tc").value : null;
  busy(true, "試招中…（不會扣血）");
  try {
    const r = await api("/api/test", { slug, input: tc });
    lastResult[slug] = { kind: "test", result: r.result };
    const ok = r.result.status_msg === "Accepted" && JSON.stringify(r.result.code_answer) === JSON.stringify(r.result.expected_code_answer);
    say(ok ? "範例全對！可以<em>出招</em>了。" : "範例沒過，看一下輸出差在哪。");
    toast(ok ? "win" : "hit", ok ? "範例測資全對" : `試招：${r.result.status_msg || "沒過"}`);
    render();
  } catch (e) {
    toast("info", "試招失敗", e.message);
    say(`試招失敗：${esc(e.message).slice(0, 80)}`);
  } finally { busy(false); }
}

async function runSubmit(slug) {
  busy(true, "出招！判題中…");
  try {
    const st = await api("/api/submit", { slug });
    lastResult[slug] = { kind: "submit", result: st.result, accepted: st.accepted };
    const inRun = (st.events || []).some((e) => e.kind === "win" || e.kind === "hit");
    applyState(st);
    if (!inRun) {
      if (st.accepted) { confetti(); toast("win", "通過！", "經驗已入帳，技能樹更新了"); say("通過了！要不要再接一題？"); setTimeout(() => maybeAd(true), 8000); }
      else { toast("hit", st.result.status_msg || "沒通過", "看一下下方的錯誤訊息"); say("差一點！看看是哪筆測資出錯。"); }
    }
  } catch (e) {
    toast("info", "出招失敗", e.message);
    say(`出招失敗：${esc(e.message).slice(0, 80)}`);
  } finally { busy(false); }
}

document.addEventListener("click", async (ev) => {
  const t = ev.target.closest("button, [data-enter], [data-node], a");
  if (!t || t.disabled) return;
  const d = t.dataset;
  if (d.go) return setTab(d.go);
  if (d.view) return viewProblem(d.view);
  if (d.open) return openFile(d.open);
  if (d.test) return runTest(d.test);
  if (d.submit) return runSubmit(d.submit);
  if (d.bounty) { await act("/api/bounty", { slug: d.bounty }); setFocus(d.bounty); return render(); }
  if (d.choose) {
    const st = await act("/api/run/choose", { slug: d.choose });
    if (st) { setFocus(d.choose); toast("info", "開戰！", "解題檔已在 VS Code 開啟"); say("上吧！寫完按<em>試招</em>先確認範例。"); setTab("problem"); }
    return;
  }
  if (d.enter) {
    const st = await act("/api/run/enter", { key: d.enter });
    const n = st && st.run.map.nodes[d.enter];
    if (n) say({ fight: "有怪物！挑一隻順眼的。", elite: "精英怪……小心，牠會打很痛。", boss: "Boss！牠專挑你的弱點。", chest: "寶箱！", camp: "篝火，休息一下吧。", shop: "商人在招手。", mystery: "嗯？這裡有點奇怪……" }[n.type]);
    return;
  }
  if (d.run) {
    if (d.run === "abandon" && !t.dataset.armed) { t.dataset.armed = "1"; t.textContent = "再按一次確認放棄"; setTimeout(() => { delete t.dataset.armed; t.textContent = "放棄遠征"; }, 3500); return; }
    const st = await act(`/api/run/${d.run}`, {});
    if (st && d.run === "start") say("地城生成好了！從最下面挑一個入口。");
    if (st && d.run === "clear") setTab("run");
    return;
  }
  if (d.act) return act("/api/run/act", { action: d.act, arg: d.arg });
  if (d.up) return act("/api/upgrade", { id: d.up });
  if (d.node) return selectNode(d.node);
  if (d.nodeGo) { selNode = d.nodeGo; setTab("tree"); return selectNode(d.nodeGo); }
  if (d.do === "sync") { const st = await act("/api/sync", {}, "同步官網進度中…"); if (st) toast("info", "同步完成", st.log.trim().split("\n").pop()); return; }
  if (d.do === "fetchAll" || d.do === "fetch") {
    const st = await act("/api/fetch", { all: true }, "抓取全部難度題庫中，大約需要 30 秒…");
    if (st) { toast("win", "題庫擴充完成", `現在有 ${st.library.total} 題`); say("題庫變大了！技能樹長出了新的分支，去看看。"); }
    return;
  }
  if (d.adx !== undefined) return closeAd();
  if (d.avatar) {
    const body = { avatar: d.avatar };
    const preset = AVATARS.find((a) => a.id === d.avatar);
    // 看板娘名字還是預設角色名時，跟著換成新角色的名字
    if (preset && (!profile().companion || AVATARS.some((a) => a.name === profile().companion))) body.companion = preset.name;
    const st = await act("/api/profile", body); if (st) { settingsSig = ""; modalKey = ""; render(); say(d.avatar === "upload" ? "新頭像很好看！" : `你好，我是<em>${esc((AVATARS.find((a) => a.id === d.avatar) || {}).name || "")}</em>，請多指教！`); } return; }
  if (d.bgpick) { const st = await act("/api/profile", { bg: d.bgpick }); if (st) { settingsSig = ""; render(); } return; }
  if (d.savename !== undefined) {
    const st = await act("/api/profile", { name: $("#pfName").value, companion: $("#pfComp").value });
    if (st) { settingsSig = ""; render(); toast("win", "名字已儲存"); say(`<em>${esc(profile().name || "獵題人")}</em>，我記住了！`); }
    return;
  }
  if (d.login !== undefined) return doLogin();
  if (d.blogin !== undefined) return startBrowserLogin();
  if (d.bcancel !== undefined) { clearInterval(bloginTimer); await api("/api/login/cancel", {}).catch(() => {}); bloginShow(""); return; }
  if (d.relogin !== undefined) { $("#reloginBox").hidden = false; return; }
  if (d.logout !== undefined) { const st = await act("/api/logout", {}); if (st) { settingsSig = ""; render(); toast("info", "已登出"); } return; }
  if (d.ws !== undefined) { const r = await act("/api/workspace/open", {}); if (r) toast("info", "開啟工作區", r.path); return; }
  if (d.vscode !== undefined) { const st = await act("/api/vscode/install", {}); if (st) { settingsSig = ""; render(); toast("win", "VS Code 任務已安裝", "用 VS Code 打開工作區，按 Ctrl+Shift+B 就能提交"); } return; }
  if (d.ob === "next") {
    const st = await act("/api/profile", { name: $("#obName").value, lang: $("#obLang").value });
    if (st) { obStep = 2; modalKey = ""; render(); }
    return;
  }
  if (d.ob === "done") { obStep = 1; await act("/api/profile", { onboarded: true }); say(`歡迎，<em>${esc(profile().name || "獵題人")}</em>！先去酒館看看今天的委託吧。`); setTab("home"); return; }
});
document.addEventListener("change", async (ev) => {
  const t = ev.target;
  if (t.matches("input[data-upload]")) return uploadFile(t);
  if (t.id === "pfLang") { const st = await act("/api/profile", { lang: t.value }); if (st) toast("info", "解題語言已更新", t.selectedOptions[0].textContent); return; }
  if (t.id === "pfDim") { await act("/api/profile", { dim: Number(t.value) }); return; }
});
document.addEventListener("input", (ev) => {
  if (ev.target.id === "pfDim") { avatarKey = ""; const d = ev.target.value; const p = profile(); if (p.uploads?.bg) document.body.style.backgroundImage = `linear-gradient(rgba(10,12,18,${d}),rgba(10,12,18,${d})),url("/user-asset/bg?v=${encodeURIComponent(p.uploads.bg.split("v=")[1] || "1")}")`; }
});
document.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("label[role=button]")) { e.preventDefault(); e.target.querySelector("input")?.click(); return; }
  if ((e.key === "Enter" || e.key === " ") && e.target.matches("[data-enter],[data-node]")) { e.preventDefault(); e.target.dispatchEvent(new MouseEvent("click", { bubbles: true })); }
});

/* ================= 廣告推薦 ================= */
let adTimer = null, lastAd = 0;
async function maybeAd(force = false) {
  if (!S || !$("#ad").hidden || !$("#modal").hidden || !$("#busy").hidden || document.hidden) return;
  if (!force && Date.now() - lastAd < 200000) return;
  if (S.run && S.run.current && S.run.current.chosen) return; // 戰鬥中不打擾
  let r;
  try { r = await api("/api/ad", {}); } catch (e) { return; }
  if (!r.ad) return;
  lastAd = Date.now();
  const a = r.ad;
  const kick = ["限時賞金！", `${profile().companion || "露緹"}強力推薦`, "你的下一個對手", "今日特價：經驗 ×2", "剛好打得贏！"][Math.floor(Math.random() * 5)];
  const ad = $("#ad");
  ad.innerHTML = `<div class="ad-in">
    <span class="ad-tag">AD</span><button class="ad-x" data-adx disabled aria-label="關閉廣告">3</button>
    <div class="ad-kicker">${kick}</div>
    <div class="ad-title">#${esc(a.id)} ${esc(a.title)}</div>
    <ul class="ad-why">${a.reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <div class="ad-meta">${diffChip(a.difficulty)}<span>難度分 ${a.rating}</span><span class="x2">XP ×2</span>${a.tagNames.slice(0, 2).map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>
    <div class="ad-cta"><button class="btn primary" data-bounty="${esc(a.slug)}">接下賞金</button><button class="btn" data-view="${esc(a.slug)}">先看題目</button></div>
  </div>`;
  ad.hidden = false;
  let n = 3;
  const x = ad.querySelector(".ad-x");
  const iv = setInterval(() => { n--; if (n <= 0) { clearInterval(iv); x.disabled = false; x.textContent = "×"; } else x.textContent = n; }, 1000);
  ad.querySelectorAll("[data-bounty],[data-view]").forEach((b) => b.addEventListener("click", () => setTimeout(closeAd, 50)));
}
function closeAd() { $("#ad").hidden = true; }

/* ================= 輪詢：在終端機提交也會被遊戲判到 ================= */
let lastPoll = 0;
async function poll() {
  if (document.hidden || !$("#busy").hidden) return;
  const fighting = S && ((S.run && S.run.current && S.run.current.chosen) || Object.keys(S.meta.bounties).length);
  const gap = fighting ? 5000 : 30000;
  if (Date.now() - lastPoll < gap) return;
  lastPoll = Date.now();
  try { applyState(await api("/api/state")); } catch (e) { /* 伺服器關了就安靜等 */ }
}

(async function boot() {
  try {
    applyState(await api("/api/state"));
    lastPoll = Date.now();
  } catch (e) {
    $("#tab-home").innerHTML = `<div class="panel"><h2>連不到遊戲伺服器</h2><p class="muted">${esc(e.message)}</p><p>請在終端機執行 <span class="mono">python lc.py game</span>。</p></div>`;
    return;
  }
  setTab(tab);
  say(IDLE[Math.floor(Math.random() * IDLE.length)], false);
  setInterval(poll, 2500);
  addEventListener("focus", () => { lastPoll = 0; poll(); });
  setTimeout(() => maybeAd(true), 25000);
  setInterval(() => maybeAd(false), 60000);
})();
