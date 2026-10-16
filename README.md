# LeetCode 演算法地城

**把刷 LeetCode 變成一款肉鴿（Roguelike）遊戲。** 解題會點亮技能樹、累積戰力，選題後解題檔會直接在 VS Code 打開，看題、試跑、提交都在遊戲裡完成，還有看板娘陪你一起刷題。

*A roguelike game layer for LeetCode: auto-generated skill tree, contest-scale skill rating with 9 rank tiers, smart problem recommendations, and a VS Code workflow. Traditional Chinese UI.*

![酒館：今日委託與推薦廣告](docs/home.png)

## 特色

- **肉鴿遠征**：每局隨機生成 10 層地城，有戰鬥、精英、寶箱、篝火、商店、神秘事件和 Boss。答錯扣血、通過拿遺物，Boss 會從你最弱的技能出題。死掉會留下結晶，可以買永久強化。
- **自動技能樹**：依題目的 LeetCode 標籤自動長出來。題庫出現新標籤時，演算法會自己推斷它的前置技能。
- **實力分與段位**：用社群的題目難度表，依你解過最難的題目算出實力分（跟 LeetCode 競賽分同尺度），9 階段位從青銅到神話，大佬也分得出高下。有參加週賽的話會一併抓回官方競賽分。
- **推薦廣告**：挑「努力一下打得贏」的題目，用廣告推給你，接下就是雙倍經驗的賞金任務。
- **VS Code 整合**：選題就自動開檔，游標停在要寫程式的地方，按 `Ctrl+Shift+B` 直接提交。
- **本地試招**：Python 3 和 C++ 直接在你的電腦上用範例測資跑，幾百毫秒就有結果、不用登入，每筆測資的輸出、正確答案和 print 都看得到。跑不了的題目（互動題等）自動改用 LeetCode 線上試跑。
- **冒險日誌**：出招沒過自動記進錯題本（當時的程式碼、出錯的測資），可以標錯因；每週一跳出上週週報：解了幾題、實力分變化、新點亮的技能、最弱的標籤和下週建議。
- **每日挑戰與分享卡**：每天一張所有人都一樣的地圖，打完拿到成績碼可以跟朋友比；一鍵產生段位或週報的分享圖片。
- **不怕弄丟進度**：每天自動備份紀錄、存檔和解題檔（保留 14 份），設定頁一鍵還原。
- **8 位個性不同的看板娘**：每位都有自己的推薦策略、台詞和小加成。想補弱點、想維持手感、想複習、想練週賽，換一位夥伴就換一種刷題節奏。
- **每個人都能玩**：在遊戲裡登入自己的 LeetCode 帳號、換看板娘或上傳頭像、換背景，也能選解題語言（Python、C++、Java、JavaScript、Go、Rust…）。

| 遠征 | 技能樹 |
|---|---|
| ![遠征戰鬥](docs/battle.png) | ![技能樹](docs/tree.png) |
| **戰力** | **看板娘** |
| ![戰力分析](docs/power.png) | ![換頭像](docs/avatars.png) |

## 快速開始

### 方法 A：下載 EXE（Windows，不用裝 Python）

1. 到 [Releases](../../releases) 下載最新的 `LeetCodeDungeon.exe`。
2. 雙擊執行，瀏覽器會自動打開遊戲畫面。
   > Windows 第一次可能跳出「Windows 已保護您的電腦」，因為這個 EXE 沒有付費簽章。按「其他資訊 → 仍要執行」即可。程式完全開源，可以自己從原始碼打包。
3. 跟著新手引導選看板娘、選語言、登入 LeetCode。

你的資料會存在 `文件\LeetCodeDungeon`。

### 方法 B：從原始碼執行（任何作業系統）

```bash
git clone https://github.com/OwenWu930302/happy-leetcode-dungeon.git
cd happy-leetcode-dungeon
pip install -r requirements.txt
python lc.py game
```

需要 Python 3.8 以上。你的資料會存在專案底下的 `workspace/`（已被 `.gitignore` 排除，不會被上傳）。

## 登入 LeetCode

試跑、提交、同步官網進度都需要登入。遊戲**不需要你的密碼**。

**方法一：用瀏覽器登入（推薦）**
到「設定 → 帳號」按「用瀏覽器登入 LeetCode」。程式會用你電腦上的 Edge 或 Chrome 開一個獨立的登入視窗，你在裡面正常登入（email、GitHub、Google 都可以），完成後視窗會自動關閉。

- 密碼是直接輸入給 LeetCode 官網，遊戲完全碰不到。
- 登入視窗使用獨立的瀏覽器設定檔（存在工作區的 `browser-profile/`），不會動到你平常的瀏覽器。
- cookie 過期時再按一次，通常 LeetCode 還記得你，不用重打密碼。
- 原理：LeetCode 沒有給第三方用的官方登入，所以程式透過瀏覽器內建的除錯介面（只聽本機 127.0.0.1）讀取 `leetcode.com` 的兩個 cookie。程式碼在 [`game/browser_login.py`](game/browser_login.py)。

**方法二：手動貼 cookie（備案）**

1. 用瀏覽器登入 [leetcode.com](https://leetcode.com)。
2. 按 `F12` → **Application（應用程式）** → 左邊 **Cookies** → `https://leetcode.com`。
3. 複製 `LEETCODE_SESSION` 和 `csrftoken` 的 Value，貼到「設定 → 帳號 → 備案：手動貼 cookie」，按「驗證並登入」。

不管用哪個方法，cookie 都只存在你電腦上工作區的 `config.json`，不會上傳到任何地方。

### 提交會不會被 LeetCode 擋？

LeetCode 有 Cloudflare 防火牆，程式直接送出的提交，有時會被要求「確認你是真人」。所以遊戲預設**由瀏覽器送出**：

- 背景會開一個藏在螢幕外的瀏覽器視窗（就是登入用的那個），試招、出招都由它代送。對 LeetCode 來說，這就是一般人在用的瀏覽器。
- 只有 LeetCode 真的要求點「我是真人」時，視窗才會跳到螢幕中間，遊戲裡也會提示；你點完它會自動藏回去，判題繼續。程式不會代替你通過驗證。
- 你選題或看題時，背景就先把瀏覽器準備好；關掉遊戲時，這個瀏覽器也會一起關掉。
- 想要最快的速度，可以到「設定 → 帳號 → 提交方式」改成「程式直接送出」，被擋時一樣會自動改用瀏覽器。

## 在 VS Code 邊寫邊玩

1. 到遊戲的「設定 → 工作區」按「安裝 VS Code 任務」（順便會開啟自動存檔），再按「在 VS Code 開啟工作區」。
2. VS Code 會問「允許自動任務？」，選允許，之後一打開工作區遊戲就會自動啟動。
3. 按 `Ctrl+Shift+P` → 輸入 **Simple Browser: Show** → 貼上 `http://localhost:8765`，把遊戲拖到編輯器右邊。
4. 在遊戲裡選題，解題檔會自動打開。寫完在遊戲按「試招」（不扣血）或「出招」（正式提交），或在 VS Code 按 **`Ctrl+Shift+B`** 直接提交。

不管從哪裡提交，遊戲都會自動判定戰果。

## 玩法

| 畫面 | 內容 |
|------|------|
| **酒館** | 今日委託（依戰力挑的 3 題）、賞金任務、同步官網進度、擴充題庫 |
| **遠征** | 選路線、打怪、拿遺物。戰鬥從 2~3 題裡挑一題打，答錯一次扣 10 HP（精英 16、Boss 22） |
| **技能樹** | 加權解題分（簡單 1、中等 2、困難 3）達 2 分就點亮，最高 Lv5；前置技能點亮後才解鎖下一環 |
| **戰力** | 段位（青銅 → 神話，每階分 IV～I）、實力分、官方競賽分、戰力、技能雷達、分享卡 |
| **日誌** | 本週／上週週報、錯題本（標錯因、再挑戰） |
| **題目** | 題目敘述、自訂測資、試招（本地）、出招（提交）、每筆測資的結果 |
| **設定** | LeetCode 帳號、看板娘圖鑑與頭像、背景、解題語言、環境檢查與試招方式、存檔備份、工作區 |

遺物共 12 種，例如「小黃鴨」讓每場戰鬥第一次答錯不扣血，「招財貓」可以免費換題。永久強化可以用結晶購買，例如最大 HP、遠征經驗加成、開場遺物。

題庫預設只有簡單題（內建 947 題，不用等下載）。到酒館按「擴充題庫」可以抓全部難度，技能樹會長出動態規劃、圖論等更深的分支。

## 看板娘

每位看板娘＝一種刷題策略＋一種說話風格。在「設定 → 看板娘圖鑑」可以看介紹、隨時換人；上傳自己的頭像時，也能另外選個性。

| 角色 | 稱號 | 推薦風格 | 特殊加成 |
|---|---|---|---|
| 露緹 | 星詠的導師 | 均衡：補你最弱的技能，難度比你的實力分高一點點 | 沒有特別加成，最適合剛開始的獵題人 |
| 米菈 | 元氣啦啦隊 | 舒適：偏好通過率高、打得贏的題，幫你維持手感 | 遠征中連續過關不答錯，經驗每次多 10%（最多 +30%） |
| 夏音 | 節拍守護者 | 打卡：推短小好上手的簡單題，讓你每天都能完成一題 | 連續刷題天數越長，遠征經驗越多（每天 +3%，最多 +21%） |
| 雪奈 | 冰霜教官 | 嚴格：專攻你最弱的技能，難度明顯高於你的實力分 | 遠征經驗 +25%，但答錯受到的傷害也 +20% |
| 琥珀 | 書塔的學者 | 系統化：照技能樹由淺到深，先把前置技能補穩，每題附上考的觀念 | 推薦題目時會附上「這題考的觀念」 |
| 夜櫻 | 月下的旅人 | 探索：推你沒碰過的標籤和冷門題型，擴大你的技能版圖 | 遠征地圖上的神秘事件變多 |
| 珂可 | 競技場的鬥士 | 競賽：推 LeetCode 週賽出過的題，難度偏高，練實戰反應 | Boss 對你的傷害 -30%，擊敗 Boss 的經驗 +30% |
| 星璃 | 記憶的守護者 | 複習：重推你以前答錯過、或很久沒碰的題（間隔重複），再搭配少量新題 | 遠征篝火休息時回血 ×1.5 |

- **露緹・星詠的導師**：地城酒館的老闆娘，也是帶過最多新人的嚮導。說話溫和，總是先看你哪裡還不穩，再一步步把你帶上去。
- **米菈・元氣啦啦隊**：全地城最大聲的應援團長。相信「贏的感覺會上癮」，所以專挑你打得贏的題目，讓你一路連勝停不下來。
- **夏音・節拍守護者**：戴著耳機、走路都在打拍子的少女。她相信「每天一點點」比偶爾爆肝更有用，最在意的是你今天有沒有來。
- **雪奈・冰霜教官**：嘴巴很壞、標準很高的教官。只推你最弱的技能、而且比你現在的程度難一截的題目。罵歸罵，你答對時她會偷偷笑。
- **琥珀・書塔的學者**：住在地城圖書館的學者，眼鏡後面是一整座知識地圖。她堅持先打地基：前置技能沒練穩，就不讓你碰後面的。
- **夜櫻・月下的旅人**：只在夜裡出現的神秘旅人，對沒走過的路特別著迷。她會帶你去技能樹的角落，推那些你從沒碰過的冷門題型。
- **珂可・競技場的鬥士**：長著角的熱血鬥士，最愛週賽的緊張感。她只推競賽出過的題目，要你練出在時間壓力下也能出手的反應。
- **星璃・記憶的守護者**：頭上頂著光環的溫柔守護者。她記得你寫過的每一題，會在你快忘記的時候，把以前錯過或很久沒碰的題目再拿出來複習。

想新增角色或台詞？全部都在 [`game/static/companions.json`](game/static/companions.json)，照格式加一筆、發 PR 就好。

## 背後的演算法

都在 [`game/engine.py`](game/engine.py) 和 [`game/rogue.py`](game/rogue.py)。

- **技能樹自動生成**：每個 LeetCode 標籤是一個節點。常見標籤使用手寫的前置關係；沒看過的標籤則找「比它常見、又最常一起出現」的標籤當前置。邊只從常見指向罕見，所以保證不會有環。接著用 **Kahn 拓撲排序** 算層數、**重心法** 排版減少連線交叉，再依拓撲序做一次 **DAG DP**，決定每個節點有沒有點亮。
- **題目難度分**：使用社群的 [zerotrac 題目難度表](https://github.com/zerotrac/leetcode_problem_rating)（約 2600 題競賽題，跟 LeetCode 競賽分同尺度），執行時下載、一週更新一次。沒收錄的題目，用拿這份表回歸出來的公式（官方難度＋通過率）估計。
- **實力分**：取你解過最難的 10 題做加權平均，解題數少時往 1000 打折。跟刷題順序無關，狂刷簡單題不會灌分；有官方競賽分時取兩者較高者。各技能實力分用同樣方法，只看該技能的題目。
- **段位**：青銅（<1200）、白銀、黃金、白金、鑽石、大師（2000）、宗師（2200）、傳說（2400）、神話（2700+），每階分 IV～I。
- **戰力**：每題貢獻（難度分 ÷ 1000）³ × 100，會一直成長的遊戲數字。
- **推薦**：每題分數 =「難度離你的實力分 + 偏移量多近」（高斯分布）×（1 + 各種加成），再依分數加權抽樣，所以每次推的題目都不一樣。偏移量和加成的權重由看板娘決定：例如雪奈把偏移量拉到 +230 並加重弱點權重，米菈偏好高通過率，夜櫻加重沒碰過的標籤，珂可只推週賽題，星璃則用間隔重複挑出以前答錯或很久沒碰的題目來複習。
- **地城生成**：6 條路徑由下往上隨機走並避免交叉，再依層數規則分配節點種類（Slay the Spire 式）。每局都有種子，可以重現。

## 指令列工具

遊戲之外，`lc.py` 也能單獨在終端機使用。EXE 版把 `python lc.py` 換成 `LeetCodeDungeon.exe` 即可。

```bash
python lc.py game                 # 開啟遊戲
python lc.py list --undone --free # 列出還沒解的免費題
python lc.py show 1               # 看題目
python lc.py new 1 --lang cpp     # 建立解題檔（可選語言）
python lc.py test 1               # 用範例測資試跑（先在本地跑，跑不了才用 LeetCode）
python lc.py test 1 --online      # 一律用 LeetCode 線上試跑
python lc.py submit 1             # 正式提交
python lc.py sync                 # 同步官網進度
python lc.py fetch --all          # 抓全部難度的題庫
python lc.py random --new         # 隨機抽一題並建檔
python lc.py stats                # 看進度
python lc.py vscode               # 在工作區安裝 VS Code 任務
python lc.py push --repo <網址>   # 把工作區備份到你自己的 GitHub 倉庫
python lc.py pdf 1 9 13           # 匯出題目 PDF（需要 xhtml2pdf）
```

題號可以用數字（`1`）、slug（`two-sum`）或解題檔檔名（`0001-two-sum.cpp`）。

## 你的資料放在哪

所有個人資料都在**工作區**，每個玩家各自一份，不會進到這個開源 repo：

```
工作區/
├── config.json          登入 cookie（只在你電腦上）
├── solutions/           你的解題檔
├── data/records.json    提交紀錄
├── data/game.json       遊戲存檔（遠征、結晶、賞金）
├── data/profile.json    暱稱、看板娘、背景
├── data/mistakes.json   錯題本
├── backups/             每日存檔快照（不含登入 cookie）
└── assets/              你上傳的頭像與背景
```

- EXE 版：`文件\LeetCodeDungeon`
- 原始碼版：專案底下的 `workspace/`
- 想放別的地方：設定環境變數 `LCD_HOME`

想把解題紀錄備份到 GitHub：先開一個**你自己的**倉庫（建議 Private），然後執行 `python lc.py push --repo https://github.com/你/my-leetcode.git`。`config.json` 會被自動排除。

## 打包 EXE

**在自己電腦上**（Windows）：

```bat
build.bat
```

完成後 EXE 會在 `dist\LeetCodeDungeon.exe`。

**自動發佈**：推一個版本標籤，GitHub Actions 就會在 Windows 上打包，並發佈到 Releases。

第一次要先啟用 workflow（把範本複製到 `.github/workflows/`）：

```bat
mkdir .github\workflows
copy tools\release.yml .github\workflows\release.yml
git add .github && git commit -m "Enable release workflow" && git push
```

之後每次要發佈新版本：

```bash
git tag v1.0.0
git push origin v1.0.0
```

## 專案結構

```
lc.py                 指令列工具（抓題、建檔、試跑、提交、同步）
launcher.py           EXE 進入點
game/engine.py        演算法：技能樹、戰力、推薦
game/rogue.py         肉鴿遠征：地圖、戰鬥、遺物、強化
game/server.py        本機伺服器（只聽 127.0.0.1）
game/browser_login.py 瀏覽器一鍵登入、瀏覽器代送提交（DevTools Protocol）
game/localrun.py      本地試跑：Python／C++ 測試外殼、範例答案比對
game/mistakes.py      錯題本
game/weekly.py        週報
game/backup.py        每日存檔快照與還原
game/static/          遊戲畫面（純 HTML/CSS/JS，沒有外部框架）
data/problems.json    內建題庫（簡單題）
tests/                單元測試（python -m unittest discover -s tests）
build.bat             Windows 打包腳本
tools/release.yml     自動打包發佈的 GitHub Actions 範本
tools/ci.yml          每次 push 自動跑測試的 GitHub Actions 範本
```

## 常見問題

**Q：試招或出招出現 403、同步說登入失效？**
cookie 過期了，到「設定 → 帳號」再登入一次。

**Q：出招出現 `IndentationError`，或說「還是空白範本」？**
解題檔還沒存檔（VS Code 分頁標題旁邊有白點 ●）。按 `Ctrl+S`，或在設定頁安裝 VS Code 任務來開啟自動存檔。

**Q：試招說「改用 LeetCode 線上試跑」？**
本地試跑目前支援 Python 3 和 C++。用別的語言、這台電腦沒有 Python 或 C++ 編譯器，或是互動題、有隱藏參數的題目（例如鏈結串列的環），就會改用 LeetCode。到「設定 → 環境與試招」看缺什麼、怎麼裝。

**Q：本地試招全對，出招卻沒過？**
本地只跑題目裡的範例，LeetCode 出招會跑幾十到幾百筆隱藏測資。沒過的那筆會記進錯題本，裡面有出錯的輸入，貼到「自訂測資」就能在本地重現。

**Q：瀏覽器登入說找不到 Edge 或 Chrome？**
用手動貼 cookie，或設定環境變數 `LCD_BROWSER` 指向瀏覽器執行檔。

**Q：支援力扣中文站（leetcode.cn）嗎？**
目前只支援 leetcode.com 帳號。題目頁有連到力扣中文站的連結，可以對照看中文題目。歡迎 PR！

**Q：遊戲畫面開在哪個網址？**
`http://localhost:8765`（被占用時會自動往後找可用的埠，終端機會顯示）。伺服器只聽本機，其他人連不進來。

**Q：可以在 Mac / Linux 玩嗎？**
可以，用方法 B 從原始碼執行。

## 參與開發

歡迎 Issue 和 PR！一些想做的方向：力扣中文站支援、更多看板娘與遺物、成就系統、多人排行榜。

前端沒有建置步驟，改完 `game/static/` 重新整理瀏覽器就能看到；改 Python 則要重新啟動 `python lc.py game`。

送 PR 前先跑測試：`python -m unittest discover -s tests`。要讓 GitHub 每次 push 自動跑，把 `tools/ci.yml` 複製到 `.github/workflows/ci.yml`。

## 授權

[MIT](LICENSE)。本專案與 LeetCode 官方無關。

看板娘的圖像與名字由 AI 生成，如有雷同，純屬巧合。

題目難度分來自 [zerotrac/leetcode_problem_rating](https://github.com/zerotrac/leetcode_problem_rating)，執行時才下載，不包含在本專案中。
