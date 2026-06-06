# 2243. Calculate Digit Sum of a String  [Easy]
# https://leetcode.com/problems/calculate-digit-sum-of-a-string/
#
# meta-slug: calculate-digit-sum-of-a-string
# meta-qid: 2361
# meta-lang: python3
#
# 提示：可先用 `python lc.py show 2243` 看完整題目。
# 寫完後用 `python lc.py test 2243` 試跑、`python lc.py submit 2243` 提交。
# === 以下是你的程式碼 (YOUR CODE BELOW) ===

class Solution:
    def digitSum(self, s: str, k: int) -> str:
        while len(s)>k:
            string=""
            for i in range(0, len(s), k):
                group= s[i : i+k]
                string+=str(sum(int(c) for c in group))
            s=string
        return s
            