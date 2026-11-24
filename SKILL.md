---
name: avatar-anim-video-zh
description: 大頭照動畫短影音：用自己的大頭照表情庫＋自己錄的旁白（AI 配音可選），從 IP 定位、寫腳本、導演表到自動出直式短片（換表情、道具、運鏡、音效、字幕）並自查，看完說改哪裡就改。使用者說「大頭照動畫」「表情庫」「聲音庫」「表情包短影音」「大頭貼短影音」時使用。
---

# 大頭照動畫短影音

一個卡通版的「你」當主角：講到哪句換哪個表情，旁邊跳出道具，鏡頭推拉震動，配上你自己錄的旁白、音效和大字幕。直式 1080×1920、30fps，繁體中文。

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

## 流程（六步，每步有關卡：使用者說 OK 才往下）

先跑 `python scripts/setup.py .` 檢查環境（Python、Pillow、numpy、ffmpeg）並建資料夾。看 `ip.md`、`faces/` 在不在，已經做過的步驟跳過，直接問「這次要拍什麼主題？」。

### 1. IP 定位＋腳本 → 讀 `references/ip-script.md`
- 第一次：聊天問 7 題做 `ip.md`
- 每支片：寫腳本（小學生聽得懂、一句 8～20 字、20～45 秒），給 3 個開頭讓他挑，存 `videos/片名/script.txt`
- **關卡：** 使用者確認腳本

### 2. 表情庫 → 讀 `references/face-prompts.md`
- 給他 ChatGPT 提示詞（先做角色，再做 4×4 表情總表），他下載圖片回來
- `python scripts/faces.py split 總表.png faces/` 切 16 張、去背；或單張 `faces.py cutout faces/ --same-box`
- `python scripts/faces.py check faces/`，**用 Read 看 `faces/_總覽.jpg`**，確認表情對、大小一致、沒有白邊
- 還沒做表情庫想先試：`faces.py demo faces/` 用內建示範角色
- **關卡：** 使用者看總覽圖說 OK

### 3. 導演表 → 讀 `references/director.md`
- `python scripts/direct.py new videos/片名 --script videos/片名/script.txt --hook "開場大字" --sub "身分標籤"` 產生初稿
- **Claude 逐句檢查、修改**表情／道具／運鏡／標籤／強調字（初稿只是關鍵字猜的），照 director.md 的「排表情原則」
- 使用者有素材（截圖、照片、影片）：放 `素材/`，那句加 `media`（card 卡片／full 全畫面）
- 配樂：問使用者要不要音樂；沒有自己的就 `python scripts/music.py make 輕快 --director …`（輕快、可愛、科技、溫馨、熱血）
- `python scripts/direct.py lint …/director.json` 沒有 ✗
- `python scripts/direct.py show …/director.json` → 把導演表（表格）給使用者看
- **關卡：** 使用者確認導演表（也可以說「直接出片我看了再改」）

### 4. 錄旁白 → 讀 `references/voice.md`
- **預設使用者自己錄，不用 AI 配音。** 產生 `錄音稿.txt`，照 voice.md 教他錄（每句停 1 秒，念錯停 2 秒從那句重念）
- 錄好：`python scripts/voice.py align videos/片名/director.json --audio 錄音檔`；某句重錄：`voice.py redo … --line N --audio 檔案`
- 使用者主動說要 AI 配音才用備案（Fish Audio 等，見 voice.md 後半）
- 還沒錄想先看畫面：`voice.py silent`

### 5. 自動出片＋自查
```bash
python scripts/render.py videos/片名/director.json --preview   # 540×960 預覽（快 4 倍）
python scripts/render.py videos/片名/director.json             # 1080×1920 成品 final.mp4
python scripts/check.py  videos/片名/director.json             # 自查
```
- 自查有 ✗ 先自己修好重出，**用 Read 看 `check/總覽.jpg`**（每句一格、紅色＝平台介面會蓋住的區域）：表情對不對、道具有沒有擋臉擋字、字幕有沒有進紅區
- 第一次出片先給 preview；**請使用者確認每句聲音和字幕對得上**（Claude 聽不到），滿意再出 1080
- 交片時告訴他：影片路徑、長度、自查結果一句話

### 6. 使用者說改哪裡 → 讀 `references/revise.md`
- 改 `director.json` → 改到台詞就請他重錄那句（`voice.py redo`）→ render → check
- 回覆：改了什麼（白話）＋新影片

## 規格與規則
- 直式 1080×1920、30fps、H.264＋AAC、音量 -14 LUFS（各平台通用）
- 安全區：上 250px、下 450px（y>1470）、右 120px 不放字和道具；字幕在 y≈1325、一行 ≤9 字、照語意斷句
- 開場 0.5 秒內出大字＋表情，前 3 秒靜音也看得懂
- 每句換表情，同表情不連續超過 2 句
- 只用使用者本人的聲音和照片；配樂要可商用

## 需要
Python 3.9+、Pillow、numpy、ffmpeg（`setup.py` 會檢查）。自己錄旁白不需要網路；AI 配音（備案）才需要網路與金鑰。全部在本機算圖，不用 GPU。

## 檔案
- `scripts/`：setup.py 環境、faces.py 表情庫、voice.py 旁白（自己錄對時間／AI 配音備案）、direct.py 導演表、render.py 出片、check.py 自查、music.py 內建配樂、asr_align.py 錄音對句（本機語音辨識）、sfx.py 音效合成、common.py 共用
- `assets/`：思源黑體（OFL）、68 個道具圖（Noto Emoji，Apache-2.0）、示範角色 demo_faces/
- `examples/demo/`：示範腳本與導演表
