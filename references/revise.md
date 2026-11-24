# 第 6 步：使用者說改哪裡 → 改導演表 → 重算

使用者看完片，用自己的話說要改什麼。Claude 對照下表改 `director.json`，只改他說的地方，然後：

- **只改畫面**（表情、道具、運鏡、標籤、配色、字幕強調）→ 直接 `render.py --preview` 給他看，確認後再出 1080
- **改了台詞**（text、say）→ 請使用者重錄那幾句（`voice.py redo --line N`）；用 AI 配音的話 `voice.py say`（只重念改過的句子），再 render
- **改了順序、加句、刪句** → 新句子請使用者錄（redo），刪句就從導演表拿掉再跑 `voice.py redo` 任一句或整篇重跑 align → render

| 使用者說 | 改哪裡 |
|---|---|
| 「第 3 句表情換生氣」「這裡要更驚訝」 | lines[2].face（更驚訝＝shocked） |
| 「這句加個錢的道具」「拿掉那個問號」 | prop |
| 「道具擋到臉」 | prop_pos 換 low_right／top_left 等，或減少道具數 |
| 「這裡要震一下」「太晃了」 | cam：shake／punch，或改 still |
| 「字太小」「字幕太大」 | style.caption_size（預設 84，可 70～96） |
| 「頭太大／太小」 | style.head_size（預設 0.68，可 0.6～0.85） |
| 「開頭標題改成…」「標題停久一點」 | hook.text／hook.until |
| 「這幾個字要變黃」 | emph |
| 「顏色換成藍色系」「換個風格」「要更高級」 | style.theme 換風格（見 director.md 風格表），或只改 accent |
| 「字幕底框不要」「字幕要有底」 | style.cap：plain／pill／bar／marker |
| 「人放左邊／右邊」「放大一點」「這句特寫」 | 那句 layout（left／right／close／low_left…）或 head 自訂 x、y、size |
| 「字不夠吸睛」「這裡放大字」 | 那句加 big（2～6 字重點） |
| 「念太快」「念太慢」 | 自己錄：請他重錄；AI 配音：voice.py say --speed 0.9～1.15 |
| 「這個字念錯」 | 自己錄：重錄那句（redo）；AI 配音：那句加 say（念法）重跑 say |
| 「句子中間停太久」 | 那句 pause 改小 |
| 「音效太吵」「不要音效」 | sfx_gain 調低，或某句 sfx: "none" |
| 「加配樂」「換一種音樂」 | `music.py make 風格 --director …`（輕快／可愛／科技／溫馨／熱血），或使用者給可商用的音樂檔寫進 bgm；「音樂太大聲」bgm_db 改 -24 |
| 「這句放這張圖／這段影片」 | 素材放進 素材/，那句加 media（card 卡片、full 全畫面） |
| 「這裡加轉場」「轉場換百葉窗」「不要轉場」 | 那句 trans（zoom／blinds／wipe／flash／none）；整支用 transition |
| 「這句拆成兩句」 | 拆 lines，兩句給不同表情 |
| 「太長了」 | 刪句或縮短台詞，目標 20～45 秒 |

改完一律再跑 `check.py`，自查通過才交片。每次回覆使用者：改了哪幾句（用他看得懂的話，不要講欄位名）＋新影片路徑。
