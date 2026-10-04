Saber-Translator 日漫→繁體中文（台灣／香港）・CPU 免安裝版
==========================================================

把所有分卷解壓到同一資料夾後直接使用，不需要安裝 Python、不需要下載模型。

【開始使用】
1. 把整個資料夾放在可寫入的位置，建議 C:\ST\Saber-Translator
   （不要放在 C:\Program Files，設定和翻譯資料會存在程式旁邊的 data-v2 資料夾）。
2. 雙擊 Saber-Translator.exe。
   第一次執行若出現「Windows 已保護您的電腦」，按「其他資訊」→「仍要執行」
   （程式沒有付費數位簽章，屬正常現象）。
3. 到「設定 → 翻译服务」貼上 DeepSeek API Key（https://platform.deepseek.com 申請、儲值）。
   服務與模型已預設為 DeepSeek / deepseek-chat，不用再改。
4. 匯入漫畫圖片，開始翻譯。

【已經是最佳預設】
- 譯文 100% 繁體（台灣用字）、標點「」『』全形。
- 字型自動使用 Windows 內建「微軟正黑體 粗體」。
- 文字顏色、字號自動與原圖一致；所有氣泡（包括語氣詞、擬音）都會翻譯。
- 去字使用 LaMA（漫畫）模型，白色氣泡快速填平，殘留小點自動清除。
- 小圖匯入時自動放大 2 倍，譯文字更清晰；譯文在氣泡內置中。
- 直排漫畫裡的短句（あっ、♡）也排成直排，不會變成橫排；旁白等真正的橫排仍是橫排。
- 翻譯進行中，已完成的頁面就能編輯、使用修復／還原筆刷。
- 並行翻譯開啟、CPU 執行緒受限、桌面寵物關閉，筆電不會卡死。

【更新到新版（保留所有書籍與設定）】
以後有新版時，不用重新下載整個程式：
1. 雙擊本資料夾裡的「Update-Saber.bat」。
2. 第一次會要求貼上 GitHub「唯讀存取權杖」（倉庫是私人的才需要，只需一次）：
   GitHub 右上角頭像 → Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token；Repository access 選 Saber-Translator，
   Permissions → Contents 選 Read-only。權杖會存在 data-v2\github-token.txt。
3. 程式會自動檢查新版：通常只下載小型更新包；版本差太多時才下載完整分卷。
4. 更新只替換程式檔案，data-v2（書籍、翻譯結果、設定、API Key、術語表）完全不動。
不想用權杖：先在網頁下載 update.zip 或全部 part*.zip 到「下載」資料夾，
再雙擊 Update-Saber.bat，直接按 Enter 跳過權杖即可。

【改成香港用字】
在 Saber-Translator.exe 同一資料夾建立捷徑，目標改為：
  cmd /c "set SABER_ZH_HANT_REGION=hk && start "" Saber-Translator.exe"

【分卷說明】
本程式內附全部模型，因 GitHub 單一檔案上限 2GB 而分成數個 zip（part1、part2…）。
請下載全部分卷，並全部解壓到同一個資料夾（缺任何一個分卷，程式都可能無法正常執行）。
