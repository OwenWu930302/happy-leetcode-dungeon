# 參與開發

謝謝你願意一起把 LeetCode 演算法地城變得更好！不管是修錯字、加一句台詞、做一個資料包，還是寫新功能，都很歡迎。

## 在自己電腦上跑起來

```bash
git clone https://github.com/OwenWu930302/happy-leetcode-dungeon.git
cd happy-leetcode-dungeon
python -m pip install -r requirements.txt
python lc.py game
```

- 個人資料會放在專案底下的 `workspace/`（已經被 `.gitignore` 排除，不會被 commit）。
- 前端沒有建置步驟：改完 `game/static/` 重新整理瀏覽器就好。
- 改了 Python 要重新啟動 `python lc.py game`。

## 跑測試

```bash
python -m unittest discover -s tests
```

有 `g++` 或 `clang++` 的話，C++ 相關測試會一起跑；沒有就自動略過。每次 push 和 PR，GitHub Actions 會在 Windows 和 Linux 各跑一次。

## 資料夾地圖

| 位置 | 內容 |
| --- | --- |
| `lc.py` | 指令列工具：抓題、建檔、試跑、提交、同步 |
| `game/engine.py` | 技能樹、實力分、推薦 |
| `game/rogue.py` | 肉鴿遠征：地圖、戰鬥、遺物、組合技、流派技能、飛升 |
| `game/localrun.py` | 本地試跑（Python／C++ 測試外殼） |
| `game/hints.py`、`game/templates.py` | 提示階梯、技能模板 |
| `game/mistakes.py`、`game/weekly.py` | 錯題本、週報 |
| `game/bond.py` | 看板娘羈絆 |
| `game/mods.py` | 資料包載入與檢查 |
| `game/server.py` | 本機伺服器與 API |
| `game/static/` | 遊戲畫面（HTML／CSS／JS）、看板娘資料、羈絆劇情 |
| `docs/` | 說明文件、美術指南、資料包範例 |
| `tests/` | 單元測試 |

## 程式風格

- Python：標準函式庫優先，避免新增相依套件。函式短、名字清楚；給玩家看的訊息用白話中文。
- JavaScript：純 JS，不加框架。每個畫面一個 `renderXxx()`。
- 註解寫「為什麼」，不用寫「做了什麼」。
- 新功能盡量附測試（`tests/` 裡照現有的寫法加）。

## 開 PR 的流程

1. Fork 這個專案，開一個新分支：`git checkout -b my-feature`
2. 改完、跑測試、開遊戲看過畫面
3. 推到你的 fork，開 Pull Request，照著範本勾選

## 適合第一次貢獻的題目

- 幫某位看板娘多寫幾句台詞（`game/static/companions.json`）
- 新增一組遺物組合技（`game/rogue.py` 的 `SYNERGIES`，或做成資料包）
- 補一份技能模板（`game/templates.py`，記得 Python 和 C++ 都要，測試會檢查能不能編譯）
- 幫還沒有提示骨架的技能寫一份虛擬碼（`game/hints.py` 的 `SKELETONS`）
- 做一個資料包放進 `docs/`（格式見 [docs/MODS.md](docs/MODS.md)）
- 翻譯介面文字

## 不會接受的東西

- 繞過 LeetCode 真人驗證、偽裝成瀏覽器躲避偵測，或任何自動破解安全機制的程式
- 大量抓取題目、把題目敘述或別人的題解放進 repo
- 現有動畫、遊戲、漫畫的角色或圖片（看板娘規則見 [docs/ART_GUIDE.md](docs/ART_GUIDE.md)）
- 會上傳玩家資料的功能（遙測、雲端存檔）

## 回報問題

開 Issue 時選擇範本：錯誤回報、功能建議、新看板娘提案。錯誤回報的話，遊戲的「設定 → 工作區 → 產生錯誤報告」能產生一段已經遮掉個人資料的報告，直接貼上最快。
