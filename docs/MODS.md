# 資料包（Mods）

資料包可以替遊戲新增**看板娘、遺物、神秘事件、遺物組合技**。資料包只有資料（JSON 和圖片），遊戲不會執行裡面的任何程式碼，所以下載別人的資料包是安全的。

## 放在哪裡

工作區裡的 `mods` 資料夾（遊戲的「設定 → 資料包 → 開啟 mods 資料夾」會幫你建好並打開）：

```
工作區/mods/
├── 小包.json                 只有文字資料：直接放一個 JSON
└── 我的資料包/
    ├── mod.json              有圖片：放在自己的資料夾，主檔叫 mod.json
    └── pola.png
```

放好之後到「設定 → 資料包」按「重新載入」。格式有錯的話，那裡會列出是哪一行、哪個欄位，整包都不會載入，不會弄壞遊戲。

完整範例：[`docs/example-mod/mod.json`](example-mod/mod.json)。把整個 `example-mod` 資料夾複製到 `mods/` 就能看到效果。

## 最外層

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `id` | ✔ | 資料包代號：1～32 個小寫英文、數字、`-`、`_`。不能跟別的資料包重複 |
| `name` | ✔ | 顯示名稱（40 字內） |
| `version` |  | 版本，例如 `"1.0"` |
| `author` |  | 作者 |
| `description` |  | 一段介紹（300 字內） |
| `companions` |  | 看板娘清單 |
| `relics` |  | 遺物清單 |
| `events` |  | 神秘事件清單 |
| `synergies` |  | 組合技清單 |

## 看板娘 `companions`

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `id` | ✔ | 小寫英文、數字、`-`、`_` |
| `name` | ✔ | 名字（12 字內） |
| `title` | ✔ | 稱號（20 字內） |
| `intro` | ✔ | 介紹（300 字內） |
| `style` |  | 推薦風格的說明 |
| `perk` |  | 加成說明（資料包角色沒有專屬加成，寫給玩家看的文字） |
| `skill` |  | 沿用哪位內建看板娘的流派技能：`p0`～`p7`（露緹、米菈、夏音、雪奈、琥珀、夜櫻、珂可、星璃） |
| `strategy` |  | 推薦題目的方式：`mode`、`offset`（-300～400，難度比實力分高多少）、`width`（80～400，難度範圍寬窄） |
| `lines` |  | 台詞，每種是一個文字清單；`{name}` 會換成玩家暱稱 |
| `image` |  | 頭像圖片（PNG、JPG、WebP、GIF，2 MB 內），要放在資料包自己的資料夾裡 |

`mode` 可以用：`balanced` 均衡、`comfort` 舒適、`daily` 打卡、`weakest` 弱點、`tree` 系統化、`explore` 探索、`contest` 競賽、`review` 複習。

台詞種類：`greet`、`idle`、`recommend`、`choose`、`testOk`、`testFail`、`win`、`hit`、`levelup`、`lit`、`bounty`、`dead`、`won`、`login`。沒寫的會用露緹的台詞。

## 遺物 `relics`

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `id` | ✔ | 小寫英文、數字、`-`、`_` |
| `name` | ✔ | 名字（16 字內） |
| `glyph` | ✔ | 顯示在圓圈裡的字（1～2 字） |
| `desc` | ✔ | 效果說明（120 字內） |
| `effect` | ✔ | 效果，至少一種（見下表） |

| 效果 | 範圍 | 意思 |
| --- | --- | --- |
| `heal_on_win` | 0～20 | 擊敗怪物時回復的 HP |
| `gold_mult` | 0.5～2 | 擊敗怪物拿到的金幣倍率 |
| `xp_mult` | 0.5～2 | 遠征經驗倍率 |
| `dmg_mult` | 0.5～1.5 | 答錯受到的傷害倍率 |
| `max_hp` | 0～30 | 拿到時增加的最大 HP |
| `camp_mult` | 0.5～3 | 篝火休息的回復倍率 |

## 神秘事件 `events`

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `title` | ✔ | 標題（30 字內） |
| `text` | ✔ | 內文（200 字內） |
| `effects` | ✔ | `heal`（-30～30）、`gold`（0～100）、`maxhp`（0～15）、`xp`（0～60）、`relic`（0 或 1，送一件隨機遺物） |

## 組合技 `synergies`

| 欄位 | 必填 | 說明 |
| --- | --- | --- |
| `id` | ✔ | 小寫英文、數字、`-`、`_` |
| `name` | ✔ | 名字 |
| `relics` | ✔ | 剛好兩件遺物：可以是內建遺物（例如 `coffee`），或這個資料包自己的遺物 id |
| `desc` | ✔ | 效果說明 |
| `effect` | ✔ | 跟遺物一樣的效果欄位 |

內建遺物的 id：`rubber_duck`、`coffee`、`golden_keyboard`、`stack_amulet`、`big_o`、`debugger`、`hash_charm`、`recursion_mirror`、`leet_crown`、`two_pointer_boots`、`lucky_cat`、`compiler_heart`。

## 規矩

- **原創**：不要放現有動畫、遊戲、漫畫的角色或圖片。看板娘的美術規則見 [ART_GUIDE.md](ART_GUIDE.md)。
- **全年齡**：台詞和介紹以陪伴、鼓勵為主。
- 想把你的資料包分享給大家？開一個 Issue（選「新看板娘提案」），或直接開 PR 放進 `docs/` 底下。
