# 第 4 步：導演表（director.json）

一支片一個資料夾 `videos/片名/`，裡面的 `director.json` 是唯一的設定檔：改片＝改這個檔再重算。

## 格式

```json
{
  "title": "存錢順序錯了",
  "faces": "../../faces",
  "style": {"bg": "#FFE9BF", "bg2": "#FFC879", "accent": "#FF4B2B", "hl": "#FFE14D", "pattern": "dots"},
  "hook": {"text": "90%的人\n都存錯錢", "sub": "上班族必看", "until": 2.6, "emph": ["90%"]},
  "bgm": null,
  "lines": [
    {"text": "你是不是每個月都存不到錢？", "face": "surprised", "cam": "punch", "prop": "money", "emph": ["存不到錢"]},
    {"text": "第一招，薪水一進來就先存", "face": "point", "cam": "slide_l", "banner": "第1招 先存再花", "prop": "calendar"},
    {"text": "第二招，把存錢帳戶分開", "face": "wink", "cam": "zoom_face", "prop": ["lock", "key"], "prop_pos": ["right", "left"]}
  ]
}
```

`voice.py say` 之後每句會多 `start`、`end`、`audio`，最外層多 `voice`、`duration`，不要手動改這些。

## 每句可以設定

| 欄位 | 說明 | 值 |
|---|---|---|
| text | 台詞＝字幕（必填） | 8～20 字，字幕自動斷成一行 ≤9 字 |
| say | 念法跟字幕不同時用 | 「三招」「欸愛」 |
| face | 表情 | neutral 平常、smile 微笑、laugh 大笑、surprised 驚訝、shocked 嚇到、think 思考、confused 疑惑、angry 生氣、sad 難過、wink 眨眼、point 指向、thumbsup 比讚、proud 得意、wave 揮手 |
| cam | 運鏡 | still 不動、push 慢推近、pull 慢拉遠、punch 快速放大（強調）、shake 震動、slide_l／slide_r 滑入、bounce 彈跳、tilt 搖擺、zoom_face 推到臉部特寫 |
| prop | 道具（最多 3 個） | 內建英文名或中文名（money／錢、idea／燈泡…，清單 assets/props/props.json），或工作資料夾 props/ 的檔名 |
| prop_pos | 道具位置 | right、left、top、top_right、top_left、low_right、low_left |
| emph | 字幕要變黃色強調的詞 | ["存不到錢"] |
| banner | 頭上的紅色標籤 | 「第1招 先存再花」「重點」「追蹤看更多」 |
| sfx | 音效（不寫＝自動配） | pop bloop ding ding_hi ding_top boing sparkle whoosh whoosh_long tick boom glitch glass；"none" 關掉 |
| pause | 這句之後停多久（秒） | 預設 0.12；轉折前可以 0.4 |
| media | 素材（照片、截圖、影片片段），放在工作資料夾 `素材/` | `{"file": "截圖.png", "mode": "card"}` 卡片彈在頭上方、大頭縮小往下；`"mode": "full"` 鋪滿畫面、大頭縮到右下角；影片可加 `"from": 秒數` 從第幾秒開始；橫的素材在 full 模式會自動用模糊底＋完整原圖，要裁滿加 `"crop": true` |
| trans | 這句開始時的轉場動畫（0.4 秒） | zoom 縮放穿越、blinds 百葉窗、wipe 色塊掃過、flash 白光、none 不要；不寫＝有 banner 的新段落自動加（縮放穿越、百葉窗輪流） |

**自動音效：** 轉場 whoosh、換表情 pop、道具出現 bloop、標籤／滑入 whoosh、shake 配 boom、punch 配 pop、開場大字 whoosh＋pop。

## 整支片

| 欄位 | 說明 |
|---|---|
| hook | 開場大字：text（`\n` 換行，最多 2 行、每行 ≤8 字）、sub 小標（身分標籤）、until 顯示到幾秒（2～3）、emph 紅字 |
| style | 背景 bg→bg2 漸層、accent 標題／標籤色、hl 字幕強調色、pattern（dots 點點、stripes 斜線、grid 格子、none）、head_size 大頭佔畫面寬度（預設 0.68）、caption_size 字幕大小（預設 84）、sticker 白邊貼紙感（預設 true） |
| bgm | 配樂檔（講話時自動壓低）；bgm_db 配樂音量（預設 -20，想更小聲 -24）。沒有配樂就用內建產生器：`python scripts/music.py make 輕快 --director …/director.json`（輕快、可愛、科技、溫馨、熱血，程式合成、可商用） |
| sfx_gain | 音效整體音量（預設 0.8） |
| caption_max | 字幕一行最多幾字（預設 9） |
| transition | 段落轉場：auto（預設，縮放穿越／百葉窗輪流）、zoom、blinds、wipe、flash、none（整支都不要） |

## 配色範例（style）

| 名稱 | bg | bg2 | accent | hl |
|---|---|---|---|---|
| 暖黃（預設） | #FFE9BF | #FFC879 | #FF4B2B | #FFE14D |
| 薄荷 | #DFF7EE | #9FE3C9 | #0E8A5F | #FFE14D |
| 天空 | #E3F1FF | #A8D1FF | #2457D6 | #FFE14D |
| 粉紅 | #FFE6EF | #FFB3CD | #E0336E | #FFF07A |
| 深色質感 | #22252E | #3A3F4E | #FFB020 | #FFB020 |

使用者有品牌色就換 accent；背景用淺色，大頭照才清楚。

## 排表情的原則（Claude 自己排或修 direct.py 初稿時）

1. 表情跟著情緒走：問句→思考／驚訝；痛點→難過／生氣；重點→指向；結論→比讚／得意；好笑→大笑
2. **每句換表情**，同一個表情不要連續超過 2 句；整支至少 5 種
3. 開頭第一句：驚訝或嚇到＋punch／shake（0.5 秒內要有強畫面）
4. 運鏡不要每句都動，大概「動、靜、動、靜」；shake 一支最多 2 次
5. 道具只放在有具體東西的句子（錢、時間、手機…），大概一半的句子有道具就好
6. 重點句加 banner（第1招、第2招…），觀眾一看就知道講到哪
