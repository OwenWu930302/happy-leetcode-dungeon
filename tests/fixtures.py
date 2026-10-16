"""測試用的假題目：格式模仿 LeetCode 的題目資料，但內容是自己寫的，不含任何官方題目敘述。"""


def problem(slug, html, examples, snippets):
    return {
        "questionId": "9001", "questionFrontendId": "9001", "title": slug.replace("-", " ").title(),
        "titleSlug": slug, "difficulty": "Easy", "content": html, "exampleTestcases": examples,
        "codeSnippets": [{"lang": k, "langSlug": k, "code": v} for k, v in snippets.items()],
    }


PAIR_SUM = problem(
    "pair-sum",
    "<p>Find two positions whose values add up to the goal.</p>"
    "<pre><strong>Input:</strong> vals = [1,4,6], goal = 10\n<strong>Output:</strong> [1,2]</pre>"
    "<pre><strong>Input:</strong> vals = [5,5], goal = 10\n<strong>Output:</strong> [0,1]</pre>"
    "<p>You can return the answer in any order.</p>",
    "[1,4,6]\n10\n[5,5]\n10",
    {
        "python3": "class Solution:\n    def pairSum(self, vals: List[int], goal: int) -> List[int]:\n        ",
        "cpp": "class Solution {\npublic:\n    vector<int> pairSum(vector<int>& vals, int goal) {\n        \n    }\n};",
    },
)

SHOUT = problem(
    "shout",
    '<p>Uppercase a word.</p><p><strong>Input:</strong> <span class="example-io">w = "hey"</span></p>'
    '<p><strong>Output:</strong> <span class="example-io">"HEY"</span></p>',
    '"hey"',
    {
        "python3": "class Solution:\n    def shout(self, w: str) -> str:\n        ",
        "cpp": "class Solution {\npublic:\n    string shout(string w) {\n        \n    }\n};",
    },
)

COUNTER = problem(
    "tally-counter",
    "<p>Implement the <code>Tally</code> class.</p>"
    "<p><strong>Input:</strong></p><p>[&quot;Tally&quot;, &quot;add&quot;, &quot;add&quot;, &quot;total&quot;]</p>"
    "<p>[[5], [2], [3], []]</p><p><strong>Output:</strong> [null, null, null, 10]</p>",
    '["Tally","add","add","total"]\n[[5],[2],[3],[]]',
    {
        "python3": "class Tally:\n\n    def __init__(self, start: int):\n        \n\n    def add(self, x: int) -> None:\n        \n\n"
                   "    def total(self) -> int:\n        \n",
        "cpp": "class Tally {\npublic:\n    Tally(int start) {\n        \n    }\n    \n    void add(int x) {\n        \n    }\n    \n"
               "    int total() {\n        \n    }\n};",
    },
)

REVERSE_LIST = problem(
    "flip-chain",
    "<p>Reverse a linked list.</p><pre><strong>Input:</strong> head = [1,2,3]\n<strong>Output:</strong> [3,2,1]</pre>",
    "[1,2,3]",
    {
        "python3": "# Definition for singly-linked list.\n# class ListNode:\n#     def __init__(self, val=0, next=None):\n"
                   "#         self.val = val\n#         self.next = next\nclass Solution:\n"
                   "    def flipChain(self, head: Optional[ListNode]) -> Optional[ListNode]:\n        ",
        "cpp": "/**\n * struct ListNode { int val; ListNode *next; };\n */\nclass Solution {\npublic:\n"
               "    ListNode* flipChain(ListNode* head) {\n        \n    }\n};",
    },
)

TREE_DEPTH = problem(
    "tree-height",
    "<p>Height of a tree.</p><pre><strong>Input:</strong> root = [3,9,20,null,null,15,7]\n<strong>Output:</strong> 3</pre>",
    "[3,9,20,null,null,15,7]",
    {
        "python3": "class Solution:\n    def treeHeight(self, root: Optional[TreeNode]) -> int:\n        ",
        "cpp": "class Solution {\npublic:\n    int treeHeight(TreeNode* root) {\n        \n    }\n};",
    },
)

HIDDEN_ARG = problem(
    "loop-check",
    "<pre><strong>Input:</strong> head = [3,2,0], pos = 1\n<strong>Output:</strong> true</pre>",
    "[3,2,0]\n1",
    {"python3": "class Solution:\n    def hasLoop(self, head: Optional[ListNode]) -> bool:\n        "},
)

INTERACTIVE = problem(
    "first-bad",
    "<pre><strong>Input:</strong> n = 5, bad = 4\n<strong>Output:</strong> 4</pre>",
    "5\n4",
    {"python3": "# The isBadVersion API is already defined for you.\nclass Solution:\n    def firstBad(self, n: int) -> int:\n        "},
)
