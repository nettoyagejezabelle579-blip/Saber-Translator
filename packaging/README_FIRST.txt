Saber-Translator 日漫→繁體中文（台灣／香港）・CPU 免安裝版
==========================================================

解壓後直接使用，不需要安裝 Python、不需要下載模型。

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
- 文字顏色、字號自動與原圖一致；單獨的「あ」「うん」等語氣詞保留原文不翻。
- 去字使用 LaMA（漫畫）模型，白色氣泡快速填平。
- 並行翻譯開啟、CPU 執行緒受限，筆電不會卡死。

【改成香港用字】
在 Saber-Translator.exe 同一資料夾建立捷徑，目標改為：
  cmd /c "set SABER_ZH_HANT_REGION=hk && start "" Saber-Translator.exe"

【此版本未內附的選用模型】（為了讓下載檔小於 2GB）
- PaddleOCR-VL、CTD 偵測器、輔助 YOLO、litelama。預設設定都用不到。

詳細說明見同資料夾的 GALAXY_BOOK_ZH_HANT_GUIDE.md。
