# 第 4 步：導演表（director.json）

一支片一個資料夾 `videos/片名/`，裡面的 `director.json` 是唯一的設定檔：改片＝改這個檔再重算。

## 格式

```json
{
  "title": "存錢順序錯了",
  "faces": "../../faces",
  "style": {"theme": "奶茶極簡"},
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
| layout | 人物位置和大小 | center 中間（預設）、left 靠左、right 靠右、close 臉部特寫、low_left／low_right 左下／右下（小）、small 中間縮小；換句時會平順移過去 |
| head | 自訂位置（比 layout 優先） | {"x": 0.3, "y": 0.5, "size": 0.9}：x、y 是畫面比例 0～1（中心點），size 大小倍數；會自動留在安全區內 |
| big | 空位放大字（吸睛重點） | 「然後呢」「保養\n日常」；不寫＝人物在旁邊時自動用第一個強調字；false 關掉。有大字的句子不放道具 |
| pause | 這句之後停多久（秒） | 預設 0.12；轉折前可以 0.4 |
| media | 素材（照片、截圖、影片片段），放在工作資料夾 `素材/` | `{"file": "截圖.png", "mode": "card"}` 卡片彈在頭上方、大頭縮小往下；`"mode": "full"` 鋪滿畫面、大頭縮到右下角；影片可加 `"from": 秒數` 從第幾秒開始；橫的素材在 full 模式會自動用模糊底＋完整原圖，要裁滿加 `"crop": true` |
| trans | 這句開始時的轉場動畫（0.4 秒） | zoom 縮放穿越、blinds 百葉窗、wipe 色塊掃過、flash 白光、none 不要；不寫＝有 banner 的新段落自動加（縮放穿越、百葉窗輪流） |

**自動音效：** 轉場 whoosh、換表情 pop、道具出現 bloop、標籤／滑入 whoosh、shake 配 boom、punch 配 pop、開場大字 whoosh＋pop。

## 整支片

| 欄位 | 說明 |
|---|---|
| hook | 開場大字：text（`\n` 換行，最多 2 行、每行 ≤8 字）、sub 小標（身分標籤）、until 顯示到幾秒（2～3）、emph 紅字 |
| style | theme 風格模板（見下表，選了就不用自己配色；其他欄位可再覆蓋）、背景 bg→bg2 漸層、accent 標題／標籤色、hl 字幕強調色、pattern（dots 點點、stripes 斜線、grid 格子、none）、head_size 大頭佔畫面寬度（預設 0.68）、caption_size 字幕大小（預設 84）、sticker 白邊貼紙感（預設 true） |
| bgm | 配樂檔（講話時自動壓低）；bgm_db 配樂音量（預設 -20，想更小聲 -24）。沒有配樂就用內建產生器：`python scripts/music.py make 輕快 --director …/director.json`（輕快、可愛、科技、溫馨、熱血，程式合成、可商用） |
| sfx_gain | 音效整體音量（預設 0.8） |
| caption_max | 字幕一行最多幾字（預設 9） |
| transition | 段落轉場：auto（預設，縮放穿越／百葉窗輪流）、zoom、blinds、wipe、flash、none（整支都不要） |

## 風格模板（style.theme）

字體全部固定圓體（粉圓 Huninn），只換配色和版面。

| 風格 | 感覺 | 頭後面 | 字幕 | 標籤 | 適合 |
|---|---|---|---|---|---|
| 奶茶極簡 | 奶茶色、溫柔 | 拱門 | 白色圓角底 | 細框圓角 | 生活、理財、女性向 |
| 莫蘭迪綠 | 灰綠、安靜 | 圓形 | 綠色字幕條 | 細線＋字 | 療癒、健康、知識 |
| 霧粉雜誌 | 霧粉、雜誌感 | 白色拱門 | 無底（柔光墊底） | 細線＋字 | 美妝、穿搭、個人品牌 |
| 黑金質感 | 深色、精品感 | 深色圓形 | 象牙白字 | 金色細框 | 高單價服務、商業、顧問 |
| 霧藍清新 | 淡藍、乾淨 | 白色圓形 | 白色圓角底 | 細框圓角 | 科技、教學、工具 |
| 燕麥紙感 | 紙質、手作 | 拱門 | 螢光筆畫重點 | 細線＋字 | 筆記、讀書、手作 |
| 活潑 | 暖黃卡通、彈跳 | 無（白邊貼紙） | 白字黑粗邊 | 紅色實心 | 搞笑、兒童、輕鬆 |

高級 IG 風（前 6 款）動作比較輕：字幕淡入、換表情和道具不大彈跳、開場標題淡入。運鏡還是照每句的 cam；想更有質感就多用 still／push／pull，少用 shake。
emoji 道具比較卡通，高級風建議一支片 2～4 個就好，或改放自己的去背圖（props/）。

可再覆蓋的欄位：shape（arch 拱門／circle 圓形／不寫＝沒有）、shape_color、frame（細線外框 true/false）、label_l／label_r（外框角落英文小字）、grain（紙感顆粒 0～10）、cap（pill 圓角底／bar 字幕條／plain 無底／marker 螢光筆／stroke 粗邊）、cap_color、cap_bg（可帶透明度 #RRGGBBAA）、banner_style（outline／line／solid）、hook_style（elegant／pop）、motion（soft／bouncy）。

## 配色範例（自己配色時用）

使用者有品牌色：選一個最接近的風格，再把 accent 換成品牌色。

| 名稱 | bg | bg2 | accent | hl |
|---|---|---|---|---|
| 暖黃（預設） | #FFE9BF | #FFC879 | #FF4B2B | #FFE14D |
| 薄荷 | #DFF7EE | #9FE3C9 | #0E8A5F | #FFE14D |
| 天空 | #E3F1FF | #A8D1FF | #2457D6 | #FFE14D |
| 粉紅 | #FFE6EF | #FFB3CD | #E0336E | #FFF07A |
| 深色質感 | #22252E | #3A3F4E | #FFB020 | #FFB020 |

使用者有品牌色就換 accent；背景用淺色，大頭照才清楚。

## 排版原則（高級感、吸睛）

1. 人物不加框、不加白邊，靠位置和大小變化做節奏：中間 → 靠邊放大字 → 特寫 → 下方小人＋上方大字，不要連續兩句同版面
2. 大字只放 2～6 個字的重點（痛點、反轉、結論），一支片 3～5 次就好；最後一行自動反白色塊
3. 特寫（close）留給情緒最強的一句（驚訝、轉折），字幕會壓在下巴附近，台詞要短
4. 有大字就不放道具；道具一支片 2～4 個

## 排表情的原則（Claude 自己排或修 direct.py 初稿時）

1. 表情跟著情緒走：問句→思考／驚訝；痛點→難過／生氣；重點→指向；結論→比讚／得意；好笑→大笑
2. **每句換表情**，同一個表情不要連續超過 2 句；整支至少 5 種
3. 開頭第一句：驚訝或嚇到＋punch／shake（0.5 秒內要有強畫面）
4. 運鏡不要每句都動，大概「動、靜、動、靜」；shake 一支最多 2 次
5. 道具只放在有具體東西的句子（錢、時間、手機…），大概一半的句子有道具就好
6. 重點句加 banner（第1招、第2招…），觀眾一看就知道講到哪
