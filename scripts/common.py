"""大頭照動畫短影音：共用設定（表情名稱、字型、路徑、讀寫導演表、字幕斷句）。只用標準函式庫＋Pillow。"""
import json, os, re, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, 'assets')
W, H, FPS = 1080, 1920, 30

# 表情庫：英文檔名（建議）＋中文別名（使用者用中文檔名也認得）
FACES = [
    ('neutral', '平常', '一般說明、陳述'),
    ('smile', '微笑', '友善、打招呼、輕鬆'),
    ('laugh', '大笑', '好笑、開心、成功'),
    ('surprised', '驚訝', '「你知道嗎」「竟然」'),
    ('shocked', '嚇到', '誇張反應、踩雷、大數字'),
    ('think', '思考', '提問、「為什麼」、分析'),
    ('confused', '疑惑', '「蛤？」、常見誤會'),
    ('angry', '生氣', '抱怨、「不要再…」'),
    ('sad', '難過', '失敗、痛點、可惜'),
    ('wink', '眨眼', '小秘密、小技巧'),
    ('point', '指向', '「重點來了」、指字卡'),
    ('thumbsup', '比讚', '推薦、結論、CTA'),
    ('proud', '得意', '成果、炫耀、「我做到了」'),
    ('wave', '揮手', '開場打招呼、結尾掰掰'),
]
# 一張 4×4 表情總表的固定順序（GPT 提示詞也照這個順序）；*_talk 是同表情「嘴巴張開」版，講話時會自動切換做出對嘴感
GRID16 = ['neutral', 'neutral_talk', 'smile', 'smile_talk', 'laugh', 'surprised', 'shocked', 'think',
          'confused', 'angry', 'sad', 'wink', 'point', 'thumbsup', 'proud', 'wave']
FACE_KEYS = [f[0] for f in FACES]
ZH2KEY = {zh: k for k, zh, _ in FACES}
# 缺表情時的替代順序
FALLBACK = {'laugh': 'smile', 'shocked': 'surprised', 'confused': 'think', 'wink': 'smile', 'point': 'smile',
            'thumbsup': 'smile', 'proud': 'smile', 'wave': 'smile', 'angry': 'neutral', 'sad': 'neutral', 'surprised': 'neutral',
            'think': 'neutral', 'smile': 'neutral'}
REQUIRED = ['neutral', 'smile', 'surprised', 'think']

CAMS = {'still': '不動', 'push': '慢慢推近', 'pull': '慢慢拉遠', 'punch': '快速放大一下（強調）', 'shake': '震動（嚇到／重擊）',
        'slide_l': '從右往左滑入', 'slide_r': '從左往右滑入', 'bounce': '彈跳（開心）', 'tilt': '左右搖擺（疑惑）', 'zoom_face': '推到臉部特寫'}
SFX = ['pop', 'bloop', 'ding', 'ding_hi', 'ding_top', 'boing', 'sparkle', 'whoosh', 'whoosh_long', 'tick', 'boom', 'glitch', 'glass',
       'r_whoosh', 'r_pop', 'r_click', 'r_ding']


def font(kind='black'):
    """全片固定用圓體（粉圓 Huninn，OFL 可商用）。只有一種粗細，要粗一點時程式用同色描邊加粗。
    工作資料夾放 fonts/Huninn-Regular.ttf 可覆蓋。"""
    name = 'Huninn-Regular.ttf'
    for d in [os.path.join(os.getcwd(), 'fonts'), os.path.join(ASSETS, 'fonts')]:
        p = os.path.join(d, name)
        if os.path.exists(p): return p
    raise SystemExit('找不到字型 ' + name)


def find_face(faces_dir, key):
    """回傳 faces_dir 裡 key 表情的檔案（英文或中文檔名都可），找不到回傳 None"""
    zh = dict((k, z) for k, z, _ in FACES).get(key, key)
    for n in [key, zh]:
        for ext in ['png', 'webp', 'jpg', 'jpeg']:
            for p in [os.path.join(faces_dir, 'cut', f'{n}.{ext}'), os.path.join(faces_dir, f'{n}.{ext}')]:
                if os.path.exists(p): return p
        hits = glob.glob(os.path.join(faces_dir, f'[0-9]*_{n}.*'))
        if hits: return sorted(hits)[0]
    return None


def resolve_face(faces_dir, key, seen=None):
    p = find_face(faces_dir, key)
    if p: return key, p
    seen = seen or set(); seen.add(key)
    nxt = FALLBACK.get(key)
    if nxt and nxt not in seen: return resolve_face(faces_dir, nxt, seen)
    return None, None


def find_prop(name, extra_dirs=()):
    for d in list(extra_dirs) + [os.path.join(os.getcwd(), 'props'), os.path.join(ASSETS, 'props')]:
        for ext in ['png', 'webp']:
            p = os.path.join(d, f'{name}.{ext}')
            if os.path.exists(p): return p
    # 中文名稱查內建道具
    idx = json.load(open(os.path.join(ASSETS, 'props', 'props.json'), encoding='utf-8'))
    for k, zh in idx.items():
        if name in zh.split(): return os.path.join(ASSETS, 'props', k + '.png')
    return None


def load(path):
    return json.load(open(path, encoding='utf-8'))


def save(path, data):
    tmp = path + '.tmp'
    json.dump(data, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    os.replace(tmp, path)


PUNCT = '，。！？、；：,.!?;:…「」『』（）()"\'～~—'


def chunks(text, maxc=9):
    """字幕斷句：先照標點切，再把太長的照語意（優先在「的、了、是、在、和、就、都、也、要、會、把、讓、給、跟」之後）切成 ≤maxc 字"""
    parts = [p for p in re.split('[' + re.escape(PUNCT) + r'\s]+', text) if p]
    out = []
    for p in parts:
        while len(p) > maxc:
            cut = None
            for i in range(min(maxc, len(p) - 3), 2, -1):   # 後半至少留 3 字，不會剩「可以」兩個字掛著
                if p[i - 1] in '的了是在和就都也要會把讓給跟說到過再還': cut = i; break
            cut = cut or (maxc if len(p) - maxc >= 3 else len(p) - 3 if len(p) > 6 else maxc)
            out.append(p[:cut]); p = p[cut:]
        if p: out.append(p)
    return out


def ffprobe_dur(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: raise SystemExit('指令失敗：' + ' '.join(cmd[:6]) + '…\n' + r.stderr[-1500:])
    return r
