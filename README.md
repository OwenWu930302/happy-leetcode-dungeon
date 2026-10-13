# 開心每日刷題 🎯

一個讓你在終端機就能管理 LeetCode 刷題的小工具：抓題目、寫解答、線上試跑、正式提交、
同步官網進度。專門針對 **簡單題**，適合重新熱身。

---

## 🎮 遊戲模式：演算法地城

```powershell
python lc.py game
```

刷題變成一款肉鴿（Roguelike）遊戲，畫面開在 VS Code 旁邊，一邊看題一邊寫：

| 畫面 | 內容 |
|------|------|
| **酒館** | 今日委託（依你的戰力挑的 3 題）、賞金任務、同步與擴充題庫 |
| **遠征** | 每局隨機生成 10 層地城：戰鬥、精英、寶箱、篝火、商店、神秘事件、Boss。答錯扣血、通過拿遺物，死掉留下結晶買永久強化 |
| **技能樹** | 依題目的 LeetCode 標籤**自動長出來**的技能樹，解題就會點亮，前置點亮後才解鎖下一環 |
| **戰力** | 類 Elo 戰力、段位、技能雷達圖、各技能戰力排行 |
| **題目** | 題目敘述、試招（範例測資）、出招（正式提交）、判題結果 |

右下角還會不定時跳出「廣告」，推一題剛好打得贏的題目給你，接下就是雙倍經驗的賞金任務。

### 在 VS Code 裡邊寫邊玩

1. 先裝一次 VS Code 任務：`python lc.py vscode`（會建立 `.vscode/tasks.json`）。
   之後用 VS Code 打開這個資料夾，第一次會問你「允許自動任務？」，選允許，一打開資料夾遊戲就會自動啟動
   （或手動：`Ctrl+Shift+P` → `Tasks: Run Task` → `🎮 開心刷題：開始遊戲`）。
2. `Ctrl+Shift+P` → 輸入 **Simple Browser: Show** → 貼上 `http://localhost:8765`，遊戲就開在編輯器旁邊。
   把它拖到右半邊，左邊寫程式、右邊看題目。
3. 在遊戲裡選題，解題檔會自動在 VS Code 打開，游標停在要寫程式的地方。
4. 寫完在遊戲按「試招」（不扣血）或「出招」（正式提交）。
   也可以直接在 VS Code 按 **`Ctrl+Shift+B`** 提交目前的檔案，遊戲會自動判定戰果。

### 背後的演算法（都在 `game/engine.py`）

- **技能樹自動生成**：每個 LeetCode 標籤是一個節點。常見標籤用手寫的前置關係；題庫出現沒看過的標籤時，
  找「比它常見、又最常一起出現」的標籤當前置（邊只從常見指向罕見，所以保證不會有環）。
  接著用 **Kahn 拓撲排序** 算層數、**重心法** 排版減少連線交叉，再依拓撲序做一次 **DAG DP** 決定每個節點有沒有點亮。
- **戰力**：每題依官方難度與通過率估一個難度分，把你的每次提交當成一場對戰，用 **Elo** 逐筆更新。
  各技能戰力 = 總戰力 + 你在該技能的「超額表現」（樣本少時打折）。
- **推薦**：每題打分 = 「難度離你的戰力 +80 多近」（高斯分布）×（1 + 技能弱點加成），再依分數加權抽樣，每次推的不一樣。
- **地城生成**：6 條路徑由下往上隨機走、避免交叉，再依層數規則分配節點種類（Slay the Spire 式）。

> 題庫預設只有簡單題。想讓技能樹長出動態規劃、圖論等更深的分支，在遊戲的酒館按「擴充題庫」，
> 或執行 `python lc.py fetch --all`。

---

## 目錄
1. [安裝](#一安裝)
2. [設定登入（一次就好）](#二設定登入一次就好)
3. [快速上手：刷第一題](#三快速上手刷第一題)
4. [完整指令說明](#四完整指令說明)
5. [典型使用情境](#五典型使用情境)
6. [檔案結構](#六檔案結構)
7. [常見問題](#七常見問題)

---

## 一、安裝

```powershell
pip install -r requirements.txt
```

只需要 `requests`（爬題、提交）和 `xhtml2pdf`（匯出 PDF，用不到可忽略）。

---

## 二、設定登入（一次就好）

`submit`、`test`、`sync` 會真的跟 LeetCode 互動，需要你的登入 cookie。
**不需要帳號密碼**，只要兩個 cookie：

1. 用瀏覽器登入 https://leetcode.com
2. 按 `F12` → **Application（應用程式）** 分頁
3. 左邊 **Cookies** → 點 `https://leetcode.com`
4. 複製這兩個值：
   - `LEETCODE_SESSION`（很長一串）
   - `csrftoken`
5. 把 `config.example.json` 複製成 `config.json`，填進去：

```json
{
  "csrftoken": "你的 csrftoken",
  "session": "你的 LEETCODE_SESSION",
  "lang": "python3"
}
```

> 🔐 `config.json` 是你的私人憑證，別分享、別上傳。cookie 約 14 天到期，
> 提交出現 403 或 sync 說「登入失效」時，回來重新複製一次即可。
>
> 只想看題目清單（`fetch` / `list` / `show` / `new` / `pdf`）的話，這步可以先跳過。

---

## 三、快速上手：刷第一題

```powershell
python lc.py fetch        # ① 第一次先抓簡單題清單（不需登入）
python lc.py show 1       # ② 看第 1 題（Two Sum）題目
python lc.py new 1        # ③ 建立解題檔 solutions/0001-two-sum.py
#                              → 打開它，在標記底下寫你的解法
python lc.py test 1       # ④ 用官方範例測資試跑（不算正式提交）
python lc.py submit 1     # ⑤ 正式提交判題，結果自動記進 records.json
python lc.py stats        # ⑥ 看自己的進度
```

題號可用數字（`1`）、英文代稱 slug（`two-sum`）或解題檔檔名（`0001-two-sum`）。

---

## 四、完整指令說明

### `fetch` — 抓題目清單
```powershell
python lc.py fetch          # 只抓簡單題
python lc.py fetch --all    # 抓全部難度（技能樹會更完整）
```
存到 `data/problems.json`。第一次使用、或想更新清單時跑。**不需登入**。

### `list` — 列出題目與完成狀態
```powershell
python lc.py list                     # 全部
python lc.py list --undone            # 只看還沒解出的
python lc.py list --free              # 只看免費題（排除付費題）
python lc.py list --tag array         # 只看某主題（array, string, hash-table…）
python lc.py list --limit 30          # 最多顯示 30 題
python lc.py list --free --undone --limit 20   # 條件可疊加
```
標記：`✅` 已解　`🔸` 試過還沒過　`🔒` 付費題。

### `show` — 顯示題目敘述
```powershell
python lc.py show 1
python lc.py show two-sum
```
在終端機顯示題目（純文字）。想要排版乾淨、不跑版的版本請用 `pdf`。

### `new` — 建立解題檔
```powershell
python lc.py new 1            # 產生 solutions/0001-two-sum.py（官方 Python 範本）
python lc.py new 1 --force    # 覆蓋重建（清掉現有內容，重新給空白範本）
```
檔案頂端是設定區（別動），`=== 以下是你的程式碼 ===` 標記底下才是你要寫的地方。

### `test` — 線上試跑（不算正式提交）
```powershell
python lc.py test 1                          # 用官方範例測資
python lc.py test 1 --input "[3,2,4]
6"                                           # 自訂測資（多行就照題目輸入格式換行）
```
會顯示你的輸出 vs 正確答案，方便除錯。**需登入**。

### `submit` — 正式提交判題
```powershell
python lc.py submit 1
```
真的送到 LeetCode 判題，顯示通過測資數 / 執行時間 / 記憶體，
並把這次結果寫進 `data/records.json`。**需登入**。

### `random` — 隨機抽一題
```powershell
python lc.py random              # 預設：免費且還沒解過的簡單題
python lc.py random --tag array  # 限定主題
python lc.py random --new        # 抽完直接幫你建好解題檔
python lc.py random --done       # 也納入已解過的（複習用）
python lc.py random --paid       # 也納入付費題
```
不知道要寫哪題時用這個，懶人專用。**不需登入**。

### `sync` — 同步 LeetCode 官網進度
```powershell
python lc.py sync
```
如果你平常直接在官網刷題，用這個把進度抓回來：
1. 用 cookie 確認你是誰（不用輸入帳密）
2. 抓各難度解題總數
3. 比對所有簡單題，標記你已解出的
4. 併入最近 20 筆 AC 紀錄（用 submission id 去重，重複跑不會重複記）

結果寫回 `data/records.json`。**需登入**。

### `push` — 把解過的題目推上 GitHub
```powershell
python lc.py push                                  # 提交並推送（第二次起這樣就好）
python lc.py push --repo https://github.com/你/倉庫.git   # 第一次：指定遠端
python lc.py push -m "解了三題！"                    # 自訂 commit 訊息
```
會做這些事：
1. 自動初始化 git、產生 `SOLVED.md`（漂亮的解題清單，含連結）
2. 提交 `solutions/`、進度紀錄、清單與程式
3. 推送到你的 GitHub

> 🔐 **安全**：`config.json`（你的登入 cookie）已被 `.gitignore` 排除，**絕對不會上傳**。

**第一次設定 GitHub（只做一次，二選一）：**

- (A) 已經在 GitHub 開好一個空 repo：
  ```powershell
  python lc.py push --repo https://github.com/你的帳號/倉庫名.git
  ```
- (B) 用 gh CLI 一鍵建立（先在終端機登入一次）：
  ```powershell
  gh auth login
  gh repo create leetcode-practice --public --source . --remote origin --push
  ```

設定好之後，每次想備份就只要 `python lc.py push`。

### `game` — 🎮 開啟遊戲
```powershell
python lc.py game               # 啟動並自動開瀏覽器
python lc.py game --no-browser  # 只啟動伺服器（在 VS Code Simple Browser 開）
python lc.py game --port 9000   # 換埠號
```
只聽本機 127.0.0.1，不會對外開放。關閉：在終端機按 `Ctrl+C`。

### `stats` — 看進度
```powershell
python lc.py stats
```
顯示簡單題總數、已解、嘗試過、總提交次數，以及最近解出的題目。

### `pdf` — 匯出題目 PDF（選用）
```powershell
python lc.py pdf 1                   # 單題 → pdf/0001-two-sum.pdf
python lc.py pdf 1 9 13              # 多題合成一份（每題一頁）
python lc.py pdf --range 1-50        # 題號 1~50 的簡單題
python lc.py pdf 1 --out 兩數之和.pdf  # 自訂檔名
```
保留粗體、範例框、清單、上下標（10⁴、O(n²)）。**不需登入**。

---

## 五、典型使用情境

**情境 A — 在這裡從頭刷一題**
```powershell
python lc.py list --free --undone --limit 20   # 挑一題還沒寫的
python lc.py show 9                             # 看題目
python lc.py new 9                              # 建檔、寫解法
python lc.py test 9                             # 試跑
python lc.py submit 9                           # 提交
```

**情境 B — 平常在官網刷，只想把進度抓回來管理**
```powershell
python lc.py sync       # 抓回已解題目與最近 AC
python lc.py stats      # 看整理後的進度
```

**情境 C — 找下一題練什麼**
```powershell
python lc.py sync                   # 先同步最新進度
python lc.py list --undone --free   # 列出還沒解的免費題
```

---

## 六、檔案結構

```
lc.py                  主程式
config.json            你的登入 cookie（自己建立，請勿外流）
config.example.json    設定範本
requirements.txt       相依套件
data/problems.json     簡單題清單
data/records.json      你的提交紀錄與完成狀態 ← 進度都記在這
data/game.json         遊戲存檔（遠征、結晶、賞金）
game/                  遊戲模式：engine.py（演算法）、rogue.py（遠征）、server.py（本機伺服器）、static/（畫面）
game/vscode/           VS Code 任務範本（python lc.py vscode 會裝到 .vscode/）
data/details/          各題敘述快取
solutions/             你的解題檔
pdf/                   匯出的題目 PDF
```

---

## 七、常見問題

**Q：提交出現 403 / sync 說登入失效？**
cookie 過期了。回 [第二節](#二設定登入一次就好) 重新複製 `LEETCODE_SESSION` 與 `csrftoken` 到 `config.json`。

**Q：終端機題目跑版、看不懂？**
用 `python lc.py pdf <題號>` 匯出排版乾淨的 PDF，或直接上官網看，再回來 `new` / `submit`。

**Q：解到一半想清空重寫？**
`python lc.py new <題號> --force` 會重新給你空白的官方範本。

**Q：解題檔要寫在哪？**
打開 `solutions/<題號>.py`，在 `=== 以下是你的程式碼 ===` 那行底下寫。
上面的設定區（meta-slug 等）不要動，提交時程式靠它辨識題目。
