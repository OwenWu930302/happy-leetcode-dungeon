// LeetCode 地城登入小幫手
// 在你平常的瀏覽器登入 leetcode.com 後，把兩個登入 cookie 交給本機的遊戲（127.0.0.1:8765～8774）。
// 不讀密碼、不讀其他網站、不送到任何外部伺服器。

const PORTS = Array.from({ length: 10 }, (_, i) => 8765 + i);
const NAMES = ["LEETCODE_SESSION", "csrftoken"];

function badge(text, color, title) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
  chrome.action.setTitle({ title: "LeetCode 地城登入小幫手：" + title });
}

async function readCookies() {
  const get = (name) => chrome.cookies.get({ url: "https://leetcode.com", name });
  const [s, c] = await Promise.all(NAMES.map(get));
  return s && c ? { session: s.value, csrftoken: c.value } : null;
}

async function sync() {
  const ck = await readCookies();
  if (!ck) {
    badge("!", "#b45309", "這個瀏覽器還沒登入 leetcode.com，登入後會自動同步");
    return;
  }
  for (const port of PORTS) {
    let res, data;
    try {
      res = await fetch(`http://127.0.0.1:${port}/ext/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(ck),
      });
      data = await res.json();
    } catch (e) {
      continue; // 這個埠沒有開，或不是遊戲：試下一個
    }
    if (!data || data.app !== "LeetCodeDungeon") continue;
    if (res.ok) badge("✓", "#15803d", `已同步登入到遊戲${data.user ? "（" + data.user + "）" : ""}`);
    else badge("✗", "#b91c1c", data.error || "遊戲沒有接受這組登入資訊");
    return;
  }
  badge("", "#6b7280", "沒找到開著的 LeetCode 地城（打開遊戲後按一下這個圖示）");
}

let timer = null;
function soon() {
  clearTimeout(timer);
  timer = setTimeout(sync, 1500);
}

// leetcode.com 的登入 cookie 一變（登入、換帳號、cookie 更新）就同步
chrome.cookies.onChanged.addListener(({ cookie, removed }) => {
  if (!removed && cookie.domain.endsWith("leetcode.com") && NAMES.includes(cookie.name)) soon();
});
chrome.action.onClicked.addListener(sync);
chrome.runtime.onStartup.addListener(sync);
chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create("sync", { periodInMinutes: 10 }); // 遊戲比瀏覽器晚開時，最多 10 分鐘內也會補上
  sync();
});
chrome.alarms.onAlarm.addListener(sync);
