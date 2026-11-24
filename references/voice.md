# 旁白（預設：自己錄）

**預設不用 AI 配音，使用者自己錄旁白**：最自然、免費、觀眾最有親切感。程式會把整篇錄音依停頓切成一句一句，對上導演表的每一句。AI 配音只是備案，使用者主動要求才用（見文末「備案」）。

旁白在**導演表確認之後**錄（台詞定了才錄，免得重錄）。

## 怎麼錄（給使用者看的說明）

1. 找安靜的地方（關冷氣、電扇），手機離嘴巴一個拳頭，用手機內建錄音 App
2. Claude 會給你一份「錄音稿」（`videos/片名/錄音稿.txt`，一行一句）
3. **照順序念，每念完一句停 1 秒再念下一句**（停頓是給程式切句用的）
4. 念錯沒關係：停 2 秒，**從那一句重念**就好，Claude 會幫你把念錯的那段拿掉
5. 用平常講話的語氣，比拍片時再多一點點情緒；不要放背景音樂
6. 錄好把檔案（m4a／mp3／wav 都可以）放進 `videos/片名/`，跟 Claude 說「錄好了」

## Claude 要做的

```bash
# 產生錄音稿：每句的 text（say 是給 AI 配音用的念法，自己錄用不到）
python -c "import json,sys;D=json.load(open(sys.argv[1],encoding='utf-8'));print('\n'.join(l['text'] for l in D['lines']))" videos/片名/director.json > videos/片名/錄音稿.txt

# 錄好之後：依停頓切句、對時間
python scripts/voice.py align videos/片名/director.json --audio videos/片名/錄音.m4a
```

- 切完要確認：`align` 如果說「只找到 N 段話、腳本有 M 句」，表示停頓不夠或念錯重念造成段數不對 → 請使用者句子之間停久一點重錄，或只重錄有問題的句子
- 念錯重念：段數會比句數多，程式會把最短的停頓併起來；Claude 聽不到聲音，所以**一定要請使用者看預覽片，確認每句嘴型、字幕和聲音對得上**
- 每句切好的錄音存在 `videos/片名/audio/line_XX_rec.wav`

### 只重錄某一句

台詞改了一句、或某句念得不好：

```bash
python scripts/voice.py redo videos/片名/director.json --line 6 --audio videos/片名/第6句.m4a
```

其他句不動，時間自動重算，再 render 就好。

### 錄音太小聲、有雜音

出片時會自動做音量標準化（-14 LUFS）、切低頻雜音、壓縮。背景很吵的話請使用者換地方重錄。

### 只想先看畫面（還沒錄）

```bash
python scripts/voice.py silent videos/片名/director.json   # 用每秒 4.6 字估時間，沒有人聲
```

---

# 備案：AI 配音（使用者主動要求才用）

**只能複製自己的聲音**（或有本人書面同意的聲音）。用 AI 配音的流程：建立聲音（setup）→ 每支片 `voice.py say` 一句一句念，時間自動寫回導演表；改台詞重跑 say 只會重念改過的句子。

## 選一家配音（預設 Fish Audio）

| 選項 | 適合 | 要準備 | 費用（以官網為準） |
|---|---|---|---|
| **fish（預設）** Fish Audio | 最簡單、中文自然 | 到 fish.audio 註冊 → API Keys 建立金鑰 | 有免費額度，之後按字數計費 |
| minimax MiniMax 海螺 | 中文語氣最強之一 | platform.minimax.io 註冊、儲值、建立金鑰 | 複製聲音要付建立費；7 天沒用會被刪 |
| elevenlabs ElevenLabs | 介面好用、國外常見 | elevenlabs.io 付費方案（Starter 以上才能複製聲音） | 月費 |
| gptsovits 本機 GPT-SoVITS | 免費、聲音不外流 | NVIDIA 顯卡＋自己安裝 GPT-SoVITS 並開 api_v2（port 9880） | 免費 |
| **剪映／自己錄** | 已經在用剪映、或想自己念 | 剪映「克隆音色」念整篇稿匯出音檔，或自己錄整篇 | 剪映會員方案 |
| edge 微軟免費語音 | 先試流程（**不是你的聲音**） | `pip install edge-tts` | 免費 |

### 金鑰放哪裡（重要）

在工作資料夾建 `voice/keys.env`，一行一個：

```
FISH_API_KEY=貼上你的金鑰
```

**金鑰不要貼到對話裡。** 使用者如果貼了，提醒他到官網把那把金鑰刪掉重建。分享工作資料夾給別人前，先刪掉 `voice/keys.env`。

## 指令

```bash
# 建立聲音（只做一次），--test 會念一句讓你試聽
python scripts/voice.py setup --provider fish --sample voice/sample.m4a --test "你好，這是我的 AI 聲音，聽起來像我嗎？"

# 每支片：照導演表一句一句念，時間自動寫回導演表
python scripts/voice.py say videos/片名/director.json
```

- 只改了某幾句台詞，重跑 `say` 只會重念改過的句子（省錢）
- 語速：`--speed 1.1`（快一點）或寫進 `voice/voice.json` 的 `speed`
- 念錯字／破音字：導演表那句加 `"say": "念法"`（字幕還是顯示 text），例如 text「3 招」say「三招」、text「AI」say「欸愛」

### 剪映／自己錄（手動一步）

剪映沒有開放給程式呼叫，所以要使用者自己匯出：

1. 剪映 → 文字朗讀 → 克隆音色（用自己的聲音建立）
2. 把 `videos/片名/script.txt` 整篇貼進去朗讀，**每句之間空一行**（或句尾加句號），讓句子之間有停頓
3. 匯出音訊（mp3／wav），放到 `videos/片名/` 裡
4. Claude 跑：

```bash
python scripts/voice.py align videos/片名/director.json --audio videos/片名/剪映匯出.mp3
```

程式會依停頓把音檔切成一句一句、對上導演表。停頓太短切不出來時會改用字數比例分配，並提醒使用者；這時請他每句之間停久一點（半秒）重匯出。自己用手機錄整篇也是同一個指令。

### 只想先看畫面

```bash
python scripts/voice.py silent videos/片名/director.json   # 用每秒 4.6 字估時間，沒有人聲
```

## 不想克隆聲音（用現成 AI 聲音、自己錄、或不要人聲）

| 做法 | 指令 |
|---|---|
| **自己錄**（最自然、免費）：手機錄整篇稿，每句停半秒 | `python scripts/voice.py align videos/片名/director.json --audio 我的錄音.m4a` |
| **免費台灣腔 AI**（edge，`pip install edge-tts`）：女聲 zh-TW-HsiaoChenNeural、zh-TW-HsiaoYuNeural；男聲 zh-TW-YunJheNeural | `python scripts/voice.py setup --provider edge --voice-id zh-TW-YunJheNeural --test "試聽一下"` |
| **Fish Audio 現成聲音**：到 fish.audio 聲音庫挑一個喜歡的，複製網址裡的模型 ID | `python scripts/voice.py setup --provider fish --voice-id 模型ID --test "試聽一下"` |
| **MiniMax 內建音色**（例：Chinese (Mandarin)_Lyrical_Voice，清單見官網） | `python scripts/voice.py setup --provider minimax --voice-id "音色ID"` |
| **剪映內建朗讀音色**：剪映選一個朗讀聲音念整篇、匯出 | 同「自己錄」，用 `voice.py align` |
| **不要人聲**：只有大字幕＋配樂＋音效 | `python scripts/voice.py silent …`，導演表加 `"bgm": "配樂.mp3"` |

setup 之後一樣用 `voice.py say` 逐句配音。用現成聲音要注意：別人也會用同一個聲音，品牌辨識度比較低；商用規定以各服務條款為準。

## 疑難排解

| 狀況 | 怎麼辦 |
|---|---|
| 401 金鑰錯誤 | 檢查 voice/keys.env 有沒有多空格、是不是過期 |
| 402／403 | 額度用完、或方案不含聲音複製 |
| 聲音不像 | 重錄 20～30 秒、更安靜、語氣更自然；用 `--sample` 重建 |
| 有雜音、像機器 | 錄音環境太吵；MiniMax 已開降噪；Fish 試 `--model s1` 或換一段錄音 |
| 念太快／太慢 | `--speed 0.9`～`1.15` |
