LeetCode 地城登入小幫手（瀏覽器擴充功能）

安裝（只要一次）：
1. Chrome 打開 chrome://extensions，Edge 打開 edge://extensions
2. 打開右上角（Edge 在左下）的「開發人員模式」
3. 按「載入未封裝項目」，選這個資料夾
4. 在這個瀏覽器登入 leetcode.com（已經登入的話，重新整理一次 LeetCode 頁面）

之後只要遊戲開著、你在這個瀏覽器登入過 LeetCode，遊戲就會自動登入；
登入過期、換帳號時也會自動更新。工具列圖示上的 ✓ 代表已同步，按一下圖示可以立刻再同步一次。

它只讀 leetcode.com 的兩個登入 cookie（LEETCODE_SESSION、csrftoken），只送到你電腦上的遊戲（127.0.0.1），
不會讀你的密碼，也不會連到其他網站。
