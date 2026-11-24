"""導演表工具
  python direct.py new  videos/片名 --script 腳本.txt [--hook "大字標題"] [--sub "身分標籤"]
        → 一行一句建立 director.json，依台詞自動配表情／道具／運鏡（初稿，Claude 再逐句調整）
  python direct.py show videos/片名/director.json    → 印出導演表、存成 導演表.md（給使用者看、說要改哪裡）
  python direct.py lint videos/片名/director.json    → 檢查導演表（表情、道具、運鏡、字幕字數、開頭節奏）
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ASSETS, FACES, FACE_KEYS, CAMS, SFX, load, save, chunks, find_prop, resolve_face

ZH = {k: z for k, z, _ in FACES}

# 台詞 → 表情（第一個命中的規則）
FACE_RULES = [
    (r'追蹤|按讚|收藏|記得|推薦|分享', 'thumbsup'),
    (r'做到|成功|賺到|變成|嚇一跳|翻倍', 'proud'),
    (r'[!！]{1,}.*(錯|完蛋|千萬|危險|不要)|嚇|天啊|竟然|居然', 'shocked'),
    (r'不要再|別再|氣死|受不了|爛', 'angry'),
    (r'難過|可惜|失敗|好累|哭|慘', 'sad'),
    (r'為什麼|怎麼|是不是|嗎[？?]|[？?]$', 'think'),
    (r'蛤|搞不懂|奇怪|到底', 'confused'),
    (r'你知道|其實|原來|沒想到', 'surprised'),
    (r'秘密|偷偷|小技巧|告訴你', 'wink'),
    (r'第[一二三四五12345]|重點|首先|最後|關鍵', 'point'),
    (r'哈哈|好笑|開心|太好了|超讚', 'laugh'),
    (r'哈囉|嗨|掰掰|下次見', 'wave'),
]
PROP_RULES = [
    (r'錢|存|薪水|賺', 'money'), (r'時間|每天|早上|晚上|分鐘', 'clock'), (r'手機|App|滑', 'phone'), (r'電腦|網站|上網', 'laptop'),
    (r'想|點子|方法|招', 'idea'), (r'成長|變多|翻倍|提升', 'chart_up'), (r'危險|小心|注意|錯', 'warning'), (r'秘密|鎖', 'lock'),
    (r'目標|計畫', 'target'), (r'追蹤|通知|訂閱', 'bell'), (r'讚|推薦', 'thumbs_up'), (r'學|書|讀', 'book'), (r'吃|喝|咖啡', 'coffee'),
    (r'快|馬上|立刻', 'lightning'), (r'找|搜尋', 'magnifier'), (r'愛|喜歡', 'heart'), (r'成功|冠軍|第一名', 'trophy'), (r'[？?]', 'question'),
]
PZH = {k: v.split()[0] for k, v in json.load(open(os.path.join(ASSETS, 'props', 'props.json'), encoding='utf-8')).items()}
PART = re.compile(r'^[【\[（(]?(起|承|轉|合)[】\]）)][：:\s]*')
CTA = re.compile(r'追蹤|留言|收藏|存起來|私訊|連結|報名|分享|按讚|訂閱|點進|預約|下一集|找我')
NUM = re.compile(r'第[一二三四五六七八九十0-9]+[招個點步]')


def guess(text, i, n):
    face = 'neutral'
    for pat, f in FACE_RULES:
        if re.search(pat, text): face = f; break
    prop = None
    for pat, p in PROP_RULES:
        if re.search(pat, text): prop = p; break
    cam = 'punch' if i == 0 else {'shocked': 'shake', 'surprised': 'punch', 'point': 'slide_l', 'laugh': 'bounce', 'confused': 'tilt',
                                  'wink': 'zoom_face', 'proud': 'push', 'thumbsup': 'punch'}.get(face, 'push' if i % 3 == 1 else 'still')
    ln = {'text': text, 'face': face, 'cam': cam}
    if prop: ln['prop'] = prop
    m = NUM.search(text)
    if m: ln['banner'] = m.group(0)
    return ln


def cmd_new(a):
    os.makedirs(a.dir, exist_ok=True)
    raw = open(a.script, encoding='utf-8').read() if a.script else sys.stdin.read()
    lines, parts, part = [], [], None
    for l in raw.splitlines():   # 腳本可以用【起】【承】【轉】【合】分段（單獨一行，或寫在句子前面）
        l = l.strip()
        m = PART.match(l)
        if m: part = m.group(1); l = l[m.end():].strip()
        l = l.strip(' \t-•*0123456789.、')
        if l and not l.startswith('#'): lines.append(l); parts.append(part)
    D = {'title': a.title or os.path.basename(os.path.normpath(a.dir)), 'faces': '../../faces', 'style': {'theme': a.theme} if a.theme else {},
         'hook': {'text': a.hook or chunks(lines[0], 8)[0], 'until': 2.6}, 'lines': []}
    if a.sub: D['hook']['sub'] = a.sub
    for i, t in enumerate(lines):
        ln = guess(t, i, len(lines))
        if parts[i]: ln['part'] = parts[i]
        D['lines'].append(ln)
    # 版面：人物位置輪流換（中間、左、右、特寫、下方），有強調字的句子把人移到旁邊、空位放大字
    cyc = ['left', 'center', 'right', 'close', 'low_left', 'center', 'low_right']; k = 0
    for i, ln in enumerate(D['lines']):
        if i == 0 or ln.get('banner'): ln['layout'] = 'center'; continue
        ln['layout'] = cyc[k % len(cyc)]; k += 1
    # 避免連續三句同表情
    for i in range(2, len(D['lines'])):
        if D['lines'][i]['face'] == D['lines'][i - 1]['face'] == D['lines'][i - 2]['face']: D['lines'][i]['face'] = 'smile' if D['lines'][i]['face'] != 'smile' else 'neutral'
    p = os.path.join(a.dir, 'director.json'); save(p, D); print('✓ 導演表初稿 → ' + p); show(p)


def show(path):
    D = load(path); rows = ['| # | 段落 | 秒數 | 台詞（字幕） | 表情 | 道具 | 運鏡 | 音效 | 標籤 |', '|---|---|---|---|---|---|---|---|---|']
    for i, l in enumerate(D['lines'], 1):
        tm = f'{l["start"]:.1f}–{l["end"]:.1f}' if 'start' in l else '－'
        pr = l.get('prop') or []; pr = [pr] if isinstance(pr, str) else pr; pr = '、'.join(PZH.get(x, x) for x in pr)
        sf = l.get('sfx') or '自動'; sf = '、'.join(sf) if isinstance(sf, list) else sf
        rows.append(f'| {i} | {l.get("part", "")} | {tm} | {l["text"]} | {ZH.get(l.get("face", "neutral"), l.get("face"))} | {pr} | {CAMS.get(l.get("cam", "still"), l.get("cam"))} | {sf} | {l.get("banner", "")} |')
    h = D.get('hook') or {}
    md = f'# 導演表：{D.get("title", "")}\n\n開場大字：**{h.get("text", "（無）")}**' + (f'（小標：{h["sub"]}）' if h.get('sub') else '') + \
         f'，顯示到 {h.get("until", 3)} 秒\n\n' + '\n'.join(rows) + '\n\n要改哪裡直接說，例如「第 3 句表情換生氣」「第 5 句加錢的道具」「開場標題改成…」。\n'
    out = os.path.join(os.path.dirname(os.path.abspath(path)), '導演表.md'); open(out, 'w', encoding='utf-8').write(md)
    print(md); print('（已存 ' + out + '）')


def lint(path):
    D = load(path); base = os.path.dirname(os.path.abspath(path)); fd = os.path.join(base, D.get('faces', '../../faces'))
    errs, warns = [], []
    if not D.get('hook'): warns.append('沒有開場大字（前 3 秒要有大字標題，靜音也看得懂）')
    for i, l in enumerate(D['lines'], 1):
        f = l.get('face', 'neutral')
        if f not in FACE_KEYS: errs.append(f'第{i}句 表情「{f}」不在表情清單（{"、".join(FACE_KEYS)}）')
        else:
            real, p = resolve_face(fd, f)
            if not p: errs.append(f'第{i}句 表情庫沒有 {f}，也沒有可代替的')
            elif real != f: warns.append(f'第{i}句 表情庫沒有「{ZH[f]}」，會用「{ZH.get(real, real)}」代替')
        if l.get('cam', 'still') not in CAMS: errs.append(f'第{i}句 運鏡「{l.get("cam")}」不認得（{"、".join(CAMS)}）')
        for s in ([l['sfx']] if isinstance(l.get('sfx'), str) else l.get('sfx') or []):
            if s != 'none' and s not in SFX: errs.append(f'第{i}句 音效「{s}」不認得')
        for p in ([l['prop']] if isinstance(l.get('prop'), str) else l.get('prop') or []):
            if not find_prop(p, [os.path.join(base, 'props'), os.path.join(base, '..', '..', 'props')]): errs.append(f'第{i}句 找不到道具「{p}」')
        if l.get('media'):
            mf = l['media']['file'] if isinstance(l['media'], dict) else l['media']
            if not any(os.path.exists(c) for c in [mf, os.path.join(base, mf), os.path.join(base, '..', '..', '素材', mf), os.path.join(base, '素材', mf)]):
                errs.append(f'第{i}句 找不到素材「{mf}」（放工作資料夾 素材/）')
        for c in chunks(l['text'], D.get('caption_max', 9)):
            if len(c) > D.get('caption_max', 9): warns.append(f'第{i}句 字幕「{c}」超過 9 字，建議改短或加標點')
        if len(l['text']) > 28: warns.append(f'第{i}句 太長（{len(l["text"])} 字），建議拆成兩句、換表情')
        if 'start' in l and l['end'] - l['start'] > 5.5: warns.append(f'第{i}句 同一個畫面 {l["end"] - l["start"]:.1f} 秒，太久會無聊，建議拆句')
    faces = [l.get('face') for l in D['lines']]
    for i in range(2, len(faces)):
        if faces[i] == faces[i - 1] == faces[i - 2]: warns.append(f'第{i - 1}～{i + 1}句 連續三句同表情')
    if len(set(faces)) < min(5, len(faces)): warns.append(f'整支只用了 {len(set(faces))} 種表情，建議至少 5 種')
    ps = [l.get('part') for l in D['lines'] if l.get('part')]
    if ps:
        miss = [p for p in '起承轉合' if p not in ps]
        if miss: warns.append('起承轉合少了「' + '、'.join(miss) + '」段')
        if [p for p in ps] != sorted(ps, key='起承轉合'.index): warns.append('起承轉合的順序亂了（要 起→承→轉→合）')
    if D['lines'] and not any(CTA.search(l['text']) for l in D['lines'][-2:]): warns.append('結尾兩句沒有 CTA（只要一個動作：追蹤／留言／收藏／私訊…，並說為什麼）')
    if D['lines'] and D['lines'][0].get('cam', 'still') == 'still': warns.append('第 1 句運鏡是不動，開頭建議 punch 或 shake')
    if D.get('duration') and not 15 <= D['duration'] <= 90: warns.append(f'總長 {D["duration"]:.0f} 秒，短影音建議 20～60 秒')
    for e in errs: print('✗ ' + e)
    for w in warns: print('⚠ ' + w)
    print('導演表檢查：' + ('✓ 沒問題' if not errs and not warns else f'{len(errs)} 個錯誤、{len(warns)} 個建議'))
    return errs, warns


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('new'); p.add_argument('dir'); p.add_argument('--script'); p.add_argument('--hook'); p.add_argument('--sub'); p.add_argument('--title'); p.add_argument('--theme', help='風格：活潑、奶茶極簡、莫蘭迪綠、霧粉雜誌、黑金質感、霧藍清新、燕麥紙感')
    p.set_defaults(f=cmd_new)
    p = sp.add_parser('show'); p.add_argument('director'); p.set_defaults(f=lambda a: show(a.director))
    p = sp.add_parser('lint'); p.add_argument('director'); p.set_defaults(f=lambda a: sys.exit(1 if lint(a.director)[0] else 0))
    a = ap.parse_args(); a.f(a)
