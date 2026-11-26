---
name: avatar-anim-video-zh
description: 大頭照動畫短影音：用自己的大頭照表情庫＋自己錄的旁白，照「抓內容＋選風格 → 做腳本 → 給產品照 → 給錄音檔（mp3／mp4）→ 含封面成片」五步，自動出設計感直式短片（柔霧、瑞士、拍立得、撕紙、講解卡片等風格；換表情、道具、音效、字幕不壓臉）並自查，看完說改哪裡就改。使用者說「大頭照動畫」「表情庫」「聲音庫」「表情包短影音」「大頭貼短影音」時使用。
---

# 大頭照動畫短影音

一個大頭照版的「你」當主角：講到哪句換哪個表情，旁邊跳出道具，鏡頭推拉，配上你自己錄的旁白、音效和字幕。預設設計感系列（柔霧／瑞士／拍立得／撕紙／講解卡片 10 款，人物在角落、字不壓臉），另有拼貼、高級 IG 風和活潑卡通風。直式 1080×1920、30fps，繁體中文。

**對使用者說話：** 一般人、不懂程式也看得懂。不要講欄位名、程式名，說「表情」「道具」「鏡頭」。一次只問一件事。

## 工作資料夾

在使用者指定的資料夾（沒指定就在目前資料夾建 `大頭照短影音/`）：

```
ip.md            我的 IP 定位（第 1 步）
faces/           表情庫（第 2 步，做一次共用）
voice/           只有用 AI 配音（備案）才會用到：voice.json、keys.env 金鑰
props/           自己的道具圖（可選）
素材/           照片、截圖、影片片段（可選，導演表 media 用）
videos/片名/     每支片：script.txt、director.json、錄音稿.txt、使用者的錄音、audio/、voice.wav、preview.mp4、final.mp4、check/
```

下面的 `scripts/` 指這個 skill 資料夾裡的 scripts（用完整路徑執行，工作目錄＝工作資料夾）。

## 流程（五步，照順序，一次只問一件事）

先跑 `python scripts/setup.py .` 檢查環境（Python、Pillow、numpy、ffmpeg）並建資料夾。`ip.md`、`faces/` 已經有就沿用，直接從第 1 步問「這支想拍什麼？」。

```
1 抓內容＋選風格 → 2 做腳本（確認）→ 3 請他給產品照／素材（第一次也做表情庫）→ 4 收錄音檔（mp3、mp4 都可以）→ 5 含封面成片 → 說改哪裡就改
```

### 1. 抓他想拍的內容 → 讀 `references/ip-script.md`
- 先問「這支想拍什麼？」，再一題一題補到寫得出三句：**誰會看**（觀眾、他們的卡點）、**看完得到什麼**、**看完要他做哪一個動作**（追蹤／留言／收藏／私訊…）
- 問有沒有要帶的**產品或服務**（名稱、是什麼、適合誰）；保健食品、保養品不寫功效（抗老、逆齡、瘦身、治療…），改成自己的使用習慣和感受
- **招募／事業片**（找夥伴、為什麼加入）：不保證收入、不寫「月入幾萬」「躺著賺」「財富自由」，改成說自己為什麼做、每天在做什麼、對方可以先怎麼了解。`direct.py lint` 會標出療效和收入字眼，有標就改寫
- 第一次用：順便把答案整理成 `ip.md`（我是誰、對誰說、說話口氣、風格），之後每支沿用
- **選風格（問完內容就問，一次只給 4 款）：** 給他 `assets/style-picker.jpg`（完整路徑，請他點開看；能附圖就直接附）（1 講解橘、2 講解藍、3 柔霧奶茶、4 拍立得），**依他要拍的內容推薦一款並說一句為什麼**（介紹產品、怎麼用、三個步驟 → 講解橘，**不確定就推這款**；事業分享、為什麼加入、找夥伴 → 講解藍；保養日常、生活分享 → 柔霧奶茶；開箱、使用心得、每日紀錄 → 拍立得）。他回編號就好；說「都可以」就用推薦的；想看更多才給 references/director.md 的完整風格表。告訴他：出片後還能換風格，腳本和錄音都不用重來。選好記進 `ip.md`，下一支先問「一樣用 X 嗎？」

### 2. 做腳本 → 讀 `references/script-library.md`
- 先寫「需要、想要、自己的目的」三句，挑模板（T01～T13），照 **HOOK → 內容 → CTA** 和 **起承轉合** 寫（小學生聽得懂、一句 8～20 字、20～45 秒），給 3 個不同型的 HOOK 讓他挑
- script.txt 用【起】【承】【轉】【合】分段，存 `videos/片名/script.txt`；照腳本庫的「交給使用者確認的格式」給他看
- **關卡：** 使用者確認腳本
- 確認後 Claude 自己做導演表（不用給使用者看表格，讀 `references/director.md`）：
  `python scripts/direct.py new videos/片名 --script videos/片名/script.txt --hook "開場大字" --sub "身分標籤 • EP01" --theme 他選的風格`，
  再逐句修表情／大字（big）／步驟標籤（banner）／道具，照「排表情原則」；`direct.py lint` 沒有 ✗
- 接著 `python scripts/voice.py sheet videos/片名/director.json` 做 `錄音稿.txt`，跟第 3 步一起交給他

### 3. 請他提供產品照和素材（＋第一次做表情庫）
- 照腳本建議 **2～3 個素材**：放第幾句、拍什麼或截什麼圖、怎麼拍（直式、自然光、背景乾淨）；最重要是**產品照**
- 收到就放 `素材/`，那句導演表加 `media`（card＝放在中間內容區，照片會自動裁成卡片大小）；沒有也可以先出片，之後補再重出
- **第一次用、還沒有表情庫** → 讀 `references/face-prompts.md`：給 ChatGPT 提示詞做 4×4 表情總表 → `python scripts/faces.py split 總表.png faces/` → `faces.py check faces/`，**用 Read 看 `faces/_總覽.jpg`** 給他確認。想先試：`faces.py demo faces/` 用示範角色
- 產品照上若印有功效字樣（例如英文 anti-aging），提醒他自己決定要不要換一張

### 4. 收錄音檔 → 讀 `references/voice.md`
- 請他照 `錄音稿.txt` 用手機錄整篇：每句停 1 秒，念錯停 2 秒從那句重念。**mp3、m4a、wav、mp4（手機錄影也行）都可以**，影片檔會自動只取聲音
- `python scripts/voice.py align videos/片名/director.json --audio 錄音檔`（本機語音辨識對句）；某句重錄：`voice.py redo … --line N --audio 檔案`
- 先檢查音量：整段沒聲音（例如 -60dB 以下）請他重傳
- 預設不用 AI 配音；他主動要才用備案（voice.md 後半）

### 5. 含封面成片＋自查
```bash
python scripts/render.py videos/片名/director.json             # 1080×1920 成品 final.mp4，同時做封面 cover.jpg（也塞進影片當縮圖）
python scripts/check.py  videos/片名/director.json             # 自查
python scripts/render.py videos/片名/director.json --cover     # 只重做封面
```
- 配樂：問要不要音樂；沒有自己的就 `python scripts/music.py make 輕快 --director …`（輕快、可愛、科技、溫馨、熱血）
- 自查有 ✗ 先自己修好重出，**用 Read 看 `check/總覽.jpg` 和 `cover.jpg`**：表情對不對、字有沒有壓到臉、有沒有進紅區（平台介面會蓋住）
- 交片：成片＋封面一起給，說長度和自查結果一句話；請他確認**聲音和字幕對得上**（Claude 聽不到）。上傳時封面選「從相簿選」用 cover.jpg
- 改稿時可以先出 `--preview`（540×960，快 4 倍）

### 6. 使用者說改哪裡 → 讀 `references/revise.md`
- 換風格：只改 `director.json` 的 `style.theme` 再 render，腳本和錄音都不用動
- 改 `director.json` → 改到台詞就請他重錄那句（`voice.py redo`）→ render → check
- 回覆：改了什麼（白話）＋新影片

## 規格與規則
- 直式 1080×1920、30fps、H.264＋AAC、音量 -14 LUFS（各平台通用）
- 安全區：上 250px、下 450px（y>1470）、右 120px 不放字和道具；字幕在 y≈1325、一行 ≤9 字、照語意斷句
- 開場 0.5 秒內出大字＋表情，前 3 秒靜音也看得懂
- 腳本一定有 HOOK＋內容＋CTA、起承轉合四段；CTA 只有一個動作；不編造數字、案例、期限
- 字型跟著風格走：設計感系列用思源宋體／黑體（罕用字自動改粉圓），其他風格用粉圓；不要自己另外換字
- 任何字（標題、大字、字幕、標籤）都不能壓到臉；設計感系列已自動避開，改版面時也要守這條
- 每句換表情，同表情不連續超過 2 句
- 只用使用者本人的聲音和照片；配樂要可商用

## 需要
Python 3.9+、Pillow、numpy、ffmpeg（`setup.py` 會檢查）。自己錄旁白不需要網路；AI 配音（備案）才需要網路與金鑰。全部在本機算圖，不用 GPU。

## 檔案
- `scripts/`：setup.py 環境、faces.py 表情庫、voice.py 旁白（自己錄對時間／AI 配音備案）、direct.py 導演表、render.py 出片、check.py 自查、music.py 內建配樂、asr_align.py 錄音對句（本機語音辨識）、sfx.py 音效合成、common.py 共用
- `assets/`：字型（粉圓 Huninn、思源宋體／黑體常用字版、DM Serif 英文斜體，全部 OFL）、68 個道具圖（Noto Emoji，Apache-2.0）、示範角色 demo_faces/
- `examples/demo/`：示範腳本與導演表
