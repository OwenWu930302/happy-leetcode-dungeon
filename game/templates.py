"""模板庫：每個技能一份 Python 與 C++ 模板，點亮技能節點後解鎖。

全部是這個專案自己寫的通用寫法（MIT 授權），可以一鍵插入到解題檔。
tests/test_templates.py 會確認每份 C++ 都能編譯、每份 Python 都能執行。
"""

TEMPLATES = {
    "binary-search": {
        "title": "對答案二分（找第一個成立的值）",
        "python": '''def first_true(lo, hi, ok):
    """在 [lo, hi] 找第一個讓 ok(x) 成立的 x；ok 必須是「先假後真」。"""
    while lo < hi:
        mid = (lo + hi) // 2
        if ok(mid):
            hi = mid
        else:
            lo = mid + 1
    return lo
''',
        "cpp": '''// 在 [lo, hi] 找第一個讓 ok(x) 成立的 x；ok 必須是「先假後真」
template <class F>
long long first_true(long long lo, long long hi, F ok) {
    while (lo < hi) {
        long long mid = lo + (hi - lo) / 2;
        if (ok(mid)) hi = mid;
        else lo = mid + 1;
    }
    return lo;
}
''',
    },
    "two-pointers": {
        "title": "左右夾擊（排序後找兩數和）",
        "python": '''def pair_with_sum(a, target):
    """a 已排序，回傳一組相加等於 target 的索引，找不到回傳 None。"""
    l, r = 0, len(a) - 1
    while l < r:
        s = a[l] + a[r]
        if s == target:
            return l, r
        if s < target:
            l += 1
        else:
            r -= 1
    return None
''',
        "cpp": '''// a 已排序，回傳一組相加等於 target 的索引，找不到回傳 {-1, -1}
pair<int, int> pair_with_sum(const vector<int>& a, long long target) {
    int l = 0, r = (int)a.size() - 1;
    while (l < r) {
        long long s = (long long)a[l] + a[r];
        if (s == target) return {l, r};
        if (s < target) l++;
        else r--;
    }
    return {-1, -1};
}
''',
    },
    "sliding-window": {
        "title": "可變長度視窗（最長的合法區間）",
        "python": '''from collections import Counter


def longest_window(s, k):
    """最多包含 k 種不同字元的最長子字串長度。把條件換成你的題目即可。"""
    cnt = Counter()
    best = l = 0
    for r, ch in enumerate(s):
        cnt[ch] += 1
        while len(cnt) > k:          # 視窗不合法：從左邊收縮
            cnt[s[l]] -= 1
            if cnt[s[l]] == 0:
                del cnt[s[l]]
            l += 1
        best = max(best, r - l + 1)
    return best
''',
        "cpp": '''// 最多包含 k 種不同字元的最長子字串長度。把條件換成你的題目即可。
int longest_window(const string& s, int k) {
    unordered_map<char, int> cnt;
    int best = 0, l = 0;
    for (int r = 0; r < (int)s.size(); r++) {
        cnt[s[r]]++;
        while ((int)cnt.size() > k) {   // 視窗不合法：從左邊收縮
            if (--cnt[s[l]] == 0) cnt.erase(s[l]);
            l++;
        }
        best = max(best, r - l + 1);
    }
    return best;
}
''',
    },
    "prefix-sum": {
        "title": "前綴和＋字典（和為 k 的子陣列個數）",
        "python": '''from collections import defaultdict


def count_subarrays(a, k):
    seen = defaultdict(int)
    seen[0] = 1
    total = ans = 0
    for x in a:
        total += x
        ans += seen[total - k]       # 之前有幾個前綴和 = total - k
        seen[total] += 1
    return ans
''',
        "cpp": '''long long count_subarrays(const vector<int>& a, long long k) {
    unordered_map<long long, int> seen{{0, 1}};
    long long total = 0, ans = 0;
    for (int x : a) {
        total += x;
        auto it = seen.find(total - k);   // 之前有幾個前綴和 = total - k
        if (it != seen.end()) ans += it->second;
        seen[total]++;
    }
    return ans;
}
''',
    },
    "monotonic-stack": {
        "title": "單調堆疊（每個元素的下一個更大）",
        "python": '''def next_greater(a):
    """res[i] = a[i] 右邊第一個更大的值，沒有就是 -1。"""
    res = [-1] * len(a)
    st = []                          # 存索引，對應的值由底到頂遞減
    for i, x in enumerate(a):
        while st and a[st[-1]] < x:
            res[st.pop()] = x
        st.append(i)
    return res
''',
        "cpp": '''// res[i] = a[i] 右邊第一個更大的值，沒有就是 -1
vector<int> next_greater(const vector<int>& a) {
    vector<int> res(a.size(), -1), st;   // st 存索引，對應的值由底到頂遞減
    for (int i = 0; i < (int)a.size(); i++) {
        while (!st.empty() && a[st.back()] < a[i]) {
            res[st.back()] = a[i];
            st.pop_back();
        }
        st.push_back(i);
    }
    return res;
}
''',
    },
    "stack": {
        "title": "堆疊配對（括號是否合法）",
        "python": '''def balanced(s):
    pair = {")": "(", "]": "[", "}": "{"}
    st = []
    for ch in s:
        if ch in pair:
            if not st or st.pop() != pair[ch]:
                return False
        else:
            st.append(ch)
    return not st
''',
        "cpp": '''bool balanced(const string& s) {
    vector<char> st;
    for (char ch : s) {
        if (ch == '(' || ch == '[' || ch == '{') { st.push_back(ch); continue; }
        char want = ch == ')' ? '(' : ch == ']' ? '[' : '{';
        if (st.empty() || st.back() != want) return false;
        st.pop_back();
    }
    return st.empty();
}
''',
    },
    "breadth-first-search": {
        "title": "網格 BFS（最少步數）",
        "python": '''from collections import deque


def min_steps(grid, start, goal):
    """grid 裡 0 可以走、1 是牆。回傳 start 到 goal 的最少步數，到不了回傳 -1。"""
    R, C = len(grid), len(grid[0])
    q = deque([start])
    dist = {start: 0}
    while q:
        r, c = q.popleft()
        if (r, c) == goal:
            return dist[(r, c)]
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < R and 0 <= nc < C and grid[nr][nc] == 0 and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    return -1
''',
        "cpp": '''// grid 裡 0 可以走、1 是牆。回傳 (sr,sc) 到 (gr,gc) 的最少步數，到不了回傳 -1
int min_steps(const vector<vector<int>>& grid, int sr, int sc, int gr, int gc) {
    int R = grid.size(), C = grid[0].size();
    vector<vector<int>> dist(R, vector<int>(C, -1));
    queue<pair<int, int>> q;
    q.push({sr, sc});
    dist[sr][sc] = 0;
    int dr[] = {1, -1, 0, 0}, dc[] = {0, 0, 1, -1};
    while (!q.empty()) {
        auto [r, c] = q.front(); q.pop();
        if (r == gr && c == gc) return dist[r][c];
        for (int d = 0; d < 4; d++) {
            int nr = r + dr[d], nc = c + dc[d];
            if (nr < 0 || nr >= R || nc < 0 || nc >= C || grid[nr][nc] || dist[nr][nc] != -1) continue;
            dist[nr][nc] = dist[r][c] + 1;
            q.push({nr, nc});
        }
    }
    return -1;
}
''',
    },
    "depth-first-search": {
        "title": "網格 DFS（數連通區塊）",
        "python": '''def count_islands(grid):
    """grid 是 '1'／'0' 的二維陣列，回傳 '1' 組成的連通區塊數。"""
    R, C = len(grid), len(grid[0])
    seen = [[False] * C for _ in range(R)]

    def dfs(r, c):
        stack = [(r, c)]               # 用自己的堆疊，避免遞迴太深
        seen[r][c] = True
        while stack:
            r, c = stack.pop()
            for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= nr < R and 0 <= nc < C and grid[nr][nc] == "1" and not seen[nr][nc]:
                    seen[nr][nc] = True
                    stack.append((nr, nc))

    count = 0
    for r in range(R):
        for c in range(C):
            if grid[r][c] == "1" and not seen[r][c]:
                dfs(r, c)
                count += 1
    return count
''',
        "cpp": '''// grid 是 '1'／'0' 的二維陣列，回傳 '1' 組成的連通區塊數
int count_islands(vector<vector<char>> grid) {
    int R = grid.size(), C = grid[0].size(), count = 0;
    function<void(int, int)> dfs = [&](int r, int c) {
        if (r < 0 || r >= R || c < 0 || c >= C || grid[r][c] != '1') return;
        grid[r][c] = '#';                 // 標記走過
        dfs(r + 1, c); dfs(r - 1, c); dfs(r, c + 1); dfs(r, c - 1);
    };
    for (int r = 0; r < R; r++)
        for (int c = 0; c < C; c++)
            if (grid[r][c] == '1') { dfs(r, c); count++; }
    return count;
}
''',
    },
    "backtracking": {
        "title": "回溯（列出所有組合）",
        "python": '''def combinations_of(nums, k):
    """從 nums 選 k 個的所有組合。"""
    res, path = [], []

    def bt(start):
        if len(path) == k:
            res.append(path[:])      # 存副本
            return
        for i in range(start, len(nums)):
            path.append(nums[i])     # 做選擇
            bt(i + 1)
            path.pop()               # 撤銷選擇

    bt(0)
    return res
''',
        "cpp": '''// 從 nums 選 k 個的所有組合
vector<vector<int>> combinations_of(const vector<int>& nums, int k) {
    vector<vector<int>> res;
    vector<int> path;
    function<void(int)> bt = [&](int start) {
        if ((int)path.size() == k) { res.push_back(path); return; }
        for (int i = start; i < (int)nums.size(); i++) {
            path.push_back(nums[i]);    // 做選擇
            bt(i + 1);
            path.pop_back();            // 撤銷選擇
        }
    };
    bt(0);
    return res;
}
''',
    },
    "dynamic-programming": {
        "title": "0/1 背包（一維 dp）",
        "python": '''def knapsack(weights, values, cap):
    """每件物品最多拿一次，容量 cap 下的最大價值。"""
    dp = [0] * (cap + 1)
    for w, v in zip(weights, values):
        for c in range(cap, w - 1, -1):    # 倒著走，每件只用一次
            dp[c] = max(dp[c], dp[c - w] + v)
    return dp[cap]
''',
        "cpp": '''// 每件物品最多拿一次，容量 cap 下的最大價值
long long knapsack(const vector<int>& w, const vector<int>& v, int cap) {
    vector<long long> dp(cap + 1, 0);
    for (size_t i = 0; i < w.size(); i++)
        for (int c = cap; c >= w[i]; c--)   // 倒著走，每件只用一次
            dp[c] = max(dp[c], dp[c - w[i]] + v[i]);
    return dp[cap];
}
''',
    },
    "heap-priority-queue": {
        "title": "堆積（前 k 大）",
        "python": '''import heapq


def top_k(nums, k):
    """回傳最大的 k 個數（由大到小）。堆積大小維持在 k。"""
    h = []
    for x in nums:
        heapq.heappush(h, x)
        if len(h) > k:
            heapq.heappop(h)         # 丟掉最小的
    return sorted(h, reverse=True)
''',
        "cpp": '''// 回傳最大的 k 個數（由大到小）。堆積大小維持在 k
vector<int> top_k(const vector<int>& nums, int k) {
    priority_queue<int, vector<int>, greater<int>> h;   // 最小堆積
    for (int x : nums) {
        h.push(x);
        if ((int)h.size() > k) h.pop();                 // 丟掉最小的
    }
    vector<int> res;
    while (!h.empty()) { res.push_back(h.top()); h.pop(); }
    reverse(res.begin(), res.end());
    return res;
}
''',
    },
    "union-find": {
        "title": "並查集（路徑壓縮＋按大小合併）",
        "python": '''class DSU:
    def __init__(self, n):
        self.parent = list(range(n))
        self.size = [1] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]   # 路徑壓縮
            x = self.parent[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a == b:
            return False
        if self.size[a] < self.size[b]:
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        return True
''',
        "cpp": '''struct DSU {
    vector<int> parent, sz;
    explicit DSU(int n) : parent(n), sz(n, 1) { iota(parent.begin(), parent.end(), 0); }
    int find(int x) {
        while (parent[x] != x) x = parent[x] = parent[parent[x]];   // 路徑壓縮
        return x;
    }
    bool unite(int a, int b) {
        a = find(a); b = find(b);
        if (a == b) return false;
        if (sz[a] < sz[b]) swap(a, b);
        parent[b] = a;
        sz[a] += sz[b];
        return true;
    }
};
''',
    },
    "trie": {
        "title": "字典樹（插入與前綴查詢）",
        "python": '''class Trie:
    def __init__(self):
        self.root = {}

    def insert(self, word):
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node["$"] = True                  # 單字結尾

    def _walk(self, s):
        node = self.root
        for ch in s:
            if ch not in node:
                return None
            node = node[ch]
        return node

    def search(self, word):
        node = self._walk(word)
        return node is not None and "$" in node

    def starts_with(self, prefix):
        return self._walk(prefix) is not None
''',
        "cpp": '''struct Trie {
    struct Node { array<int, 26> next; bool end = false; Node() { next.fill(-1); } };
    vector<Node> t{Node()};
    void insert(const string& w) {
        int u = 0;
        for (char ch : w) {
            int c = ch - 'a';
            if (t[u].next[c] == -1) { t[u].next[c] = t.size(); t.emplace_back(); }
            u = t[u].next[c];
        }
        t[u].end = true;
    }
    int walk(const string& s) const {
        int u = 0;
        for (char ch : s) { u = t[u].next[ch - 'a']; if (u == -1) return -1; }
        return u;
    }
    bool search(const string& w) const { int u = walk(w); return u != -1 && t[u].end; }
    bool startsWith(const string& p) const { return walk(p) != -1; }
};
''',
    },
    "linked-list": {
        "title": "反轉鏈結串列＋虛擬頭節點",
        "python": '''def reverse_list(head):
    prev = None
    while head:
        nxt = head.next          # 先存好下一個
        head.next = prev
        prev, head = head, nxt
    return prev


def remove_value(head, val):
    dummy = ListNode(0, head)    # 虛擬頭節點：刪掉第一個也不用特判
    cur = dummy
    while cur.next:
        if cur.next.val == val:
            cur.next = cur.next.next
        else:
            cur = cur.next
    return dummy.next
''',
        "cpp": '''ListNode* reverse_list(ListNode* head) {
    ListNode* prev = nullptr;
    while (head) {
        ListNode* nxt = head->next;   // 先存好下一個
        head->next = prev;
        prev = head;
        head = nxt;
    }
    return prev;
}

ListNode* remove_value(ListNode* head, int val) {
    ListNode dummy(0, head);          // 虛擬頭節點：刪掉第一個也不用特判
    ListNode* cur = &dummy;
    while (cur->next) {
        if (cur->next->val == val) cur->next = cur->next->next;
        else cur = cur->next;
    }
    return dummy.next;
}
''',
    },
    "binary-tree": {
        "title": "層序走訪（一層一層處理）",
        "python": '''from collections import deque


def level_order(root):
    if not root:
        return []
    res, q = [], deque([root])
    while q:
        level = []
        for _ in range(len(q)):          # 只處理這一層
            node = q.popleft()
            level.append(node.val)
            if node.left:
                q.append(node.left)
            if node.right:
                q.append(node.right)
        res.append(level)
    return res
''',
        "cpp": '''vector<vector<int>> level_order(TreeNode* root) {
    vector<vector<int>> res;
    if (!root) return res;
    queue<TreeNode*> q;
    q.push(root);
    while (!q.empty()) {
        vector<int> level;
        for (int n = q.size(); n > 0; n--) {   // 只處理這一層
            TreeNode* node = q.front(); q.pop();
            level.push_back(node->val);
            if (node->left) q.push(node->left);
            if (node->right) q.push(node->right);
        }
        res.push_back(level);
    }
    return res;
}
''',
    },
    "binary-search-tree": {
        "title": "迭代中序走訪（得到排序好的序列）",
        "python": '''def inorder(root):
    res, st, node = [], [], root
    while st or node:
        while node:                  # 一路往左
            st.append(node)
            node = node.left
        node = st.pop()
        res.append(node.val)
        node = node.right
    return res
''',
        "cpp": '''vector<int> inorder(TreeNode* root) {
    vector<int> res;
    vector<TreeNode*> st;
    TreeNode* node = root;
    while (!st.empty() || node) {
        while (node) { st.push_back(node); node = node->left; }   // 一路往左
        node = st.back(); st.pop_back();
        res.push_back(node->val);
        node = node->right;
    }
    return res;
}
''',
    },
    "shortest-path": {
        "title": "Dijkstra 最短路徑",
        "python": '''import heapq


def dijkstra(n, edges, src):
    """edges = [(u, v, w), ...]（有向、w ≥ 0）。回傳 src 到每個點的距離，到不了是 inf。"""
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [float("inf")] * n
    dist[src] = 0
    h = [(0, src)]
    while h:
        d, u = heapq.heappop(h)
        if d > dist[u]:
            continue                 # 過期的紀錄
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(h, (dist[v], v))
    return dist
''',
        "cpp": '''// edges = {u, v, w}（有向、w ≥ 0）。回傳 src 到每個點的距離，到不了是 LLONG_MAX
vector<long long> dijkstra(int n, const vector<array<int, 3>>& edges, int src) {
    vector<vector<pair<int, int>>> adj(n);
    for (auto& e : edges) adj[e[0]].push_back({e[1], e[2]});
    vector<long long> dist(n, LLONG_MAX);
    priority_queue<pair<long long, int>, vector<pair<long long, int>>, greater<>> h;
    dist[src] = 0;
    h.push({0, src});
    while (!h.empty()) {
        auto [d, u] = h.top(); h.pop();
        if (d > dist[u]) continue;          // 過期的紀錄
        for (auto [v, w] : adj[u])
            if (d + w < dist[v]) { dist[v] = d + w; h.push({dist[v], v}); }
    }
    return dist;
}
''',
    },
    "topological-sort": {
        "title": "Kahn 拓撲排序（順便判斷有沒有環）",
        "python": '''from collections import deque


def topo_order(n, edges):
    """edges = [(u, v)] 表示 u 要在 v 之前。有環就回傳空陣列。"""
    adj = [[] for _ in range(n)]
    indeg = [0] * n
    for u, v in edges:
        adj[u].append(v)
        indeg[v] += 1
    q = deque(i for i in range(n) if indeg[i] == 0)
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return order if len(order) == n else []
''',
        "cpp": '''// edges = {u, v} 表示 u 要在 v 之前。有環就回傳空陣列
vector<int> topo_order(int n, const vector<pair<int, int>>& edges) {
    vector<vector<int>> adj(n);
    vector<int> indeg(n, 0), order;
    for (auto [u, v] : edges) { adj[u].push_back(v); indeg[v]++; }
    queue<int> q;
    for (int i = 0; i < n; i++) if (!indeg[i]) q.push(i);
    while (!q.empty()) {
        int u = q.front(); q.pop();
        order.push_back(u);
        for (int v : adj[u]) if (--indeg[v] == 0) q.push(v);
    }
    if ((int)order.size() != n) order.clear();
    return order;
}
''',
    },
    "graph": {
        "title": "建鄰接表＋數連通塊",
        "python": '''def components(n, edges):
    """無向圖的連通塊數量。"""
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    seen = [False] * n
    count = 0
    for s in range(n):
        if seen[s]:
            continue
        count += 1
        seen[s] = True
        stack = [s]
        while stack:
            u = stack.pop()
            for v in adj[u]:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
    return count
''',
        "cpp": '''// 無向圖的連通塊數量
int components(int n, const vector<pair<int, int>>& edges) {
    vector<vector<int>> adj(n);
    for (auto [u, v] : edges) { adj[u].push_back(v); adj[v].push_back(u); }
    vector<bool> seen(n, false);
    int count = 0;
    for (int s = 0; s < n; s++) {
        if (seen[s]) continue;
        count++;
        seen[s] = true;
        vector<int> st{s};
        while (!st.empty()) {
            int u = st.back(); st.pop_back();
            for (int v : adj[u]) if (!seen[v]) { seen[v] = true; st.push_back(v); }
        }
    }
    return count;
}
''',
    },
    "bit-manipulation": {
        "title": "位元技巧（數 1、列舉子集）",
        "python": '''def popcount(x):
    count = 0
    while x:
        x &= x - 1               # 去掉最低的 1
        count += 1
    return count


def all_subsets(items):
    n = len(items)
    return [[items[i] for i in range(n) if mask >> i & 1] for mask in range(1 << n)]
''',
        "cpp": '''int popcount_of(unsigned x) {
    int count = 0;
    while (x) { x &= x - 1; count++; }   // 去掉最低的 1
    return count;
}

vector<vector<int>> all_subsets(const vector<int>& items) {
    int n = items.size();
    vector<vector<int>> res;
    for (int mask = 0; mask < (1 << n); mask++) {
        vector<int> sub;
        for (int i = 0; i < n; i++) if (mask >> i & 1) sub.push_back(items[i]);
        res.push_back(sub);
    }
    return res;
}
''',
    },
    "math": {
        "title": "快速冪、質數篩",
        "python": '''MOD = 10**9 + 7


def power_mod(a, e, m=MOD):
    """a^e mod m（Python 也可以直接用 pow(a, e, m)）。"""
    result = 1
    a %= m
    while e:
        if e & 1:
            result = result * a % m
        a = a * a % m
        e >>= 1
    return result


def primes_up_to(n):
    is_p = [True] * (n + 1)
    is_p[0:2] = [False, False]
    for i in range(2, int(n ** 0.5) + 1):
        if is_p[i]:
            is_p[i * i::i] = [False] * len(is_p[i * i::i])
    return [i for i, ok in enumerate(is_p) if ok]
''',
        "cpp": '''const long long MOD = 1'000'000'007;

long long power_mod(long long a, long long e, long long m = MOD) {
    long long result = 1;
    a %= m;
    while (e) {
        if (e & 1) result = result * a % m;
        a = a * a % m;
        e >>= 1;
    }
    return result;
}

vector<int> primes_up_to(int n) {
    vector<bool> is_p(n + 1, true);
    vector<int> res;
    for (int i = 2; i <= n; i++) {
        if (!is_p[i]) continue;
        res.push_back(i);
        for (long long j = (long long)i * i; j <= n; j += i) is_p[j] = false;
    }
    return res;
}
''',
    },
    "hash-table": {
        "title": "計數與分組（Counter／依 key 分組）",
        "python": '''from collections import Counter, defaultdict


def most_common(items, k=1):
    """出現最多次的 k 個東西。"""
    return [x for x, _ in Counter(items).most_common(k)]


def group_by(items, key):
    """依 key(x) 分組，例如 key=lambda w: "".join(sorted(w)) 可以把字母組成相同的字分在一起。"""
    groups = defaultdict(list)
    for x in items:
        groups[key(x)].append(x)
    return list(groups.values())
''',
        "cpp": '''// 出現最多次的元素（平手時回傳先出現的那個）
int most_common(const vector<int>& items) {
    unordered_map<int, int> cnt;
    int best = items.empty() ? 0 : items[0], top = 0;
    for (int x : items)
        if (++cnt[x] > top) { top = cnt[x]; best = x; }
    return best;
}

// 依 key 分組，例如把字母組成相同的字分在一起：key = 排序後的字
vector<vector<string>> group_by_sorted(const vector<string>& words) {
    unordered_map<string, vector<string>> groups;
    for (const string& w : words) {
        string k = w;
        sort(k.begin(), k.end());
        groups[k].push_back(w);
    }
    vector<vector<string>> res;
    for (auto& [k, g] : groups) res.push_back(g);
    return res;
}
''',
    },
    "greedy": {
        "title": "區間排程（按結束時間排序）",
        "python": '''def max_non_overlapping(intervals):
    """最多能選幾個互不重疊的區間 [start, end)。"""
    count, end = 0, float("-inf")
    for s, e in sorted(intervals, key=lambda iv: iv[1]):
        if s >= end:                 # 最早結束的先拿
            count += 1
            end = e
    return count
''',
        "cpp": '''// 最多能選幾個互不重疊的區間 [start, end)
int max_non_overlapping(vector<vector<int>> iv) {
    sort(iv.begin(), iv.end(), [](const auto& a, const auto& b) { return a[1] < b[1]; });
    int count = 0;
    long long end = LLONG_MIN;
    for (auto& x : iv)
        if (x[0] >= end) { count++; end = x[1]; }   // 最早結束的先拿
    return count;
}
''',
    },
    "sorting": {
        "title": "自訂排序（多個條件）",
        "python": '''def sort_people(people):
    """people = [(名字, 年齡)]：年齡由大到小，同齡依名字字母順序。"""
    return sorted(people, key=lambda p: (-p[1], p[0]))
''',
        "cpp": '''// people = {名字, 年齡}：年齡由大到小，同齡依名字字母順序
void sort_people(vector<pair<string, int>>& people) {
    sort(people.begin(), people.end(), [](const auto& a, const auto& b) {
        if (a.second != b.second) return a.second > b.second;
        return a.first < b.first;
    });
}
''',
    },
    "binary-indexed-tree": {
        "title": "樹狀陣列（單點修改、前綴和查詢）",
        "python": '''class Fenwick:
    def __init__(self, n):
        self.t = [0] * (n + 1)

    def add(self, i, delta):         # i 從 0 開始
        i += 1
        while i < len(self.t):
            self.t[i] += delta
            i += i & -i

    def prefix(self, i):             # a[0] + ... + a[i - 1]
        s = 0
        while i > 0:
            s += self.t[i]
            i -= i & -i
        return s

    def range_sum(self, l, r):       # a[l] + ... + a[r]
        return self.prefix(r + 1) - self.prefix(l)
''',
        "cpp": '''struct Fenwick {
    vector<long long> t;
    explicit Fenwick(int n) : t(n + 1, 0) {}
    void add(int i, long long delta) { for (i++; i < (int)t.size(); i += i & -i) t[i] += delta; }
    long long prefix(int i) const { long long s = 0; for (; i > 0; i -= i & -i) s += t[i]; return s; }   // a[0..i-1]
    long long range_sum(int l, int r) const { return prefix(r + 1) - prefix(l); }                       // a[l..r]
};
''',
    },
    "string-matching": {
        "title": "KMP（找出所有出現位置）",
        "python": '''def find_all(text, pat):
    """pat 在 text 裡所有出現的起點。"""
    if not pat:
        return list(range(len(text) + 1))
    fail = [0] * len(pat)            # 最長相同前後綴
    k = 0
    for i in range(1, len(pat)):
        while k and pat[i] != pat[k]:
            k = fail[k - 1]
        if pat[i] == pat[k]:
            k += 1
        fail[i] = k
    res, k = [], 0
    for i, ch in enumerate(text):
        while k and ch != pat[k]:
            k = fail[k - 1]
        if ch == pat[k]:
            k += 1
        if k == len(pat):
            res.append(i - k + 1)
            k = fail[k - 1]
    return res
''',
        "cpp": '''// pat 在 text 裡所有出現的起點
vector<int> find_all(const string& text, const string& pat) {
    vector<int> res;
    if (pat.empty()) return res;
    vector<int> fail(pat.size(), 0);    // 最長相同前後綴
    for (size_t i = 1, k = 0; i < pat.size(); i++) {
        while (k && pat[i] != pat[k]) k = fail[k - 1];
        if (pat[i] == pat[k]) k++;
        fail[i] = k;
    }
    for (size_t i = 0, k = 0; i < text.size(); i++) {
        while (k && text[i] != pat[k]) k = fail[k - 1];
        if (text[i] == pat[k]) k++;
        if (k == pat.size()) { res.push_back(i - k + 1); k = fail[k - 1]; }
    }
    return res;
}
''',
    },
}

# 標籤別名：這些標籤沿用另一個標籤的模板
ALIASES = {"tree": "binary-tree", "queue": "breadth-first-search", "matrix": "breadth-first-search",
           "counting": "hash-table", "memoization": "dynamic-programming", "segment-tree": "binary-indexed-tree",
           "array": "two-pointers", "string": "sliding-window", "number-theory": "math",
           "recursion": "backtracking", "heap": "heap-priority-queue"}


def for_tag(tag):
    return TEMPLATES.get(tag) or TEMPLATES.get(ALIASES.get(tag, ""))


def listing(tree_nodes, lang):
    """回傳所有模板：哪些已解鎖（對應的技能節點已點亮）、哪些還鎖著。"""
    lit = {n["id"] for n in tree_nodes if n.get("lit")}
    names = {n["id"]: n["name"] for n in tree_nodes}
    unlocked_by = {}
    for tag in lit:
        key = tag if tag in TEMPLATES else ALIASES.get(tag)
        if key in TEMPLATES:
            unlocked_by.setdefault(key, tag)
    out = []
    for key, t in TEMPLATES.items():
        via = unlocked_by.get(key)
        item = {"id": key, "title": t["title"], "skill": names.get(key) or names.get(via) or key,
                "tags": [key] + [a for a, k in ALIASES.items() if k == key],
                "unlocked": via is not None, "via": names.get(via) if via else None,
                "present": key in names or any(ALIASES.get(n) == key for n in names)}
        if via is not None:
            use_cpp = lang == "cpp"
            item["code"] = t["cpp"] if use_cpp else t["python"]
            item["lang"] = "cpp" if use_cpp else "python3"
        out.append(item)
    out.sort(key=lambda x: (not x["unlocked"], not x["present"], x["skill"]))
    return out
