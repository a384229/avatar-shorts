"""設計感版面（style.stage = 'design'）：柔霧／瑞士／拍立得／撕紙 系列。
人物固定在左下或右下當配角，中間是內容區（小標 → 引言 → 大字），字幕放在人物旁邊的空位，
任何字都不會壓到臉。整格用 1080×1920 畫，預覽時再縮小。"""
import math, os, random, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from common import W, H, FPS, find_prop

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(HERE, '..', 'assets', 'fonts'), os.path.join(os.getcwd(), 'fonts')]
SERIF, SERIFM, SANS, SANSM, ITAL, ROUND = ('NotoSerif-Black.ttf', 'NotoSerif-SemiBold.ttf', 'NotoSans-Black.ttf',
                                           'NotoSans-Medium.ttf', 'DMSerifDisplay-Italic.ttf', 'Huninn-Regular.ttf')

def _soft(ink, acc, g1, g2, blob, tag=None, line=None):
    return dict(kind='soft', ink=ink, acc=acc, g1=g1, g2=g2, blob=blob, tag=tag or ink, line=line or '#E3D3C6',
                title=SERIF, lead=SERIFM, big=SERIF, cap_font=SERIF)

DESIGN_THEMES = {
    '柔霧奶茶': _soft('#3B302A', '#B5654A', (247, 240, 232), (238, 222, 208), (255, 214, 186), line='#E0CDBE'),
    '柔霧藍':   _soft('#26324A', '#4A6FA5', (240, 243, 247), (220, 226, 238), (196, 210, 240), line='#C9D2E3'),
    '柔霧綠':   _soft('#2E3A2F', '#5F7F5A', (244, 243, 236), (222, 230, 216), (200, 222, 196), line='#CBD6C4'),
    '柔霧莓':   _soft('#3D2A2E', '#B04A62', (250, 240, 234), (244, 221, 218), (255, 196, 180), tag='#B04A62', line='#EACBCB'),
    '瑞士極簡': dict(kind='swiss', ink='#111111', acc='#E5372A', bg='#F5F4F0', collage=False, title=SANS, lead=SANSM, big=SANS, cap_font=SANS),
    '瑞士拼貼': dict(kind='swiss', ink='#111111', acc='#E5372A', bg='#F5F4F0', collage=True, title=SANS, lead=SANSM, big=SANS, cap_font=SANS),
    '拍立得':   dict(kind='polaroid', ink='#33291F', acc='#C0704E', bg='#F6F1EA', title=SERIF, lead=SERIFM, big=SERIF, cap_font=SERIF),
    '講解橘':   dict(kind='explain', ink='#1E1A17', acc='#C2521C', bg='#F4F1EB', grid='#E7E2D9', muted='#C9C2B8',
                     title=SERIF, lead=SERIFM, big=SANS, cap_font=SERIF),
    '講解藍':   dict(kind='explain', ink='#17202E', acc='#2F62B0', bg='#F2F3F5', grid='#E2E5EA', muted='#C2C8D0',
                     title=SERIF, lead=SERIFM, big=SANS, cap_font=SERIF),
    '撕紙':     dict(kind='torn', ink='#24312C', acc='#E0603C', bg='#F4EEE6', dark='#2F4A40', light='#F4EEE6', muted='#D9CFB8',
                     title=SERIF, lead=SERIFM, big=SERIF, cap_font=SERIF),
}
PART_LABEL = {'起': '先講結論', '承': '問題在哪', '轉': '怎麼做', '合': '下一步'}
BOX = {'explain': (80, 470, 1000, 1010), 'soft': (70, 270, 1010, 960), 'swiss': (80, 330, 1000, 975), 'polaroid': (90, 280, 970, 930), 'torn': (60, 270, 1000, 890)}
FACE_H, FACE_BOTTOM, CAP_Y = 520, 1495, 1240


SOFT_CUT = set('了的是要都在把給讓和跟就也還才過著')
NO_START = set('，。、！？；：,.!?;:）」』】》〉…～—')
NO_END = set('（「『【《〈')
def split_at(t):
    """找兩行的斷點：不切開英文數字，優先斷在「了的是…」這類虛字後面，最後才從中間切"""
    n = len(t); ok = [j for j in range(2, n - 1) if not (t[j - 1].isascii() and t[j - 1].isalnum() and t[j].isascii() and t[j].isalnum())]
    ok = [j for j in ok if t[j] not in NO_START and t[j - 1] not in NO_END] or ok   # 標點不放行首、開括號不放行尾
    soft = [j for j in ok if (t[j - 1] in SOFT_CUT or t[j - 1] in NO_START) and n * 0.3 <= j <= n * 0.75]
    return min(soft or ok or [(n + 1) // 2], key=lambda x: abs(x - n / 2))


# 字型裡都沒有的符號換成這些（值是空字串＝直接拿掉）
GLYPH_SUB = {'✓': '√', '✔': '√', '☑': '√', '✅': '√', '✗': '×', '✘': '×', '❌': '×', '★': '★', '☆': '☆', '♥': '', '❤': '', '❤️': '',
             '⭐': '★', '👉': '→', '➡': '→', '▶': '→', '▸': '›', '●': '•', '◆': '•', '■': '•', '\ufe0f': '', '\u200d': ''}


def hexrgb(h):
    if isinstance(h, tuple): return h[:3]
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def out3(x): return 1 - (1 - clamp(x)) ** 3


class Design:
    def __init__(self, r, theme):
        self.r = r; self.D = r.D; self.lines = r.lines
        self.T = dict(DESIGN_THEMES[theme]); self.T.update({k: v for k, v in r.st.items() if k in ('ink', 'acc')})
        self._f = {}; self._c = {}; self._faces = {}; self._cm = {}
        cs = self.fpath('charset-design.txt'); self.chars = set(open(cs, encoding='utf-8').read()) if cs else None
        self.parts = []
        for l in self.lines:
            p = l.get('part')
            if p and p not in self.parts: self.parts.append(p)
        self.bg = self.make_bg()

    # ---------- 字 ----------
    def fpath(self, name):
        for d in FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p): return p
        return None

    def font(self, name, size):
        k = (name, int(size))
        if k not in self._f: self._f[k] = ImageFont.truetype(self.fpath(name) or self.fpath(ROUND), max(8, int(size)))
        return self._f[k]

    def cmap(self, name):
        """這個字型檔真的有哪些字（直接讀字型，不靠字表，避免方塊字）"""
        if name not in self._cm:
            try:
                from fontTools.ttLib import TTFont
                self._cm[name] = set(TTFont(self.fpath(name) or self.fpath(ROUND)).getBestCmap())
            except Exception:
                self._cm[name] = None
        return self._cm[name]

    def has(self, ch, name):
        cm = self.cmap(name)
        if cm is None: return name == ROUND or (self.chars is None or ch in self.chars)
        return ord(ch) in cm

    def clean(self, s):
        """所有字型都沒有的符號：換成長得像的字，換不了就拿掉（不會出現方塊）"""
        out = []
        for ch in s:
            if ch.isspace() or any(self.has(ch, n) for n in (SANS, SERIF, ROUND)): out.append(ch); continue
            rep = GLYPH_SUB.get(ch)
            if rep is not None: out.append(rep)
        return ''.join(out)

    def runs(self, s, name):
        """每個字先用指定字型；那個字型沒有就換粉圓／黑體／宋體；都沒有的符號先換掉或拿掉"""
        s = self.clean(s); out = []
        for ch in s:
            n = name if ch.isspace() or self.has(ch, name) else next((m for m in (ROUND, SANS, SERIF) if self.has(ch, m)), name)
            if out and out[-1][1] == n: out[-1] = (out[-1][0] + ch, n)
            else: out.append((ch, n))
        return out

    def tw(self, s, name, size): return sum(self.font(n, size).getlength(t) for t, n in self.runs(s, name))

    def text(self, d, xy, s, name, size, fill, anchor='la', stroke=0):
        x, y = xy; w = self.tw(s, name, size)
        if anchor[0] == 'm': x -= w / 2
        elif anchor[0] == 'r': x -= w
        for t, n in self.runs(s, name):
            d.text((x, y), t, font=self.font(n, size), fill=fill, anchor='l' + anchor[1], stroke_width=stroke, stroke_fill=fill)
            x += self.font(n, size).getlength(t)
        return w

    def rich(self, d, xy, s, emph, name, size, fill, hl, anchor='la'):
        """重點字換色"""
        marks = [False] * len(s)
        for e in emph or []:
            i = s.find(e)
            while e and i >= 0:
                for j in range(i, i + len(e)): marks[j] = True
                i = s.find(e, i + 1)
        x, y = xy; w = self.tw(s, name, size)
        if anchor[0] == 'm': x -= w / 2
        elif anchor[0] == 'r': x -= w
        k = 0
        while k < len(s):
            j = k
            while j < len(s) and marks[j] == marks[k]: j += 1
            x += self.text(d, (x, y), s[k:j], name, size, hl if marks[k] else fill, 'l' + anchor[1])
            k = j

    def fit(self, s, name, maxsize, maxw): return int(min(maxsize, maxsize * maxw / max(1, self.tw(s, name, maxsize))))

    # ---------- 小零件 ----------
    def rrect(self, img, box, r, fill, outline=None, width=0, shadow=None, soff=(0, 14), blur=20):
        if shadow:
            lay = Image.new('RGBA', img.size, hexrgb(shadow) + (0,))
            ImageDraw.Draw(lay).rounded_rectangle([box[0] + soff[0], box[1] + soff[1], box[2] + soff[0], box[3] + soff[1]], r, fill=shadow)
            img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(blur)) if blur else lay)
        ImageDraw.Draw(img).rounded_rectangle(box, r, fill=fill, outline=outline, width=width)

    def paper(self, size, color, seed=0, torn=True):
        w, h = size; rnd = random.Random(seed); im = Image.new('RGBA', (w, h), hexrgb(color) + (0,))
        if not torn: ImageDraw.Draw(im).rectangle([0, 0, w, h], fill=color); return im
        pts = [(x, rnd.randint(0, 9)) for x in range(0, w + 1, 14)] + [(w - rnd.randint(0, 9), y) for y in range(0, h + 1, 14)]
        pts += [(x, h - rnd.randint(0, 9)) for x in range(w, -1, -14)] + [(rnd.randint(0, 9), y) for y in range(h, -1, -14)]
        ImageDraw.Draw(im).polygon(pts, fill=color); return im

    def place(self, img, piece, xy, rot=0, shadow=True):
        p = piece.rotate(rot, expand=True, resample=Image.BICUBIC) if rot else piece
        if shadow:
            a = p.getchannel('A').filter(ImageFilter.GaussianBlur(10)).point(lambda v: int(v * .28))
            sh = Image.new('RGBA', p.size, (40, 30, 20, 0)); sh.putalpha(a); img.alpha_composite(sh, (int(xy[0] + 6), int(xy[1] + 10)))
        img.alpha_composite(p, (int(xy[0]), int(xy[1])))

    def tape(self, img, cx, cy, w=170, h=52, rot=-12):
        t = Image.new('RGBA', (w, h), (250, 240, 200, 170)).rotate(rot, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(t, (int(cx - t.width / 2), int(cy - t.height / 2)))

    def halftone(self, img, box, color, step=20, rmax=7):
        d = ImageDraw.Draw(img); x0, y0, x1, y1 = box
        for y in range(y0, y1, step):
            for x in range(x0, x1, step):
                r = rmax * (1 - (x - x0) / (x1 - x0)) + 1; d.ellipse([x - r, y - r, x + r, y + r], fill=color)

    def chip(self, s, name, size, fg, bg, seed):
        w = int(self.tw(s, name, size)) + 60; h = int(size * 1.3) + 30
        p = self.paper((w, h), bg, seed=seed); self.text(ImageDraw.Draw(p), (w // 2, h // 2 + 2), s, name, size, fg, 'mm'); return p

    def grain(self, img, amt):
        a = np.asarray(img).astype(np.int16); n = np.random.default_rng(1).integers(-amt, amt + 1, (a.shape[0], a.shape[1], 1))
        a[..., :3] = np.clip(a[..., :3] + n, 0, 255); return Image.fromarray(a.astype(np.uint8), 'RGBA')

    # ---------- 背景 ----------
    def make_bg(self):
        T = self.T; k = T['kind']
        if k == 'soft':
            t = np.linspace(0, 1, H)[:, None, None]; a = np.array(T['g1'])[None, None] * (1 - t) + np.array(T['g2'])[None, None] * t
            img = Image.fromarray(np.repeat(a, W, 1).astype(np.uint8), 'RGB').convert('RGBA')
            lay = Image.new('RGBA', (W, H), T['blob'] + (0,)); d = ImageDraw.Draw(lay)
            d.ellipse([520, 120, 1320, 920], fill=T['blob'] + (150,)); d.ellipse([-300, 1100, 400, 1800], fill=T['blob'] + (150,))
            img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(130))); return img
        img = Image.new('RGBA', (W, H), T['bg']); d = ImageDraw.Draw(img)
        if k == 'explain':
            for x in range(0, W, 54): d.line([(x, 0), (x, H)], fill=T['grid'], width=2)
            for y in range(0, H, 54): d.line([(0, y), (W, y)], fill=T['grid'], width=2)
        if k == 'swiss':
            for x in (80, 380, 680, 1000): d.line([(x, 250), (x, 1470)], fill='#DEDCD5', width=2)
            self.text(d, (80, 262), self.r.st.get('label_l') or 'SHORT VIDEO', SANSM, 30, T['ink'])
            self.text(d, (1000, 262), self.r.st.get('label_r') or 'EP 01', SANSM, 30, T['ink'], 'ra')
            d.line([(80, 310), (1000, 310)], fill=T['ink'], width=3)
        elif k == 'polaroid':
            for x in range(0, W, 60): d.line([(x, 0), (x, H)], fill='#ECE4D8', width=2)
            for y in range(0, H, 60): d.line([(0, y), (W, y)], fill='#ECE4D8', width=2)
        elif k == 'torn':
            self.place(img, self.paper((W + 40, 980), T['dark'], seed=12), (-20, -60), 0)
            img = self.grain(img, 5)
        return img

    # ---------- 開場封面 ----------
    def hook_lines(self):
        hk = self.D.get('hook') or {}
        ls = hk.get('text', '').split('\n') if '\n' in hk.get('text', '') else [hk.get('text', '')]
        tags = [x.strip() for x in re.split(r'[•·|｜]', hk.get('sub', '')) if x.strip()]
        rib = '，'.join(x.strip() for x in re.split(r'[•·]', hk.get('ribbon', '')) if x.strip())
        return ls, tags, rib, hk.get('en', '')

    def cover_layers(self):
        """回傳 [(圖層, 延遲秒)]，一層一層淡入"""
        if 'cover' in self._c: return self._c['cover']
        T = self.T; k = T['kind']; ls, tags, rib, en = self.hook_lines(); ink, acc = T['ink'], T['acc']
        L = [Image.new('RGBA', (W, H), (0, 0, 0, 0)) for _ in range(3)]; D = [ImageDraw.Draw(x) for x in L]
        mw = 900
        if k == 'soft':
            x = 80
            for t in tags[:3]:
                w = self.tw(t, SANSM, 34) + 60; self.rrect(L[0], [x, 270, x + w, 330], 30, None, outline=ink, width=2)
                self.text(D[0], (x + 30, 300), t, SANSM, 34, ink, 'lm'); x += w + 18
            y = 380
            for j, s in enumerate(ls):
                last = j == len(ls) - 1 and len(ls) > 1; sz = self.fit(s, T['title'], 200 if last else 160, mw)
                self.text(D[1], (80, y), s, T['title'], sz, acc if last else ink); y += int(sz * 1.25)
            if en: self.text(D[2], (84, y + 10), en, ITAL, 70, ink); y += 100
            if rib: self.text(D[2], (84, y + 20), rib, T['lead'], 44, ink)
        elif k == 'swiss':
            ImageDraw.Draw(L[0]).ellipse([820, 350, 1000, 530], fill=acc)
            y = 370
            for j, s in enumerate(ls):
                last = j == len(ls) - 1 and len(ls) > 1; sz = self.fit(s, SANS, 160, 700 if j == 0 else 880)
                self.text(D[1], (80, y), s, SANS, sz, acc if last else ink); y += int(sz * 1.22)
            if tags: self.text(D[2], (80, y + 20), '　'.join(tags), SANSM, 40, ink)
            if rib:
                if T.get('collage'):
                    p = self.chip(rib, SANS, 42, ink, '#FFE14D', 91); self.place(L[2], p, (80, y + 90), -3); self.tape(L[2], 120, y + 100, 110, rot=-30)
                    self.halftone(L[0], (790, 600, 1000, 740), acc)
                else: self.text(D[2], (80, y + 80), rib, SANSM, 40, '#888888')
        elif k == 'polaroid':
            pol = self.paper((270, 320), '#FFFFFF', torn=False); pd = ImageDraw.Draw(pol); pd.rectangle([18, 18, 252, 252], fill='#E7D6C4')
            cap = en or (tags[-1] if tags else '')
            self.text(pd, (135, 135), cap, ITAL if en else T['title'], self.fit(cap, ITAL if en else T['title'], 56, 200), '#FFFFFF', 'mm')
            if tags: self.text(pd, (135, 286), tags[-1], T['lead'], self.fit(tags[-1], T['lead'], 28, 230), ink, 'mm')
            self.place(L[0], pol, (690, 250), 7); self.tape(L[0], 830, 262, rot=-6)
            for j, tg in enumerate(tags[:-1] or tags[:1]): self.text(D[0], (80, 290 + j * 64), tg, T['lead'], 44, acc)
            ImageDraw.Draw(L[0]).line([(80, 300 + 64 * max(1, len(tags) - 1)), (240, 300 + 64 * max(1, len(tags) - 1))], fill=acc, width=3)
            y = 620 if len(ls) > 1 else 760
            for j, s in enumerate(ls):
                last = j == len(ls) - 1 and len(ls) > 1; sz = self.fit(s, T['title'], 150 if last else 130, 880)
                self.text(D[1], (80, y), s, T['title'], sz, acc if last else ink); y += int(sz * 1.18)
            if rib:
                lab = self.chip(rib, T['lead'], 36, ink, '#F3D9C9', 8); self.place(L[2], lab, (76, 420), -3)
        elif k == 'torn':
            self.text(D[0], (80, 285), '　·　'.join(tags) if tags else '', T['lead'], 38, T['muted'])
            y = 360
            for j, s in enumerate(ls):
                last = j == len(ls) - 1 and len(ls) > 1
                if last:
                    sz = self.fit(s, T['title'], 150, 820); p = self.chip(s, T['title'], sz, '#FFFFFF', acc, 70); self.place(L[1], p, (60, y - 10), -3); y += p.height + 10
                else:
                    sz = self.fit(s, T['title'], 170, 880); self.text(D[1], (76, y), s, T['title'], sz, T['light']); y += int(sz * 1.2)
            sub = rib or en
            if sub and y + 70 < 860: self.text(D[2], (80, y + 10), sub, ITAL if sub == en else T['lead'], 52 if sub == en else 44, T['muted'])
        self._c['cover'] = [(L[0], 0.0), (L[1], 0.12), (L[2], 0.32)]
        return self._c['cover']

    # ---------- 內容區 ----------
    def container(self):
        if 'box' in self._c: return self._c['box']
        T = self.T; k = T['kind']; img = Image.new('RGBA', (W, H), (0, 0, 0, 0)); x0, y0, x1, y1 = BOX[k]
        if k == 'soft': self.rrect(img, [x0, y0, x1, y1], 40, (255, 255, 255, 165), shadow=(60, 60, 80, 50))
        elif k == 'polaroid':
            note = self.paper((x1 - x0, y1 - y0), '#FFFFFF', torn=False); nd = ImageDraw.Draw(note)
            for y in range(130, y1 - y0, 70): nd.line([(40, y), (x1 - x0 - 40, y)], fill='#EEE6DA', width=2)
            self.place(img, note, (x0, y0), 0); self.tape(img, x0 + 120, y0 + 8, rot=-24); self.tape(img, x1 - 90, y0 + 14, rot=22)
        elif k == 'swiss' and T.get('collage'): self.halftone(img, (700, 360, 1000, 520), T['acc'])
        self._c['box'] = img; return img

    def part_no(self, i):
        p = self.lines[i].get('part'); return (self.parts.index(p) + 1 if p in self.parts else 1), p

    def content_of(self, i):
        L = self.lines[i]; n, p = self.part_no(i)
        labels = dict(PART_LABEL); labels.update(self.r.st.get('part_labels') or {})
        label = L.get('label') or labels.get(p, '')
        same = [l for l in self.lines if l.get('part') == p and l.get('banner')] if p else []
        steps = None
        if L.get('banner') and (len(same) > 1 or re.match(r'^第\s*[0-9一二三四五六七八九十]', L['banner'])):
            rows = [l['banner'] for l in self.lines[:i + 1] if l.get('banner') and l.get('part') == p]
            steps = [re.sub(r'^第\s*([0-9一二三四五六七八九十]+)\s*[步招個點]\s*', '', s) or s for s in rows]
        big = L.get('big')
        if big is None:
            big = L['banner'] if L.get('banner') and not steps else (L.get('emph') or [None])[0]
        lead, tail = L['text'], ''
        if big and '\n' not in big:
            core = big.strip('？?！!。')
            k = L['text'].find(core)
            if k >= 0: lead, tail = L['text'][:k], L['text'][k + len(core):]
            else: lead = ''
        elif big: lead = L['text']
        strip = lambda s: s.strip(' ，,。：:「」『』、')
        plain = False
        if not big and not steps:   # 沒有重點字：整句用大字分兩行，不要只放一行小字
            t = strip(L['text']); m = [q.end() for q in re.finditer(r'[，,、：:]', t)]
            big = (lambda c: t[:c].rstrip('，,、：:') + '\n' + t[c:])(m and min(m, key=lambda x: abs(x - len(t) / 2)) or split_at(t)) if len(t) > 9 else t
            lead = ''; plain = True
        return dict(n=n, label=label, lead=strip(lead), big=big, tail=strip(tail), steps=steps, plain=plain,
                    prop=L.get('prop') if plain else None)

    def content_layers(self, i):
        """[(圖層, 延遲)]：小標、引言、大字分開淡入"""
        C = self.content_of(i); key = ('ct', repr(C))
        if key in self._c: return self._c[key], C
        T = self.T; k = T['kind']; ink, acc = T['ink'], T['acc']; x0, y0, x1, y1 = BOX[k]
        pad = {'soft': 50, 'swiss': 0, 'polaroid': 50, 'torn': 20}[k]; X = x0 + pad; MW = (min(x1, 960) - pad) - X
        Ls = [Image.new('RGBA', (W, H), (0, 0, 0, 0)) for _ in range(3)]; Ds = [ImageDraw.Draw(x) for x in Ls]
        lead_c = T['light'] if k == 'torn' else ink
        # 小標
        y = y0 + 40
        if k == 'soft':
            s = f"{C['label']} {C['n']:02d}"; w = self.tw(s, SANSM, 32) + 56
            self.rrect(Ls[0], [X, y, X + w, y + 60], 30, T['tag']); self.text(Ds[0], (X + w / 2, y + 30), s, SANSM, 32, '#FFFFFF', 'mm'); y += 110
        elif k == 'swiss':
            self.text(Ds[0], (X, y - 20), f"{C['n']:02d}", SANS, 200, acc)
            self.text(Ds[0], (X + 300, y + 30), C['label'], SANS, 56, ink); y += 250
        elif k == 'polaroid':
            self.text(Ds[0], (X, y), f"No.{C['n']:02d} {C['label']}", T['lead'], 40, acc); y += 100
        else:
            self.text(Ds[0], (X, y - 10), f"NO.{C['n']:02d} ── {C['label']}", T['lead'], 40, T['muted']); y += 90
        ytop, ybot = y, y1 - (60 if k != 'swiss' else 20)

        def body(Ls, Ds, y, sc):
            """畫引言／大字／步驟，回傳底部 y；sc 是縮放（放不下就縮小）"""
            if C['steps']:
                rh = int(118 * sc)
                for r, s in enumerate(C['steps']):
                    cur = r == len(C['steps']) - 1; cy = y + r * rh + rh // 2; D = Ds[1 if cur else 0]
                    col = (acc if cur else (T['muted'] if k == 'torn' else '#B8B0A8'))
                    D.ellipse([X, cy - 32, X + 64, cy + 32], fill=col); self.text(D, (X + 32, cy), str(r + 1), SANS, 38, '#FFFFFF', 'mm')
                    fz = self.fit(s, T['big'] if cur else T['lead'], (80 if cur else 60) * sc, MW - 100)
                    self.text(D, (X + 96, cy), s, T['big'] if cur else T['lead'], fz, lead_c if cur else (T['muted'] if k == 'torn' else '#9A928A'), 'lm')
                return y + len(C['steps']) * rh
            if C['lead']:
                sz = self.fit(C['lead'], T['lead'], (88 if C['big'] else 96) * sc, MW); self.text(Ds[1], (X, y), C['lead'], T['lead'], sz, lead_c); y += int(sz * 1.45)
            if C['big']:
                bl = C['big'].split('\n'); n = len(bl)
                for j, s in enumerate(bl):
                    mx = (130 if C['plain'] else 220 if n == 1 else 160) * sc
                    sz = self.fit(s, T['big'], mx, MW - (60 if k == 'torn' else 0)); last = j == n - 1
                    if k == 'torn' and not C['plain']:
                        pc = self.chip(s, T['big'], sz, '#FFFFFF', acc, 80 + j); self.place(Ls[2], pc, (X - 10, y - 14), -2); y += pc.height + 6
                        continue
                    col = lead_c if C['plain'] else acc if k == 'soft' else ink
                    if k == 'polaroid' and last and not C['plain']: ImageDraw.Draw(Ls[2]).rectangle([X, y + int(sz * 1.12), X + self.tw(s, T['big'], sz), y + int(sz * 1.24)], fill='#F3C9B4')
                    self.text(Ds[2], (X, y), s, T['big'], sz, col)
                    if k == 'swiss' and last and not C['plain']: Ds[2].rectangle([X, y + int(sz * 1.32), X + 300, y + int(sz * 1.32) + 12], fill=acc)
                    y += int(sz * (1.3 if n == 1 else 1.22))
                if k == 'soft' and not C['plain']: Ds[2].line([(X + 4, y + 20), (x1 - 50, y + 20)], fill=T['line'], width=2); y += 40
            if C['tail']:
                self.text(Ds[2], (X + 4, y + 20), C['tail'], T['lead'], 46 * sc, T['muted'] if k == 'torn' else '#7A706A'); y += int(80 * sc)
            if C['prop']:
                pp = find_prop(C['prop'] if isinstance(C['prop'], str) else C['prop'][0],
                               [os.path.join(self.r.base, 'props'), os.path.join(self.r.base, '..', '..', 'props')])
                if pp:
                    im = ImageOps.contain(Image.open(pp).convert('RGBA'), (int(300 * sc), int(300 * sc)), Image.LANCZOS)
                    Ls[2].alpha_composite(im, (int((x0 + min(x1, 960)) / 2 - im.width / 2), int(y + 20))); y += im.height + 20
            return y

        dummy = [Image.new('RGBA', (W, H)) for _ in range(3)]
        h = body(dummy, [ImageDraw.Draw(x) for x in dummy], 0, 1.0); sc = 1.0
        if h > ybot - ytop: sc = (ybot - ytop) / h; h = body(dummy, [ImageDraw.Draw(x) for x in dummy], 0, sc)
        yy = ytop + (0 if C['steps'] else max(0, (ybot - ytop - h) // 2))
        body(Ls, Ds, yy, sc)
        self._c[key] = [(Ls[0], 0.0), (Ls[1], 0.08), (Ls[2], 0.18)]
        return self._c[key], C

    # ---------- 人物 ----------
    def face(self, key, talk):
        k = (key, talk)
        if k in self._faces: return self._faces[k]
        r = self.r; im = r.face(key, talk)
        if im is None: self._faces[k] = None; return None
        s = FACE_H / im.height
        im = im.resize((max(1, int(im.width * s)), FACE_H), Image.LANCZOS)
        self._faces[k] = im; return im

    def side_of(self, i, t):
        hk = self.D.get('hook')
        if hk and t < hk.get('until', 3.0): return self.r.st.get('cover_side', 'r')
        n, _ = self.part_no(i); return 'r' if n % 2 == 1 else 'l'

    def face_x(self, side, w): return W - w + 20 if side == 'r' else -20

    # ---------- 字幕 ----------
    def caption(self, c, emph, side, fw):
        key = ('cap', c, tuple(emph), side)
        if key in self._c: return self._c[key]
        T = self.T; k = T['kind']; ink, acc = T['ink'], T['acc']
        col_w = (W - fw - 20 - 70 - 30) if side == 'r' else (960 - (fw - 20) - 30)
        size = 62; f = T['cap_font']; pad = 30
        lines = [c]
        if self.tw(c, f, size) > col_w - 2 * pad:   # 先縮字（最小 50），還放不下才分兩行
            size = max(50, self.fit(c, f, size, col_w - 2 * pad))
        if self.tw(c, f, size) > col_w - 2 * pad:
            h = split_at(c); lines = [c[:h], c[h:]]
            size = min(size, self.fit(max(lines, key=len), f, size, col_w - 2 * pad))
        tw = max(self.tw(s, f, size) for s in lines); lh = int(size * 1.4)
        bw, bh = int(tw + 2 * pad), lh * len(lines) + 24
        im = Image.new('RGBA', (bw + 30, bh + 30), (0, 0, 0, 0))
        if k == 'soft': self.rrect(im, [0, 0, bw, bh], 34, (255, 255, 255, 235), shadow=(0, 0, 0, 40), soff=(0, 8), blur=8); fg, hl = ink, acc
        elif k == 'swiss': ImageDraw.Draw(im).rectangle([0, 0, bw, bh], fill=ink); fg, hl = '#FFFFFF', '#FF7A6E'
        elif k == 'polaroid': self.rrect(im, [0, 0, bw, bh], 6, '#FFFFFF', shadow=(0, 0, 0, 45), soff=(4, 8), blur=8); fg, hl = ink, acc
        else: ImageDraw.Draw(im).rectangle([0, 0, bw, bh], fill=ink); fg, hl = T['light'], '#FFC9A8'
        d = ImageDraw.Draw(im)
        for j, s in enumerate(lines): self.rich(d, (pad, 12 + j * lh + lh // 2), s, emph, f, size, fg, hl, 'lm')
        if k == 'polaroid': self.tape(im, bw // 2, 8, 110, 36, rot=-4)
        self._c[key] = im; return im

    def media_photo(self, i):
        """照片素材：裁成內容區的大小（圓角），填滿不留白邊；影片素材回傳 None 走原本的卡片"""
        m = self.lines[i]['media']; f = m['file'] if isinstance(m, dict) else m
        if f.lower().endswith(('.mp4', '.mov', '.m4v', '.webm', '.mkv', '.gif')): return None
        key = ('photo', i)
        if key not in self._c:
            x0, y0, x1, y1 = BOX[self.T['kind']]; w, h = x1 - x0 - 40, y1 - y0 - 40
            im = Image.open(self.r.media_path(m)).convert('RGB')
            im = ImageOps.exif_transpose(im) if hasattr(ImageOps, 'exif_transpose') else im
            im = ImageOps.fit(im, (w, h), Image.LANCZOS, centering=(0.5, 0.5)).convert('RGBA')
            mask = Image.new('L', (w, h), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], 28, fill=255); im.putalpha(mask)
            self._c[key] = im
        return self._c[key]

    def name_tag(self):
        """人物下方的小名牌（style.footer，例如「于葳影音｜網紅陪跑製造機」）"""
        txt = self.r.st.get('footer')
        if not txt: return None
        if 'tag' in self._c: return self._c['tag']
        T = self.T; k = T['kind']; f = SANSM if k == 'swiss' else T['lead']; size = 30
        w = int(self.tw(txt, f, size)) + 48; h = 56
        im = Image.new('RGBA', (w + 16, h + 16), (0, 0, 0, 0))
        if k == 'soft': self.rrect(im, [0, 0, w, h], 28, (255, 255, 255, 235), shadow=(0, 0, 0, 40), soff=(0, 6), blur=6); fg = T['ink']
        elif k == 'polaroid': self.rrect(im, [0, 0, w, h], 4, '#FFFFFF', shadow=(0, 0, 0, 45), soff=(3, 6), blur=6); fg = T['ink']
        else: ImageDraw.Draw(im).rectangle([0, 0, w, h], fill=T['ink']); fg = T.get('light', '#FFFFFF')
        self.text(ImageDraw.Draw(im), (w / 2, h / 2), txt, f, size, fg, 'mm')
        self._c['tag'] = im; return im

    def put_tag(self, scene, fx, fw):
        tag = self.name_tag()
        if tag is None: return
        cx = min(max(fx + fw / 2, 30 + tag.width / 2), 960 - tag.width / 2)
        scene.alpha_composite(tag, (int(cx - tag.width / 2), int(FACE_BOTTOM - 95)))

    def cover_image(self):
        """封面：背景＋開場標題全部顯示＋人物（第一句的表情），不放字幕"""
        img = self.bg.copy()
        for lay, _ in self.cover_layers(): img.alpha_composite(lay)
        im = self.face(self.lines[0].get('face', 'neutral'), False); side = self.r.st.get('cover_side', 'r')
        img.alpha_composite(im, (int(self.face_x(side, im.width)), int(FACE_BOTTOM - im.height)))
        self.put_tag(img, self.face_x(side, im.width), im.width)
        return img.convert('RGB')

    # ---------- 一格 ----------
    @staticmethod
    def fade(img, a, dy=0):
        if a >= 1 and not dy: return img
        if a < 1: img = img.copy(); img.putalpha(img.getchannel('A').point(lambda v: int(v * max(0, a))))
        return img

    def frame(self, fi):
        r = self.r; t = fi / FPS; i = r.line_at(t); L = self.lines[i]; lt = t - L['start']
        scene = self.bg.copy()
        hk = self.D.get('hook'); u = hk.get('until', 3.0) if hk else -1
        mode = r.media_mode(i)
        if mode == 'full':
            mf = r.media_frame(i, lt, 'full')
            if mf is not None:
                mf = mf if r.S == 1 else mf.resize((W, H), Image.BILINEAR)
                a = 1.0 if (i > 0 and r.media_mode(i - 1) == 'full') else clamp(lt / 0.25); scene.alpha_composite(self.fade(mf, a))
        # 開場封面
        if hk and t < u + 0.35:
            out = 1 - out3((t - u) / 0.25) if t > u else 1.0
            for lay, dl in self.cover_layers():
                a = clamp((t - dl) / 0.35) * out
                if a > 0: scene.alpha_composite(self.fade(lay, a), (0, int(24 * (1 - out3((t - dl) / 0.45)))))
        # 內容區
        if t >= u and mode != 'full':
            a = clamp((t - u - 0.1) / 0.3) if hk else 1.0
            scene.alpha_composite(self.fade(self.container(), a))
            if mode == 'card':
                mc = self.media_photo(i)
                if mc is None:
                    mc = r.media_frame(i, lt, 'card')
                    if mc is not None and r.S != 1: mc = mc.resize((int(mc.width / r.S), int(mc.height / r.S)), Image.BILINEAR)
                if mc is not None:
                    x0, y0, x1, y1 = BOX[self.T['kind']]
                    mc = ImageOps.contain(mc, (x1 - x0 - 20, y1 - y0 - 20), Image.BILINEAR)
                    k = clamp(lt / 0.3); scene.alpha_composite(self.fade(mc, k), (int((x0 + x1) / 2 - mc.width / 2), int((y0 + y1) / 2 - mc.height / 2 + 20 * (1 - out3(lt / 0.35)))))
            else:
                lays, C = self.content_layers(i)
                prev = self.content_layers(i - 1)[1] if i > 0 else None
                since = min(lt, t - u - 0.25)
                for j, (lay, dl) in enumerate(lays):
                    same = prev is not None and j == 0 and prev['n'] == C['n'] and prev['label'] == C['label']
                    if same or (C['steps'] and prev and prev.get('steps') and j == 0): scene.alpha_composite(lay); continue
                    tj = since - dl; a = clamp(tj / 0.3)
                    if a > 0: scene.alpha_composite(self.fade(lay, a), (0, int(22 * (1 - out3(tj / 0.4)))))
        # 人物（每個段落換邊，平順移過去）
        talking = r.st.get('talk') and r.raw_env[min(fi, len(r.raw_env) - 1)] > 0.32 and L['start'] <= t <= L['end']
        fname = L.get('face', 'neutral')
        im = self.face(fname, True) if talking and (fi // 3) % 3 != 2 else None
        im = im or self.face(fname, False)
        s1 = self.side_of(i, t); s0 = self.side_of(i - 1, L['start'] - 0.01) if i > 0 else s1
        if hk and u <= t < u + 0.5: s0 = self.side_of(i, u - 0.01); kk = out3((t - u) / 0.5)
        else: kk = out3(lt / 0.5)
        x = self.face_x(s0, im.width) + (self.face_x(s1, im.width) - self.face_x(s0, im.width)) * kk
        prevf = self.lines[i - 1].get('face') if i > 0 else None
        if prevf != fname and lt < 0.3:
            sc = 0.97 + 0.03 * out3(lt / 0.3); im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
            x += (im.width / sc - im.width) / 2
        scene.alpha_composite(im, (int(x), int(FACE_BOTTOM - im.height)))
        self.put_tag(scene, x, im.width)
        # 字幕：放在人物旁邊的空位
        side = s1 if kk > 0.5 else s0
        for (a0, a1, c, emph) in r.cplan:
            if a0 <= t < a1:
                cap = self.caption(c, emph, side, im.width); a = clamp((t - a0) / 0.16)
                fx = self.face_x(side, im.width)
                if side == 'r': cx = (70 + fx - 30) / 2
                else: cx = (fx + im.width + 30 + 960) / 2
                scene.alpha_composite(self.fade(cap, a), (int(cx - cap.width / 2), int(CAP_Y - cap.height / 2 + 10 * (1 - out3((t - a0) / 0.2)))))
        out = scene.convert('RGB')
        return out if r.S == 1 else out.resize((r.w, r.h), Image.LANCZOS)


def back(x, s=1.7):
    x = clamp(x) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2


class Explain(Design):
    """講解卡片：上方逐字變色字幕（講到哪個字變深色、重點詞套色塊）＋段落小標＋中間卡片／標籤／手機畫面一個一個彈出＋白邊貼紙人物左右換位。
    節奏：每句 2～3 個元素，間隔約 0.3～0.5 秒彈出（參考爆款講解型短影音）。"""
    CAP_TOP = 300

    # ---------- 上方步驟進度條（有「第1步、第2步…」時，從第一步開始一直顯示） ----------
    def all_steps(self):
        if 'steps_all' in self._c: return self._c['steps_all']
        best = (None, [])
        for p in self.parts:
            rows = [(k, l['banner']) for k, l in enumerate(self.lines) if l.get('part') == p and l.get('banner')]
            if len(rows) >= 2 and len(rows) > len(best[1]): best = (p, rows)
        names = [re.sub(r'^第\s*([0-9一二三四五六七八九十]+)\s*[步招個點]\s*', '', b) or b for _, b in best[1]]
        first = best[1][0][0] if best[1] else None
        self._c['steps_all'] = (first, [k for k, _ in best[1]], names); return self._c['steps_all']

    def step_state(self, i):
        """回傳 (目前第幾步, 名稱清單)；還沒到步驟段就回 None"""
        first, idx, names = self.all_steps()
        if first is None or i < first or self.r.st.get('progress') is False: return None
        return sum(1 for k in idx if k <= i), names

    def cap_top(self, i): return self.CAP_TOP + (120 if self.step_state(i) else 0)

    def progress_bar(self, i, since):
        st = self.step_state(i)
        if not st: return None
        cur, names = st; n = len(names); T = self.T; ink, acc, mut = hexrgb(T['ink']), hexrgb(T['acc']), hexrgb(T['muted'])
        im = Image.new('RGBA', (W, 130), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x0, x1, y = 130, W - 130, 40; xs = [x0 + (x1 - x0) * k / max(1, n - 1) for k in range(n)]
        d.line([(x0, y), (x1, y)], fill=mut + (150,), width=4)
        prog = clamp(since / 0.4)          # 進到新的一步：線往前長過去
        reach = xs[max(0, cur - 2)] + (xs[cur - 1] - xs[max(0, cur - 2)]) * prog if cur >= 1 else x0
        d.line([(x0, y), (reach, y)], fill=acc + (255,), width=6)
        for k, x in enumerate(xs):
            num = k + 1; r = 24 if num == cur else 18
            if num < cur:
                d.ellipse([x - r, y - r, x + r, y + r], fill=acc + (255,))
                d.line([(x - 8, y), (x - 2, y + 7), (x + 9, y - 7)], fill='#FFFFFF', width=4, joint='curve')
            elif num == cur:
                d.ellipse([x - r - 6, y - r - 6, x + r + 6, y + r + 6], fill=acc + (60,))
                d.ellipse([x - r, y - r, x + r, y + r], fill=ink + (255,)); self.text(d, (x, y), str(num), SANS, 26, '#FFFFFF', 'mm')
            else:
                d.ellipse([x - r, y - r, x + r, y + r], fill='#FFFFFF', outline=mut + (255,), width=3); self.text(d, (x, y), str(num), SANS, 22, T['muted'], 'mm')
            lab = names[k][:5]; fz = 24
            self.text(d, (x, y + 52), lab, SANSM if num == cur else SANSM, fz, T['ink'] if num <= cur else T['muted'], 'mm')
        return im

    # ---------- 上方逐字字幕 ----------
    def karaoke_lines(self, text):
        f, size = self.T['cap_font'], 62
        if self.tw(text, f, size) <= 900: return [text], size
        h = split_at(text); ls = [text[:h], text[h:]]
        return ls, min(size, self.fit(max(ls, key=len), f, size, 900))

    def draw_karaoke(self, scene, i, t):
        L = self.lines[i]; T = self.T; text = L['text']; f = T['cap_font']
        ls, size = self.karaoke_lines(text)
        p = clamp((t - L['start']) / max(0.3, (L['end'] - L['start']) * 0.92)); n = len(text); shown = p * n
        marks = [False] * n
        for e in L.get('emph') or []:
            k = text.find(e)
            while e and k >= 0:
                for j in range(k, k + len(e)): marks[j] = True
                k = text.find(e, k + 1)
        d = ImageDraw.Draw(scene); idx = 0; y = self.cap_top(i); lh = int(size * 1.45)
        ink, mut, acc = hexrgb(T['ink']), hexrgb(T['muted']), hexrgb(T['acc'])
        for ln in ls:
            x = W / 2 - self.tw(ln, f, size) / 2; j = 0
            while j < len(ln):   # 重點詞：講到就套色塊
                gi = idx + j
                if marks[gi]:
                    e = j
                    while e < len(ln) and marks[idx + e]: e += 1
                    seg = ln[j:e]; w = self.tw(seg, f, size); a = clamp((shown - gi) / max(1, len(seg)))
                    if a > 0:   # 螢光筆底線：跟著講的速度由左往右畫過去
                        band = Image.new('RGBA', scene.size, (0, 0, 0, 0))
                        ImageDraw.Draw(band).rounded_rectangle([x - 4, y + size * 0.08, x - 4 + (w + 8) * a, y + size * 0.52], 6, fill=acc + (70,))
                        scene.alpha_composite(band); d = ImageDraw.Draw(scene)
                    for c in seg:
                        k = clamp(shown - (idx + j)); col = tuple(int(mut[q] + (acc[q] - mut[q]) * k) for q in range(3))
                        x += self.text(d, (x, y), c, f, size, col, 'lm'); j += 1
                    continue
                c = ln[j]; k = clamp(shown - gi)
                col = tuple(int(mut[q] + (ink[q] - mut[q]) * k) for q in range(3))
                x += self.text(d, (x, y), c, f, size, col, 'lm'); j += 1
            idx += len(ln); y += lh
        return y - lh + size * 0.7

    def badge(self, i):
        C = self.content_of(i); key = ('badge', C['n'], C['label'])
        if key in self._c: return self._c[key]
        T = self.T; s = C['label']; fz = 32
        w = int(self.tw(s, SANSM, fz)) + 110; h = 58; im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=T['ink'])
        d.ellipse([10, 9, 50, 49], fill='#FFFFFF'); self.text(d, (30, 29), f"{C['n']:02d}", SANS, 22, T['ink'], 'mm')
        self.text(d, (64, 29), s, SANSM, fz, '#FFFFFF', 'lm'); self._c[key] = im; return im

    # ---------- 元素 ----------
    def white_card(self, w, h, rot=0, r=24):
        im = Image.new('RGBA', (w + 60, h + 60), (0, 0, 0, 0))
        self.rrect(im, [30, 30, 30 + w, 30 + h], r, '#FFFFFF', shadow=(60, 40, 20, 55), soff=(0, 12), blur=14)
        return im, (lambda img: img.rotate(rot, expand=True, resample=Image.BICUBIC) if rot else img)

    def label_block(self, s, maxw=720, size=120, rot=-3):
        """重點大字：思源宋體粗字＋重點色、下半部淡色螢光筆底（不轉斜、不用實心色塊）。rot 保留參數相容，不使用。"""
        T = self.T; acc = hexrgb(T['acc']); sz = self.fit(s, SERIF, size, maxw - 60)
        tw = int(self.tw(s, SERIF, sz)); w = tw + 60; h = int(sz * 1.5)
        im = Image.new('RGBA', (w + 40, h + 40), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        x0, cy = 50, 20 + h / 2
        d.rounded_rectangle([x0 - 10, cy + sz * 0.02, x0 + tw + 10, cy + sz * 0.5], int(sz * 0.12), fill=acc + (55,))
        self.text(d, (x0, cy), s, SERIF, sz, T['acc'], 'lm')
        return im

    def text_card(self, s, size=60, w=700, rot=0, bars=2):
        T = self.T; lines = s.split('\n') if '\n' in s else [s]
        sz = min(self.fit(max(lines, key=len), T['lead'], size, w - 90), size); lh = int(sz * 1.4)
        h = 60 + lh * len(lines) + bars * 34 + 20
        im, rotf = self.white_card(w, h, 0); d = ImageDraw.Draw(im)
        for j, ln in enumerate(lines): self.text(d, (75, 30 + 40 + j * lh + lh // 2), ln, T['lead'], sz, T['ink'], 'lm')
        y = 30 + 40 + lh * len(lines) + 16
        for b in range(bars): d.rounded_rectangle([75, y + b * 34, 75 + int((w - 150) * (0.9 - 0.25 * b)), y + b * 34 + 14], 7, fill='#ECE8E1')
        return rotf(im) if rot else im

    def phone(self, photo, w=330, h=600):
        im = Image.new('RGBA', (w + 60, h + 60), (0, 0, 0, 0))
        self.rrect(im, [30, 30, 30 + w, 30 + h], 44, '#1B1B1B', shadow=(0, 0, 0, 80), soff=(0, 14), blur=16)
        sw, sh = w - 24, h - 24; ph = ImageOps.fit(photo.convert('RGB'), (sw, sh), Image.LANCZOS).convert('RGBA')
        m = Image.new('L', (sw, sh), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], 34, fill=255); ph.putalpha(m)
        im.alpha_composite(ph, (42, 42)); return im

    def checklist(self, i):
        C = self.content_of(i); T = self.T; rows = C['steps']; w = 720; rh = 92
        h = 110 + rh * len(rows) + 30
        im, _ = self.white_card(w, h); d = ImageDraw.Draw(im)
        chip = C['label']; cw = self.tw(chip, SANSM, 28) + 76; ac = hexrgb(T['acc'])
        d.rounded_rectangle([60, 55, 60 + cw, 101], 23, fill=ac + (40,))
        d.line([(82, 79), (90, 87), (104, 70)], fill=ac + (255,), width=5, joint='curve')   # 打勾用畫的，不靠字型
        self.text(d, (116, 78), chip, SANSM, 28, T['acc'], 'lm')
        for r, s in enumerate(rows):
            cy = 30 + 110 + r * rh + rh // 2; cur = r == len(rows) - 1
            d.ellipse([60, cy - 24, 108, cy + 24], fill=T['ink'] if cur else '#D9D4CC'); self.text(d, (84, cy), str(r + 1), SANS, 26, '#FFFFFF', 'mm')
            fz = self.fit(s, SANS if cur else T['lead'], 60 if cur else 48, w - 190)
            self.text(d, (132, cy), s, SANS if cur else T['lead'], fz, T['ink'] if cur else '#9A928A', 'lm')
        return im

    def side(self, i):
        hk = self.D.get('hook')
        if hk and self.lines[i]['start'] < hk.get('until', 3.0) - 0.2: return 'r'
        return 'r' if i % 2 == 0 else 'l'

    def person_box(self, i):
        """這句人物實際占的範圍（用透明度算，髮飾、頭髮也算進去）"""
        im = self.face(self.lines[i].get('face', 'neutral'), False)
        if im is None: return None
        x = self.face_x(self.side(i), im.width); y = FACE_BOTTOM - im.height
        bb = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox() or (0, 0, im.width, im.height)
        return (x + bb[0], y + bb[1], x + bb[2], y + bb[3])

    def content_top(self, i):
        ls, size = self.karaoke_lines(self.lines[i]['text'])
        yb = self.cap_top(i) + (len(ls) - 1) * int(size * 1.45) + size * 0.7
        return int(yb + 40 + 58 + 14)            # 小標下面再留空，卡片自帶 30px 陰影邊

    def stack(self, items, i, top, bottom=1470, margin=40, gap=6):
        """由上往下排，不重疊：跟人物同高度的部分只用人物旁邊的空欄，太寬就縮小，整體超出底線就整組縮小"""
        P = self.person_box(i); sd = self.side(i)
        for sc in [1.0, 0.92, 0.85, 0.78, 0.72, 0.66, 0.6]:
            out, y = [], top
            for it in items:
                im = it['im']
                if sc < 1: im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS)
                y += int(it.get('gap', gap) * sc)
                def rng(h):
                    if P and y + h > P[1] + 30:
                        return (P[2] + 10, W - margin) if sd == 'l' else (margin, P[0] - 10)
                    return (margin, W - margin)
                x0, x1 = rng(im.height)
                if im.width > x1 - x0:
                    k = max(0.55, (x1 - x0) / im.width); im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)
                    x0, x1 = rng(im.height)
                al = it.get('align', 'c')
                cx = (x0 + im.width / 2) if al == 'l' else (x1 - im.width / 2) if al == 'r' else (x0 + x1) / 2
                if al == 'c' and (x1 - x0) > 900: cx = (x0 + x1) / 2 + (40 if sd == 'r' else -40) * 0   # 全寬時置中
                out.append((im, cx, y + im.height / 2, it['delay'], it.get('kind', ''))); y += im.height
            if y <= bottom: return out, y
        return out, y

    def elements(self, i):
        """這句要彈出的元素：[(圖, 中心 x, 中心 y, 延遲秒)]，用 stack() 排版，保證不互相重疊、不壓到人物"""
        key = ('el', i)
        if key in self._c: return self._c[key]
        L = self.lines[i]; C = self.content_of(i); sd = self.side(i); items = []
        mode = self.r.media_mode(i)
        if mode == 'card' and self.media_photo(i) is not None:
            tag = C['big'].replace('\n', ' ') if C['big'] and not C['plain'] else (L.get('emph') or [''])[0]
            if tag: items.append(dict(im=self.label_block(tag, 640, 90), delay=0.35))
            items.append(dict(im=self.phone(Image.open(self.r.media_path(L['media']))), delay=0.0))
        elif C['steps']:
            items.append(dict(im=self.checklist(i), delay=0.0))
        elif C['big'] and not C['plain']:
            big = C['big'].replace('\n', '・')
            if C['lead']:
                items.append(dict(im=self.text_card(C['lead'], 58, 760), delay=0.0))
                items.append(dict(im=self.label_block(big, 900, 120), delay=0.3, gap=0))
            else:
                items.append(dict(im=self.label_block(big, 900, 130), delay=0.0))
            if C['tail']: items.append(dict(im=self.text_card(C['tail'], 44, 560, 0, 1), delay=0.6, gap=0))
        else:
            items.append(dict(im=self.text_card(C['big'], 70, 800, 0, 2), delay=0.0))
        st = L.get('stamp')
        if st:
            sz = 60; w = int(self.tw(st, SANS, sz)) + 60; h = int(sz * 1.5)
            im = Image.new('RGBA', (w + 20, h + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            d.rounded_rectangle([10, 10, 10 + w, 10 + h], 10, fill='#FFFFFFE6', outline='#D23A2A', width=7); self.text(d, (10 + w / 2, 10 + h / 2), st, SANS, sz, '#D23A2A', 'mm')
            items.append(dict(im=im.rotate(6, expand=True, resample=Image.BICUBIC), delay=0.75, align='r' if sd == 'l' else 'l', gap=4, kind='stamp'))
        els, bottom = self.stack(items, i, self.content_top(i))
        prop = L.get('prop')
        if prop and mode != 'card' and not C['steps']:
            pp = find_prop(prop if isinstance(prop, str) else prop[0], [os.path.join(self.r.base, 'props'), os.path.join(self.r.base, '..', '..', 'props')])
            if pp:
                im = ImageOps.contain(Image.open(pp).convert('RGBA'), (140, 140), Image.LANCZOS)
                P = self.person_box(i); boxes = [(cx - e.width / 2, cy - e.height / 2, cx + e.width / 2, cy + e.height / 2) for e, cx, cy, *_ in els] + ([P] if P else [])
                fx = 200 if sd == 'r' else W - 200
                for cy in (1340, bottom + 110, 1200):
                    bx = (fx - 90, cy - 90, fx + 90, cy + 90)
                    if cy < 1450 and not any(bx[0] < b[2] and b[0] < bx[2] and bx[1] < b[3] and b[1] < bx[3] for b in boxes):
                        els.append((im, fx, cy, 0.55)); break
        self._c[key] = els; return els

    # ---------- 封面 ----------
    def cover_layers(self):
        if 'cover' in self._c: return self._c['cover']
        T = self.T; ls, tags, rib, en = self.hook_lines()
        L = [Image.new('RGBA', (W, H), (0, 0, 0, 0)) for _ in range(3)]; D = [ImageDraw.Draw(x) for x in L]
        x = 80
        for tg in tags[:3]:
            w = self.tw(tg, SANSM, 34) + 56; D[0].rounded_rectangle([x, 290, x + w, 350], 30, fill=T['ink'])
            self.text(D[0], (x + w / 2, 320), tg, SANSM, 34, '#FFFFFF', 'mm'); x += w + 16
        y = 410
        for j, s in enumerate(ls):
            last = j == len(ls) - 1 and len(ls) > 1
            if last:
                b = self.label_block(s, 900, 170, -3); L[1].alpha_composite(b, (60, y - 20)); y += b.height
            else:
                sz = self.fit(s, T['title'], 170, 900); self.text(D[1], (80, y), s, T['title'], sz, T['ink']); y += int(sz * 1.3)
        if rib: self.text(D[2], (84, y + 10), rib, T['lead'], 46, T['ink'])
        self._c['cover'] = [(L[0], 0.0), (L[1], 0.12), (L[2], 0.35)]
        return self._c['cover']

    def cover_image(self):
        img = self.bg.copy()
        for lay, _ in self.cover_layers(): img.alpha_composite(lay)
        im = self.face(self.lines[0].get('face', 'neutral'), False)
        img.alpha_composite(im, (int(self.face_x('r', im.width)), int(FACE_BOTTOM - im.height)))
        self.put_tag(img, self.face_x('r', im.width), im.width)
        return img.convert('RGB')

    def face(self, key, talk):
        k = ('xf', key, talk)
        if k in self._faces: return self._faces[k]
        im = self.r.face(key, talk)
        if im is None: self._faces[k] = None; return None
        h = 600; w = im.width * h / im.height
        if w > 480: h = int(h * 480 / w); w = 480      # 髮型、頭飾很寬的照片整個縮小，人物是配角，留空間給字
        im = im.resize((max(1, int(w)), h), Image.LANCZOS)
        self._faces[k] = im; return im

    # ---------- 一格 ----------
    def frame(self, fi):
        r = self.r; t = fi / FPS; i = r.line_at(t); L = self.lines[i]; lt = t - L['start']
        scene = self.bg.copy(); hk = self.D.get('hook'); u = hk.get('until', 3.0) if hk else -1
        if hk and t < u + 0.25:
            out = 1 - out3((t - u) / 0.25) if t > u else 1.0
            for lay, dl in self.cover_layers():
                k = back((t - dl) / 0.35) if t < u else 1.0; a = clamp((t - dl) / 0.15) * out
                if a <= 0: continue
                if abs(k - 1) > 0.01:
                    sc = 0.9 + 0.1 * k; lay2 = lay.resize((int(W * sc), int(H * sc)), Image.BILINEAR); ox, oy = (W - lay2.width) // 2, int((H - lay2.height) * 0.2)
                    scene.alpha_composite(self.fade(lay2, a), (ox, oy))
                else: scene.alpha_composite(self.fade(lay, a))
        if t >= u:
            since = min(lt, t - u)
            pb = self.progress_bar(i, since if (i == 0 or self.step_state(i) != self.step_state(i - 1)) else 9)
            if pb is not None: scene.alpha_composite(pb, (0, 240))
            yb = self.draw_karaoke(scene, i, t)
            bd = self.badge(i); prevb = self.badge(i - 1) if i > 0 else None
            a = 1.0 if (prevb is bd and t - u > 0.3) else clamp(since / 0.2)
            scene.alpha_composite(self.fade(bd, a), (80, int(yb + 40)))
            prev_steps = i > 0 and self.content_of(i - 1)['steps'] and self.content_of(i)['steps']
            for e in self.elements(i):
                im, cx, cy, dl = e[:4]; kind = e[4] if len(e) > 4 else ''
                tj = since - dl
                if tj <= 0: continue
                k = 1.0 if (prev_steps and dl == 0) else back(tj / 0.32); a = clamp(tj / 0.12)
                if kind == 'stamp':   # 印章：從大大的蓋下來，落地時輕輕一震
                    k = 1 + 0.9 * (1 - out3(tj / 0.22)); a = clamp(tj / 0.08)
                    if 0.22 < tj < 0.4: cx += 6 * math.sin(tj * 90)
                q = im if abs(k - 1) < 0.01 else im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.BILINEAR)
                scene.alpha_composite(self.fade(q, a), (int(cx - q.width / 2), int(cy - q.height / 2)))
        # 人物：白邊貼紙，換位置或換表情時彈一下
        fname = L.get('face', 'neutral'); im = self.face(fname, False)
        sd = self.side(i); psd = self.side(i - 1) if i > 0 else sd
        pf = self.lines[i - 1].get('face') if i > 0 else None
        x = self.face_x(sd, im.width)
        if self.r.st.get('blob', True):   # 頭後面一個淡淡的圓，人物比較跳
            P = self.person_box(i)
            if P:
                rr = int((P[2] - P[0]) * 0.42); hx, hy = (P[0] + P[2]) / 2, P[1] + (P[3] - P[1]) * 0.36
                bl = Image.new('RGBA', scene.size, (0, 0, 0, 0)); ImageDraw.Draw(bl).ellipse([hx - rr, hy - rr, hx + rr, hy + rr], fill=hexrgb(self.T['acc']) + (34,))
                scene.alpha_composite(bl)
        if (sd != psd or pf != fname or i == 0) and lt < 0.35:
            k = back(lt / 0.3, 2.0); sc = 0.8 + 0.2 * k
            q = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
            scene.alpha_composite(q, (int(x + (im.width - q.width) / 2), int(FACE_BOTTOM - q.height)))
        else: scene.alpha_composite(im, (int(x), int(FACE_BOTTOM - im.height)))
        self.put_tag(scene, x, im.width)
        # 換段落（起承轉合換段）：斜的色塊從右往左刷過去
        if i > 0 and t >= u and self.lines[i].get('part') and self.lines[i].get('part') != self.lines[i - 1].get('part') and lt < 0.4 and self.r.st.get('wipe', True):
            q = lt / 0.4; ex = W * 1.6 * (1 - q) - W * 0.3
            poly = [(ex, 0), (ex + 420, 0), (ex + 420 - 700, H), (ex - 700, H)]
            wl = Image.new('RGBA', scene.size, (0, 0, 0, 0)); ImageDraw.Draw(wl).polygon(poly, fill=hexrgb(self.T['acc']) + (235,)); scene.alpha_composite(wl)
        out = scene.convert('RGB')
        return out if r.S == 1 else out.resize((r.w, r.h), Image.LANCZOS)


def make(r, theme):
    return Explain(r, theme) if DESIGN_THEMES[theme]['kind'] == 'explain' else Design(r, theme)
