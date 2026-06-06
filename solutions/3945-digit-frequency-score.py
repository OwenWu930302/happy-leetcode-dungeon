# 3945. Digit Frequency Score  [Easy]
# https://leetcode.com/problems/digit-frequency-score/
#
# meta-slug: digit-frequency-score
# meta-qid: 4321
# meta-lang: python3
#
# 提示：可先用 `python lc.py show 3945` 看完整題目。
# 寫完後用 `python lc.py test 3945` 試跑、`python lc.py submit 3945` 提交。
# === 以下是你的程式碼 (YOUR CODE BELOW) ===
class Solution:
    def digitFrequencyScore(self, n: int) -> int:
        count = [0] * 10
        for c in str(n):
            count[int(c)] += 1
        return sum(c * f for c, f in enumerate(count))