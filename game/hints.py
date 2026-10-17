"""提示階梯：卡住時一階一階打開。

第 1 階：這題相關的技能（題目標籤）
第 2 階：主要技能的核心觀念（一句話）
第 3 階：主要技能的通用虛擬碼骨架

內容都是技能層級的通用教學，不針對任何一題寫解答，也不搬運別人的題解。
每打開一階，這題的獎勵 -15%（遠征經驗與賞金都算）。
"""
from __future__ import annotations

from collections import Counter

from game import engine

PENALTY = 0.15
MAX_LEVEL = 3

SKELETONS = {
    "hash-table": "seen = 空的字典\n對每個元素 x：\n    如果「x 需要配對的東西」在 seen 裡 → 找到答案\n    把 x 的資訊記進 seen",
    "two-pointers": "l = 0，r = n - 1\n當 l < r：\n    看 a[l] 和 a[r] 的關係\n    依照情況把 l 往右或把 r 往左",
    "sliding-window": "l = 0\n對每個 r：\n    把 a[r] 放進視窗\n    當視窗不合法：把 a[l] 移出，l += 1\n    用目前的視窗更新答案",
    "binary-search": "lo, hi = 答案可能的範圍\n當 lo < hi：\n    mid = (lo + hi) // 2\n    如果 mid「夠了」→ hi = mid\n    否則 → lo = mid + 1\n回傳 lo",
    "prefix-sum": "pre[0] = 0\npre[i + 1] = pre[i] + a[i]\n區間 [l, r] 的和 = pre[r + 1] - pre[l]\n常搭配字典：記住每個前綴和出現幾次",
    "stack": "st = 空堆疊\n對每個元素：\n    如果它能和堆疊頂端配對 → 彈出\n    否則 → 推入\n最後看堆疊剩下什麼",
    "monotonic-stack": "st = 空堆疊（存索引，對應的值保持單調）\n對每個 i：\n    當 st 不空且 a[st 頂端] < a[i]：\n        頂端元素的「下一個更大」就是 i，彈出它\n    推入 i",
    "queue": "q = 佇列，先放起點\n當 q 不空：\n    取出最前面的處理\n    把接下來要處理的放到最後面",
    "breadth-first-search": "q = [起點]，標記起點走過，步數 = 0\n當 q 不空：\n    把這一層全部取出\n    對每個鄰居：沒走過就標記並放進 q\n    步數 += 1",
    "depth-first-search": "dfs(位置)：\n    如果越界、走過或不能走 → 回傳\n    標記走過\n    對每個鄰居 dfs(鄰居)\n從每個還沒走過的起點呼叫 dfs",
    "backtracking": "path = []\nbt(i)：\n    如果完成 → 記下 path 的副本，回傳\n    對每個可以做的選擇：\n        不合法就跳過（剪枝）\n        做選擇；bt(下一步)；撤銷選擇",
    "dynamic-programming": "dp[狀態] = 這個子問題的答案\n先填好最小的初始狀態\n照依賴順序走過每個狀態：\n    dp[狀態] = 用較小的狀態組合（取 max、min 或加總）\n答案在 dp[最終狀態]",
    "memoization": "f(參數)：\n    算過就直接回傳記下的答案\n    用較小的參數遞迴算出答案\n    記下來再回傳",
    "greedy": "先依某個關鍵排序\n依序處理每個元素：\n    能拿就拿（或挑當下最好的）\n說服自己：把任何一步換掉都不會更好",
    "sorting": "先排序（必要時自訂比較方式）\n排好之後，相鄰元素、前後關係就容易判斷",
    "heap-priority-queue": "h = 堆積（最小或最大）\n每次取出最好的那個處理\n把新產生的候選放回 h\n只要前 k 個：讓 h 的大小維持在 k",
    "linked-list": "dummy = 新節點，dummy.next = head\nprev = dummy，cur = head\n一邊走一邊改指標（先存好 next 再改）\n回傳 dummy.next",
    "tree": "solve(node)：\n    node 是空的 → 回傳基本值\n    left = solve(node.left)\n    right = solve(node.right)\n    用 left、right、node.val 組出這棵子樹的答案",
    "binary-tree": "solve(node)：\n    node 是空的 → 回傳基本值\n    left = solve(node.left)\n    right = solve(node.right)\n    用 left、right、node.val 組出這棵子樹的答案\n（要一層一層處理時，改用佇列做層序走訪）",
    "binary-search-tree": "利用左小右大：\n    目標比 node.val 小 → 往左\n    目標比較大 → 往右\n中序走訪會得到排序好的序列",
    "graph": "adj[u] = [v, ...]（鄰接表）\n用 BFS 或 DFS 走過相連的點\n一定要標記走過，避免繞圈",
    "topological-sort": "算每個點的入度\nq = 所有入度為 0 的點\n當 q 不空：\n    取出 u，放進結果\n    把 u 指向的點入度 -1，變成 0 就放進 q\n結果少於 n 個 → 有環",
    "shortest-path": "dist = 全部無限大，dist[起點] = 0\nh = 最小堆積 [(0, 起點)]\n當 h 不空：\n    取出 (d, u)；d 比 dist[u] 大就跳過\n    對每條邊 (u, v, w)：能讓 dist[v] 變小就更新並放進 h",
    "union-find": "parent[i] = i\nfind(x)：沿著 parent 往上找根，順便路徑壓縮\nunion(a, b)：把兩個根接起來\n同一群 ⇔ find(a) == find(b)",
    "trie": "每個節點：children（字元 → 節點）和 end 標記\n插入：沿著字元往下走，沒有就建\n查詢：沿著字元往下走，走不下去就失敗",
    "bit-manipulation": "x & 1 看最低位，x >> 1 往右移一位\nx ^ x = 0：成對的會互相抵銷\nx & (x - 1) 去掉最低的那個 1",
    "math": "先手算幾個小例子，找出規律\n把規律寫成公式或遞推\n注意溢位、除以 0 和負數",
    "counting": "cnt = 計數器\n對每個元素 cnt[x] += 1\n再依題意比較或走過 cnt",
    "matrix": "dirs = 上下左右四個方向\n對每個格子 (r, c)：\n    對每個方向算出 (nr, nc)\n    先檢查邊界再存取",
    "simulation": "把規則一條一條翻成程式\n用變數記住目前的狀態\n一步一步更新，直到結束條件成立",
    "string": "一個字元一個字元走過\n需要時搭配計數器或雙指標\n要大量串接時，先放進陣列，最後再合併",
    "array": "先想：一次走訪能不能解（O(n)）？\n需要快速查詢時，搭配雜湊表或前綴和",
    "recursion": "f(問題)：\n    基本情況直接回傳\n    相信 f(較小的問題) 已經正確\n    用它組出 f(問題) 的答案",
    "design": "先決定用哪些資料結構存狀態\n每個操作要多快？依此挑結構（雜湊表、堆積、鏈結串列…）\n建構子負責初始化，每個方法只做自己的事",
    "divide-and-conquer": "solve(範圍)：\n    夠小就直接算\n    切成兩半，各自 solve\n    把兩半的答案合併",
    "segment-tree": "每個節點管一段區間，存那段的總和或最大值\n修改：從葉子往上更新\n查詢：把查詢區間拆成 O(log n) 段節點",
    "enumeration": "先估算：全部列舉要幾種情況？夠小就直接列舉\n對每種情況檢查是否符合條件、更新答案",
}

GENERIC = ("先寫出最直接的暴力解，確認自己懂題目\n找出暴力解裡重複做的事\n"
           "想想哪種資料結構能把那件事變快（雜湊表、排序、堆疊、前綴和…）")

_FREQ: Counter = Counter()


def set_problems(problems):
    _FREQ.clear()
    for p in problems:
        _FREQ.update(p.get("tags", []))


def primary_tag(tags) -> str | None:
    """主要技能：有教學內容的標籤裡，最少見的那個（越少見越有資訊量）。"""
    cands = [t for t in tags if t in SKELETONS or t in engine.CONCEPTS]
    if not cands:
        return None
    return min(cands, key=lambda t: (_FREQ.get(t, 0), tags.index(t)))


def ladder(problem: dict, names: dict, upto: int) -> list[dict]:
    """回傳第 1～upto 階的提示內容。names 是標籤 → 技能名稱。"""
    tags = problem.get("tags", [])
    main = primary_tag(tags)
    out = []
    if upto >= 1:
        if tags:
            out.append({"level": 1, "title": "相關技能",
                        "text": "、".join(names.get(t, t) for t in tags), "tags": tags})
        else:
            out.append({"level": 1, "title": "相關技能", "text": "這題沒有標籤，先從暴力解想起。", "tags": []})
    if upto >= 2:
        if main:
            idea = engine.CONCEPTS.get(main) or "這個技能的核心是把重複的工作省下來。"
            out.append({"level": 2, "title": f"核心觀念：{names.get(main, main)}", "text": idea, "tag": main})
        else:
            out.append({"level": 2, "title": "核心觀念", "text": "先把題目的限制看清楚：資料量多大？要求的複雜度大概是多少？"})
    if upto >= 3:
        out.append({"level": 3, "title": f"虛擬碼骨架：{names.get(main, main)}" if main else "虛擬碼骨架",
                    "text": SKELETONS.get(main, GENERIC), "pseudo": True})
    return out
