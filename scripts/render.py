"""自動出片：照導演表把大頭照、表情切換、道具、運鏡、音效、字幕算成直式影片。
  python render.py videos/片名/director.json              完整 1080×1920、30fps → final.mp4
  python render.py videos/片名/director.json --preview    540×960 快速預覽 → preview.mp4（改稿時用）
  python render.py videos/片名/director.json --stills 0.3,5,12   只輸出這幾秒的畫面 → check/still_*.png
需要：Python 3.9+、Pillow、numpy、ffmpeg。"""
import argparse, math, os, re, subprocess, sys, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import W, H, FPS, load, resolve_face, find_face, find_prop, font, chunks, run, ffprobe_dur
import sfx as SFX

DEFAULT_STYLE = {'bg': '#FFE9BF', 'bg2': '#FFC879', 'accent': '#FF4B2B', 'ink': '#1F1A17', 'hl': '#FFE14D',
                 'pattern': 'dots', 'sticker': False, 'caption_size': 84, 'head_size': 0.68,
                 'shape': None, 'shape_color': None, 'frame': False, 'grain': 0, 'glow': True, 'shadow': True,
                 'cap': 'stroke', 'cap_color': 'white', 'cap_bg': None, 'hook_style': 'pop', 'banner_style': 'solid',
                 'motion': 'bouncy', 'label_l': '', 'label_r': ''}
# 風格模板：style.theme 選一個，其他 style 欄位可再覆蓋。高級 IG 風＝淡色、留白、細線、柔陰影、不加粗描邊、動作輕。
THEMES = {
    '活潑': {},   # 原本的暖黃卡通風
    '奶茶極簡': dict(bg='#F4EEE6', bg2='#E9DFD2', accent='#9C7356', ink='#4A3B31', hl='#C79A6E', pattern='none', grain=6,
                 sticker=False, glow=False, cap='pill', cap_color='#4A3B31', cap_bg='#FFFFFFD9',
                 hook_style='elegant', banner_style='outline', motion='soft', head_size=0.84),
    '莫蘭迪綠': dict(bg='#E6EAE3', bg2='#D3DACE', accent='#5F7461', ink='#33403A', hl='#E9F1D8', pattern='none', grain=5,
                 sticker=False, glow=False, cap='bar', cap_color='#FFFFFF', cap_bg='#5F7461E6',
                 hook_style='elegant', banner_style='line', motion='soft', head_size=0.84),
    '霧粉雜誌': dict(bg='#F6E9E6', bg2='#EED9D5', accent='#A8646E', ink='#3D2C2E', hl='#A8646E', pattern='none', grain=6,
                 sticker=False, glow=False, frame=True, cap='plain', cap_color='#3D2C2E',
                 hook_style='elegant', banner_style='line', motion='soft', head_size=0.84, label_l='DAILY NOTES', label_r='VOL.01'),
    '黑金質感': dict(bg='#1E1D1B', bg2='#2B2926', accent='#C8A96A', ink='#F3EDE2', hl='#C8A96A', pattern='none', grain=8,
                 sticker=False, glow=True, frame=True, cap='plain', cap_color='#F3EDE2',
                 hook_style='elegant', banner_style='outline', motion='soft', head_size=0.84, label_l='PREMIUM', label_r='NO.01'),
    '霧藍清新': dict(bg='#EDF1F4', bg2='#DCE4EA', accent='#3F5D78', ink='#2C3A47', hl='#F2D58A', pattern='grid_fine', grain=4,
                 sticker=False, glow=False, cap='pill', cap_color='#2C3A47', cap_bg='#FFFFFFE6',
                 hook_style='elegant', banner_style='outline', motion='soft', head_size=0.84),
    '燕麥紙感': dict(bg='#EFE7DA', bg2='#E6DBCA', accent='#2F2A25', ink='#2F2A25', hl='#F0C96B', pattern='none', grain=10,
                 sticker=False, glow=False, cap='marker', cap_color='#2F2A25',
                 hook_style='elegant', banner_style='line', motion='soft', head_size=0.84, label_l='NOTE', label_r='01'),
    # 拼貼風：粗字、反白色塊、斜紋底、深色字幕框、粗框貼紙卡片（參考 IG 爆款教學帳號）
    '拼貼': dict(bg='#F3EBDD', bg2='#EBDFCB', accent='#F26B1D', ink='#1E2A47', hl='#F26B1D', ribbon='#2449B8', ribbon_hl='#FFC83D',
               pattern='stripes_soft', grain=0, sticker=False, glow=False, cap='dark', hook_style='collage', banner_style='bubble',
               big_style='heavy', motion='bouncy', head_size=0.84, caption_size=78, doodle=True, stage='side', title_fx='heavy'),
    '拼貼橘': dict(bg='#F47B20', bg2='#EF6E12', accent='#FFE14D', ink='#1E1E1E', hl='#FFE14D', ribbon='#1E1E1E', ribbon_hl='#FFE14D',
                pattern='stripes_soft', grain=0, sticker=False, glow=False, cap='dark', hook_style='collage', banner_style='bubble',
                big_style='heavy', motion='bouncy', head_size=0.84, caption_size=78, doodle=True, title_color='#FFFFFF', stage='side', title_fx='heavy'),
}
# 設計感系列（scripts/design.py）：人物在下方角落當配角，字幕放人物旁邊，不壓到臉
from design import DESIGN_THEMES
for _k in DESIGN_THEMES: THEMES[_k] = dict(stage='design', sticker=False)
for _k, _v in THEMES.items():
    if _v: _v.setdefault('caption_size', 74)
PROP_POS = {'right': (0.76, 0.33), 'left': (0.22, 0.33), 'top': (0.5, 0.2), 'top_right': (0.74, 0.22), 'top_left': (0.24, 0.22),
            'low_right': (0.78, 0.58), 'low_left': (0.2, 0.58)}


def hexrgb(h): h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
def rgba(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + ((int(h[6:8], 16),) if len(h) >= 8 else (255,))
def clamp(x, a=0., b=1.): return max(a, min(b, x))
def back(x, s=1.9): x = clamp(x) - 1; return 1 + (s + 1) * x ** 3 + s * x ** 2      # easeOutBack
def out3(x): return 1 - (1 - clamp(x)) ** 3


class R:
    def __init__(self, path, scale=1.0):
        self.path = path; self.base = os.path.dirname(os.path.abspath(path)); self.D = load(path)
        self.S = scale; self.w, self.h = int(W * scale), int(H * scale)
        us = self.D.get('style', {}); st = dict(DEFAULT_STYLE)
        th = us.get('theme')
        if th:
            if th not in THEMES: raise SystemExit(f'沒有「{th}」這個風格，可選：' + '、'.join(THEMES))
            st.update(THEMES[th])
        st.update(us); self.st = st
        self.dz = None
        self.lines = self.D['lines']
        if any('start' not in l for l in self.lines): raise SystemExit('導演表還沒有時間：先跑 voice.py say（或 voice.py silent 先看畫面）')
        self.dur = self.D.get('duration') or self.lines[-1]['end'] + 0.7
        fd = self.D.get('faces', '../../faces'); self.faces_dir = fd if os.path.isabs(fd) else os.path.join(self.base, fd)
        self.fB = font('black'); self.fb = font('bold')
        self._faces = {}; self._props = {}; self._caps = {}; self._txt = {}
        self.env = self.voice_env()
        self.bg = self.make_bg()
        self.rng = random.Random(7)
        if st.get('stage') == 'design':
            from design import Design
            self.dz = Design(self, th)

    def px(self, v): return int(round(v * self.S))

    # ---------- 素材 ----------
    def make_bg(self):
        w, h = self.w, self.h + self.px(120)
        a, b = np.array(hexrgb(self.st['bg']), float), np.array(hexrgb(self.st['bg2']), float)
        y = np.linspace(0, 1, h)[:, None, None]
        g = (a * (1 - y) + b * y).repeat(w, 1).astype(np.uint8)
        im = Image.fromarray(g, 'RGB'); d = ImageDraw.Draw(im, 'RGBA'); pat = self.st['pattern']; c = (255, 255, 255, 70)
        step = self.px(60)
        if pat == 'dots':
            for yy in range(0, h, step):
                for xx in range((yy // step) % 2 * step // 2, w, step): r = self.px(7); d.ellipse([xx - r, yy - r, xx + r, yy + r], fill=c)
        elif pat == 'stripes':
            for k in range(-h, w, step): d.line([(k, h), (k + h, 0)], fill=c, width=self.px(16))
        elif pat == 'grid':
            for k in range(0, w, step): d.line([(k, 0), (k, h)], fill=c, width=self.px(3))
            for k in range(0, h, step): d.line([(0, k), (w, k)], fill=c, width=self.px(3))
        elif pat == 'stripes_soft':   # 寬斜紋（拼貼風）
            light = sum(hexrgb(self.st['bg'])) > 600
            cc = (255, 255, 255, 120) if light else (255, 255, 255, 28); sw = self.px(46)
            for k in range(-h, w + h, self.px(150)): d.polygon([(k, h), (k + sw, h), (k + sw + h, 0), (k + h, 0)], fill=cc)
        elif pat == 'grid_fine':   # 很淡的細方格（筆記本感）
            cc = hexrgb(self.st['ink']) + (14,); st2 = self.px(90)
            for k in range(0, w, st2): d.line([(k, 0), (k, h)], fill=cc, width=max(1, self.px(2)))
            for k in range(0, h, st2): d.line([(0, k), (w, k)], fill=cc, width=max(1, self.px(2)))
        if self.st.get('glow'):   # 柔光暈在頭後面
            glow = Image.new('L', (w, h), 0); gd = ImageDraw.Draw(glow); r = self.px(520); cx, cy = w // 2, self.px(860)
            gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=120 if self.st['pattern'] != 'none' or self.st.get('sticker') else 45)
            glow = glow.filter(ImageFilter.GaussianBlur(self.px(120)))
            im.paste(Image.new('RGB', (w, h), 'white' if sum(hexrgb(self.st['bg'])) > 380 else self.st['accent']), (0, 0), glow)
        if self.st.get('footer'):   # 底部品牌小字（在字幕下面、平台遮擋區上面）
            f = ImageFont.truetype(self.fb, self.px(34)); col = hexrgb(self.st['ink']) + (150,)
            d.text((w / 2, self.px(1430)), self.st['footer'], font=f, fill=col, anchor='mm')
        if self.st.get('frame'):   # 細線外框＋角落小字（雜誌感），避開上方 250、下方 450 的平台遮擋區
            ink = hexrgb(self.st['ink']) + (110,); m = self.px(54); lw = max(1, self.px(2))
            d.rectangle([m, self.px(250), w - m, self.px(1455)], outline=ink, width=lw)
            f = ImageFont.truetype(self.fb, self.px(26))
            for txt, x, anc in [(self.st.get('label_l', ''), m + self.px(24), 'lm'), (self.st.get('label_r', ''), w - m - self.px(24), 'rm')]:
                if txt:
                    tw = f.getlength(txt) + self.px(24) * len(txt) / 6
                    x0 = x - self.px(12) if anc == 'lm' else x - tw - self.px(12)
                    d.rectangle([x0, self.px(1455) - self.px(20), x0 + tw + self.px(24), self.px(1455) + self.px(20)], fill=hexrgb(self.st['bg2']))
                    self.spaced(d, (x, self.px(1455)), txt, f, ink, anc, self.px(4))
        g = self.st.get('grain', 0)
        if g:   # 細顆粒，質感比較像底片／紙
            n = np.random.default_rng(3).normal(0, g, (h, w, 1))
            im = Image.fromarray(np.clip(np.asarray(im).astype(float) + n, 0, 255).astype(np.uint8), 'RGB')
        return im

    def spaced(self, d, xy, txt, f, fill, anchor='lm', sp=0):
        """字距拉開的小字（英文標籤用）"""
        tot = sum(f.getlength(c) for c in txt) + sp * (len(txt) - 1); x, y = xy
        if anchor[0] == 'r': x -= tot
        elif anchor[0] == 'm': x -= tot / 2
        for c in txt: d.text((x, y), c, font=f, fill=fill, anchor='l' + anchor[1]); x += f.getlength(c) + sp

    def shape_img(self, hw, hh):
        """頭後面的拱門／圓形色塊"""
        k = ('shape', hw, hh)
        if k in self._txt: return self._txt[k]
        kind = self.st.get('shape'); col = rgba(self.st.get('shape_color') or self.st['bg2'])
        if kind == 'arch':
            sw, sh = int(hw * 0.92), int(hh * 1.05); im = Image.new('RGBA', (sw, sh)); d = ImageDraw.Draw(im)
            d.rounded_rectangle([0, 0, sw - 1, sh + sw], radius=sw // 2, fill=col)
        else:
            r = int(max(hw, hh) * 0.5); im = Image.new('RGBA', (2 * r, 2 * r)); ImageDraw.Draw(im).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=col)
        self._txt[k] = im; return im

    def face(self, key, talk=False):
        k = (key, talk)
        if k in self._faces: return self._faces[k]
        p = find_face(self.faces_dir, key + '_talk') if talk else None
        if not p:
            if talk: self._faces[k] = None; return None
            real, p = resolve_face(self.faces_dir, key)
            if not p: raise SystemExit(f'表情庫找不到「{key}」也沒有可代替的。表情庫位置：{self.faces_dir}')
        im = Image.open(p).convert('RGBA'); bb = im.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox(); im = im.crop(bb) if bb else im
        side = self.px(W * self.st['head_size']); im = ImageOps.contain(im, (side, side), Image.LANCZOS)
        al = np.asarray(im.getchannel('A'))
        cut = max((al[-k] > 128).mean() for k in range(1, max(2, al.shape[0] // 30))) > 0.25   # 半身照下緣被切平
        if self.st.get('sticker', True):
            pad = self.px(30); big = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2)); big.alpha_composite(im, (pad, pad))
            a = big.getchannel('A').point(lambda v: 255 if v > 40 else 0)
            border = a.filter(ImageFilter.MaxFilter(2 * (self.px(12) // 2) + 1)).filter(ImageFilter.GaussianBlur(1))
            shadow = border.filter(ImageFilter.GaussianBlur(self.px(14))).point(lambda v: v * 0.35)
            out = Image.new('RGBA', big.size)
            sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sh.putalpha(shadow); out.alpha_composite(sh, (0, self.px(14)))
            wh = Image.new('RGBA', big.size, (255, 255, 255, 0)); wh.putalpha(border); out.alpha_composite(wh)
            out.alpha_composite(big); im = out
        elif self.st.get('shadow', True):   # 沒有白邊：只加很淡的柔陰影，比較有質感
            pad = self.px(40); big = Image.new('RGBA', (im.width + pad * 2, im.height + pad * 2)); big.alpha_composite(im, (pad, pad))
            a = big.getchannel('A').filter(ImageFilter.GaussianBlur(self.px(22))).point(lambda v: v * 0.22)
            out = Image.new('RGBA', big.size); sh = Image.new('RGBA', big.size, (0, 0, 0, 0)); sh.putalpha(a)
            out.alpha_composite(sh, (0, self.px(18))); out.alpha_composite(big); im = out
        if cut:   # 底部淡出（連白邊一起），不會像被刀切
            al = np.asarray(im.getchannel('A')).astype(float); h = im.height; fade = np.ones(h)
            n = int(h * 0.2); end = h - (self.px(30) if self.st.get('sticker', True) else self.px(40) if self.st.get('shadow', True) else 0)
            fade[end - n:end] = np.linspace(1, 0, n) ** 1.4; fade[end:] = 0
            im = im.copy(); im.putalpha(Image.fromarray((al * fade[:, None]).astype(np.uint8)))
        self._faces[k] = im; return im

    def prop(self, name):
        if name in self._props: return self._props[name]
        p = find_prop(name, [os.path.join(self.base, 'props'), os.path.join(self.base, '..', '..', 'props')])
        if not p: print(f'⚠ 找不到道具「{name}」，略過'); self._props[name] = None; return None
        im = Image.open(p).convert('RGBA'); sz = self.px(240); im = ImageOps.contain(im, (sz, sz), Image.LANCZOS)
        self._props[name] = im; return im

    def voice_env(self):
        n = int(self.dur * FPS) + 2; env = np.zeros(n)
        v = self.D.get('voice')
        if v:
            r = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(self.base, v), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True)
            x = np.frombuffer(r.stdout, np.int16).astype(float) / 32768; hop = 16000 // FPS
            m = min(n, len(x) // hop)
            rms = np.sqrt((x[:m * hop].reshape(m, hop) ** 2).mean(1)); env[:m] = rms
            if env.max() > 0: env = np.clip(env / (np.percentile(env[env > 0.005], 90) + 1e-6), 0, 1.3) if (env > 0.005).any() else env
        else:   # 沒聲音（silent 模式）：講話時間用假波形
            for l in self.lines:
                for f in range(int(l['start'] * FPS), min(n, int(l['end'] * FPS))): env[f] = 0.55 + 0.35 * math.sin(f / FPS * 2 * math.pi * 3.5)
        # 平滑：起音、收音都慢一點，頭才不會每格亂跳（防抖）
        sm = np.copy(env); a_up, a_dn = 0.25, 0.10
        for i in range(1, n):
            k = a_up if env[i] > sm[i - 1] else a_dn; sm[i] = sm[i - 1] + k * (env[i] - sm[i - 1])
        self.raw_env = env
        return sm

    # ---------- 文字 ----------
    def text_img(self, text, size, fill, stroke, sw, fontp=None, emph=(), hl=None, marker=None, sp=0):
        k = (text, size, fill, stroke, sw, tuple(emph), hl, marker, sp)
        if k in self._txt: return self._txt[k]
        f = ImageFont.truetype(fontp or self.fB, size)
        marks = [False] * len(text)
        for e in emph:
            i = text.find(e)
            while e and i >= 0:
                for j in range(i, i + len(e)): marks[j] = True
                i = text.find(e, i + 1)
        wsum = sum(f.getlength(c) for c in text) + sp * max(0, len(text) - 1); hgt = int(size * 1.35) + sw * 2
        im = Image.new('RGBA', (int(wsum) + sw * 2 + 4, hgt)); d = ImageDraw.Draw(im); x = sw + 2
        if marker:   # 螢光筆：強調字下半部畫色塊
            xx = x
            for c, m in zip(text, marks):
                cw = f.getlength(c)
                if m: d.rectangle([xx - 2, hgt * 0.52, xx + cw + sp + 2, hgt * 0.86], fill=marker)
                xx += cw + sp
        for c, m in zip(text, marks):
            col = hl if m and hl else fill
            d.text((x, hgt // 2), c, font=f, fill=col, stroke_width=sw, stroke_fill=(col if stroke == 'same' else stroke), anchor='lm'); x += f.getlength(c) + sp
        self._txt[k] = im; return im

    def caption_plan(self):
        plan = []
        for l in self.lines:
            cs = chunks(l['text'], self.D.get('caption_max', 9)); tot = sum(len(c) for c in cs) or 1; t = l['start']; span = l['end'] - l['start']
            for c in cs:
                d = span * len(c) / tot; plan.append((t, t + d, c, l.get('emph', []))); t += d
        return plan

    # ---------- 單格 ----------
    def line_at(self, t):
        cur = 0
        for i, l in enumerate(self.lines):
            if t >= l['start'] - 0.02: cur = i
        return cur

    # ---------- 素材（照片、截圖、影片片段） ----------
    def media_mode(self, i):
        m = self.lines[i].get('media') if i is not None and i >= 0 else None
        if not m: return None
        return (m.get('mode', 'card') if isinstance(m, dict) else 'card')

    def media_path(self, m):
        f = m['file'] if isinstance(m, dict) else m
        for c in [f, os.path.join(self.base, f), os.path.join(self.base, '..', '..', f), os.path.join(self.base, '..', '..', '素材', f), os.path.join(self.base, '素材', f)]:
            if os.path.exists(c): return c
        raise SystemExit(f'找不到素材「{f}」（放在工作資料夾的 素材/ 或這支片的資料夾）')

    def media_frame(self, i, lt, mode):
        key = ('media', i, mode)
        if key not in self._txt:
            L = self.lines[i]; m = L['media']; p = self.media_path(m); mm = m if isinstance(m, dict) else {}
            if mode == 'full': box = (self.w, self.h)
            else: box = (self.px(W * 0.8), self.px(640))
            def fit(im):
                im = im.convert('RGB')
                if mode == 'full':   # 鋪滿（裁切）＋底部加深讓字幕清楚
                    if abs(im.width / im.height - box[0] / box[1]) > 0.25 and not mm.get('crop'):   # 橫的素材：模糊放大當底，原圖完整放中間
                        bgi = ImageOps.fit(im, box, Image.BILINEAR).filter(ImageFilter.GaussianBlur(self.px(40))).convert('RGBA')
                        fg = ImageOps.contain(im, (box[0], int(box[1] * 0.5)), Image.LANCZOS)
                        bgi.paste(fg, ((box[0] - fg.width) // 2, int(box[1] * 0.36 - fg.height / 2))); im = bgi
                    else:
                        im = ImageOps.fit(im, box, Image.LANCZOS).convert('RGBA')
                    sh = Image.new('RGBA', box, (0, 0, 0, 0)); g = np.zeros((box[1], 1), np.uint8)
                    g[int(box[1] * .55):, 0] = np.linspace(0, 150, box[1] - int(box[1] * .55)).astype(np.uint8)
                    sh.putalpha(Image.fromarray(g).resize(box)); im.alpha_composite(sh); return im
                im = ImageOps.contain(im, box, Image.LANCZOS)   # 卡片：圓角＋白邊＋陰影
                bw, r, pad = self.px(10), self.px(28), self.px(24)
                card = Image.new('RGBA', (im.width + bw * 2 + pad * 2, im.height + bw * 2 + pad * 2))
                sh = Image.new('L', card.size, 0); ImageDraw.Draw(sh).rounded_rectangle([pad, pad + self.px(10), card.width - pad, card.height - pad + self.px(10) - 1], r, fill=110)
                card.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(self.px(12))))
                d = ImageDraw.Draw(card); d.rounded_rectangle([pad, pad, card.width - pad - 1, card.height - pad - 1], r, fill='white')
                mask = Image.new('L', im.size, 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, im.width - 1, im.height - 1], max(1, r - bw), fill=255)
                card.paste(im, (pad + bw, pad + bw), mask)
                return card
            if p.lower().endswith(('.mp4', '.mov', '.m4v', '.webm', '.mkv', '.gif')):
                dur = L['end'] - L['start'] + 0.6
                tw, th = (box if mode == 'full' else (box[0], box[1]))
                r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(mm.get('from', 0)), '-i', p, '-t', f'{dur:.2f}', '-an', '-vf',
                                    f'fps={FPS},scale={tw}:{th}:force_original_aspect_ratio=decrease',
                                    '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True).stdout
                frames, k = [], 0
                while True:   # 切 PNG 串流
                    e = r.find(b'IEND', k)
                    if e < 0: break
                    import io; frames.append(fit(Image.open(io.BytesIO(r[k:e + 8])))); k = e + 8
                self._txt[key] = frames or None
            else:
                self._txt[key] = [fit(Image.open(p))]
        fr = self._txt[key]
        if not fr: return None
        return fr[min(len(fr) - 1, max(0, int(lt * FPS)))]

    # ---------- 轉場 ----------
    TRANS_DUR = 0.42
    def trans_of(self, i):
        if i == 0: return None
        L = self.lines[i]; tr = L.get('trans')
        if tr == 'none': return None
        if tr: return tr
        if self.st.get('stage') == 'design' and self.D.get('transition', 'auto') == 'auto': return None   # 設計感版面：換句用淡入，不加大轉場
        if L.get('banner'):   # 自動：每個新段落（有標籤的句子）換場，輪流用縮放穿越、百葉窗
            k = sum(1 for l in self.lines[1:i] if l.get('banner') and l.get('trans') != 'none')
            d = self.D.get('transition', 'auto')
            if d == 'none': return None
            return ['zoom', 'blinds'][k % 2] if d == 'auto' else d
        return None

    def frame(self, fi):
        t = fi / FPS; i = self.line_at(t); tr = self.trans_of(i)
        if tr:
            s0 = self.lines[i]['start']; p = (t - s0) / self.TRANS_DUR
            if 0 <= p < 1:
                key = ('A', i)
                if key not in self._txt: self._txt[key] = self.frame_raw(max(0, int(s0 * FPS) - 1))
                return self.transition(tr, self._txt[key], self.frame_raw(fi), p)
        return self.frame_raw(fi)

    def transition(self, kind, A, B, p):
        w, h = self.w, self.h
        if kind == 'zoom':      # T03 縮放穿越：舊畫面往前衝出去、新畫面從後面推上來
            e = out3(p); za = 1 + 1.6 * e; zb = 1.25 - 0.25 * e
            def zoomed(im, z):
                cw, ch = int(w / z), int(h / z); x0, y0 = (w - cw) // 2, (h - ch) // 2
                return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), Image.BILINEAR)
            return Image.blend(zoomed(B, zb), zoomed(A, za), clamp(1 - p / 0.4) ** 1.5)
        if kind == 'blinds':    # T04 百葉窗：橫條一條一條翻開
            out = A.copy(); n = 8; sh = h / n
            for k in range(n):
                q = out3(clamp((p - k * 0.05) / 0.55)); hh = int(sh * q)
                if hh <= 0: continue
                y0 = int(k * sh + (sh - hh) / 2); out.paste(B.crop((0, y0, w, y0 + hh)), (0, y0))
            return out
        if kind == 'wipe':      # 品牌色塊掃過
            x = int((1 - out3(p * 2 if p < .5 else 1)) * w) if p < .5 else 0
            base = A if p < .5 else B; out = base.copy(); d = ImageDraw.Draw(out)
            if p < .5: d.rectangle([x, 0, w, h], fill=self.st['accent'])
            else: xr = int(out3((p - .5) * 2) * w); d.rectangle([xr, 0, w, h], fill=self.st['accent'])
            return out
        if kind == 'flash':     # 白光
            a = 1 - abs(p - 0.35) / 0.65 if p > 0.35 else p / 0.35
            return Image.blend(A if p < 0.35 else B, Image.new('RGB', (w, h), 'white'), clamp(a) * 0.9)
        return B

    def frame_raw(self, fi):
        if self.dz: return self.dz.frame(fi)
        t = fi / FPS; S = self.S; st = self.st; i = self.line_at(t); L = self.lines[i]; lt = t - L['start']
        ldur = max(0.3, L['end'] - L['start'])
        prev_face = self.lines[i - 1].get('face', 'neutral') if i > 0 else None
        face = L.get('face', 'neutral'); amp = float(self.env[min(fi, len(self.env) - 1)])
        # 背景（慢慢往上飄）
        scene = self.bg.crop((0, 0, self.w, self.h)).convert('RGBA')   # 背景固定不動（整數像素慢慢飄會一頓一頓的）
        mode, pmode = self.media_mode(i), self.media_mode(i - 1) if i > 0 else None
        mk = out3(lt / 0.32)   # 版面切換進度
        if mode == 'full':     # 素材鋪滿：淡入＋微微推近
            mf = self.media_frame(i, lt, 'full')
            if mf is not None:
                z = 1.06 - 0.06 * mk if pmode != 'full' else 1.0
                if z != 1: mf = mf.resize((int(self.w * z), int(self.h * z)), Image.BILINEAR).crop((int(self.w * (z - 1) / 2), int(self.h * (z - 1) / 2), int(self.w * (z - 1) / 2) + self.w, int(self.h * (z - 1) / 2) + self.h))
                a = 1.0 if pmode == 'full' else clamp(lt / 0.25)
                if a < 1: mf = mf.copy(); mf.putalpha(int(255 * a))
                scene.alpha_composite(mf)
        # 中間的內容卡片（人物當配角時，畫面中間固定一張卡，內容一句一句換）
        if self.st.get('stage') == 'side' and mode is None:
            hk = self.D.get('hook'); u = hk.get('until', 3.0) if hk else -1
            if t > u: self.draw_card(scene, t - u)
        # 大頭
        talking = self.raw_env[min(fi, len(self.raw_env) - 1)] > 0.32 and L['start'] <= t <= L['end']
        im = self.face(face, talk=True) if talking and (fi // 3) % 3 != 2 else None
        im = im or self.face(face)
        sc = 1.0
        dy = 0; dx = 0; rot = 0      # 講話時頭不上下動（畫面不要抖），對嘴靠張嘴圖
        soft = self.st.get('motion') == 'soft'
        if face != prev_face or i == 0: sc *= (0.96 + 0.04 * out3(lt / 0.3)) if soft else (0.88 + 0.12 * back(lt / 0.3))           # 換表情：彈一下
        cam = L.get('cam', 'still')
        if cam == 'bounce': dy += -self.px(40) * abs(math.sin(lt * math.pi * 2.2)) * math.exp(-lt * 1.2)
        if cam == 'tilt': rot = 6 * math.sin(lt * math.pi * 1.6) * math.exp(-lt * 0.6)
        if cam == 'slide_l': dx = self.px(700) * (1 - out3(lt / 0.35))
        if cam == 'slide_r': dx = -self.px(700) * (1 - out3(lt / 0.35))
        a0, a1 = self.layout_of(i - 1) if i > 0 else self.layout_of(i), self.layout_of(i)
        k = out3(lt / (0.45 if soft else 0.32))   # 換位置：平順移過去
        ls, lx, ly = [u + (v - u) * k for u, v in zip(a0, a1)]
        sc *= ls
        hi = im if abs(sc - 1) < 0.002 else im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
        if abs(rot) > 0.3: hi = hi.rotate(rot, Image.BILINEAR, expand=True)
        cx, cy = self.w * lx + dx, self.px(ly) + dy
        if ls < 1.2:   # 不超出安全區左右（右邊 120 留給平台按鈕）；特寫可以出框
            hw = hi.width * 0.42; cx = min(max(cx, hw), self.px(960) - hw)
        hk = self.D.get('hook')
        if hk:   # 開場標題在的時候，大頭縮小往下讓位，標題收掉時再放大回來
            u = hk.get('until', 3.0); m = 1 - out3((t - u) / 0.4) if t > u else 1.0
            if m > 0:
                col = self.st.get('hook_style') == 'collage'; f = 1 - (0.3 if col else 0.2) * m; hi = hi.resize((max(1, int(hi.width * f)), max(1, int(hi.height * f))), Image.BILINEAR); cy += self.px(0 if self.st.get('stage') == 'side' else 230 if col else 130) * m
        if self.st.get('shape') and mode != 'full':   # 頭後面的色塊（跟著頭的位置和大小）
            shp = self.shape_img(hi.width // 6 * 6, hi.height // 6 * 6)
            yb = cy + hi.height / 2 - shp.height   # 底部對齊頭的下緣
            if self.st['shape'] == 'circle': yb = cy - shp.height / 2 + hi.height * 0.04
            scene.alpha_composite(shp, (int(cx - shp.width / 2), int(yb)))
        scene.alpha_composite(hi, (int(cx - hi.width / 2), int(cy - hi.height / 2)))
        self._head_box = (cx - hi.width * 0.36, cx + hi.width * 0.36)   # 臉大約的左右邊（扣掉透明邊）
        # 道具
        props = L.get('prop') or []
        props = [props] if isinstance(props, str) else props
        poss = L.get('prop_pos') or ['right', 'left']
        poss = [poss] if isinstance(poss, str) else poss
        p0 = self.prop_start(L)   # 開場標題還在的時候先不放道具，免得擋字，標題收掉才出現
        if self.big_text(i) and mode is None and not L.get('prop_pos'): props = []   # 有大字就不放道具，畫面才乾淨
        center_prop = self.st.get('stage') == 'side' and mode is None and not L.get('banner') and not L.get('prop_pos') and props
        if self.st.get('stage') == 'side' and L.get('banner') and mode is None: props = []
        for k, pn in enumerate(props[:3]):
            p = self.prop(pn)
            if not p: continue
            pt = t - p0 - 0.12 - 0.18 * k
            if pt <= 0: continue
            s = (0.85 + 0.15 * out3(pt / 0.35)) * clamp(pt / 0.2) if soft else back(pt / 0.32, 2.4); fade = clamp((L['end'] + 0.1 - t) / 0.18)
            if s <= 0.02 or fade <= 0: continue
            ang = (2 if soft else 8) * math.sin(t * 2.4 + k); fy = self.px(8 if soft else 12) * math.sin(t * 2.0 + k)
            q = p.resize((max(1, int(p.width * s)), max(1, int(p.height * s))), Image.BILINEAR).rotate(ang, Image.BILINEAR, expand=True)
            if fade < 1: q.putalpha(q.getchannel('A').point(lambda v: int(v * fade)))
            if center_prop:   # 人物當配角：道具放大擺中間
                if k == 0: q = q.resize((q.width * 3 // 2, q.height * 3 // 2), Image.BILINEAR)
                px_, py_ = self.px((self.CARD[0] + self.CARD[2]) / 2) + (k - (min(len(props), 3) - 1) / 2) * self.px(330), self.px(615)
            elif L.get('prop_pos') or self.lay_name(i) in ('center', 'close'):
                fx, fyy = PROP_POS.get(poss[k % len(poss)], PROP_POS['right']); px_, py_ = fx * self.w, fyy * self.h
            else:   # 人物換了位置：道具跟著頭的左上／右上
                side = 1 if (k % 2 == 0) == (cx < self.w / 2) else -1
                px_ = min(max(cx + side * hi.width * 0.38, self.px(130)), self.px(840)); py_ = cy - hi.height * 0.32 + k * self.px(60)
            scene.alpha_composite(q, (int(px_ - q.width / 2), int(py_ + fy - q.height / 2)))
        if mode == 'card':     # 素材卡片：從上方彈出
            mc = self.media_frame(i, lt, 'card')
            if mc is not None:
                k = back(lt / 0.35, 1.6) if pmode != 'card' else 1.0
                if k > 0.02:
                    q = mc if abs(k - 1) < 0.01 else mc.resize((max(1, int(mc.width * k)), max(1, int(mc.height * k))), Image.BILINEAR)
                    scene.alpha_composite(q, (int(self.w / 2 - q.width / 2), int(self.px(640) - q.height / 2)))
        # 運鏡（整個畫面）
        z, ox, oy, zr = 1.0, 0.0, 0.0, 0.0
        if cam == 'push': z = 1 + 0.08 * out3(lt / ldur)
        if cam == 'pull': z = 1.1 - 0.1 * out3(lt / ldur)
        if cam == 'punch': z = 1 + 0.14 * math.exp(-max(0, lt) * 5) * clamp(lt / 0.06)
        if cam == 'zoom_face': z = 1 + 0.32 * out3(lt / 0.45)
        if cam == 'shake':
            k = math.exp(-lt * 3.5); ox = self.px(26) * k * math.sin(lt * 63); oy = self.px(18) * k * math.cos(lt * 51); z = 1.04; zr = 1.2 * k * math.sin(lt * 40)
        if z != 1 or ox or oy or zr:
            fx, fy = self.w / 2, self.px(760)
            a = math.radians(zr); ca, sa = math.cos(a) / z, math.sin(a) / z
            data = (ca, sa, fx - ca * (fx + ox) - sa * (fy + oy), -sa, ca, fy + sa * (fx + ox) - ca * (fy + oy))
            scene = scene.transform((self.w, self.h), Image.AFFINE, data, Image.BILINEAR)
        # 開場標題（前幾秒，鉤子）
        hook = self.D.get('hook')
        hook_on = hook and t < hook.get('until', 3.0)
        if hook:
            self.draw_hook(scene, hook, t)
        elif False: pass
        # 段落標籤
        if L.get('banner') and not hook_on:
            if self.st.get('stage') == 'side' and mode is None: self.draw_steps(scene, i, lt, L['end'] - t)
            else: self.draw_banner(scene, L['banner'], lt, L['end'] - t)
        # 大字（人物移到旁邊時，空出來的地方放重點字）
        if not hook_on and mode is None: self.draw_big(scene, i, lt, L['end'] - t)
        # 字幕
        for (a0, a1, c, emph) in self.cplan:
            if a0 <= t < a1: self.draw_caption(scene, c, emph, t - a0)
        return scene.convert('RGB')

    def caption_img(self, c, emph):
        k = ('cap', c, tuple(emph))
        if k in self._txt: return self._txt[k]
        st = self.st; size = self.px(st['caption_size']); kind = st.get('cap', 'stroke'); col = st.get('cap_color', 'white')
        if kind == 'stroke':
            img = self.text_img(c, size, 'white', st['ink'], self.px(9), emph=emph, hl=st['hl'])
        elif kind == 'dark':   # 深色圓角框＋白字（拼貼風）
            t = self.text_img(c, size, '#FFFFFF', 'same', self.px(2), emph=emph, hl=st['hl'], sp=self.px(2))
            img = Image.new('RGBA', (t.width + self.px(64), t.height + self.px(22))); ImageDraw.Draw(img).rounded_rectangle([0, 0, img.width - 1, img.height - 1], self.px(20), fill=(38, 32, 28, 240))
            img.alpha_composite(t, (self.px(32), self.px(9)))
        elif kind == 'marker':
            img = self.halo(self.text_img(c, size, col, 'same', self.px(1), emph=emph, marker=st['hl'], sp=self.px(2)))
        else:
            hl = st['hl'] if kind == 'bar' else st['accent']
            mk = None if kind == 'bar' else rgba(st['hl'])[:3] + (110,)
            img = self.text_img(c, size, col, 'same', self.px(1), emph=emph, hl=hl, sp=self.px(2), marker=mk)
            if kind in ('pill', 'bar'):
                px_, py_ = (self.px(46), self.px(14)) if kind == 'pill' else (self.px(40), self.px(16))
                box = Image.new('RGBA', (img.width + px_ * 2, img.height + py_ * 2)); d = ImageDraw.Draw(box)
                r = box.height // 2 if kind == 'pill' else self.px(10)
                if kind == 'pill':   # 很淡的陰影
                    sh = Image.new('L', box.size, 0); ImageDraw.Draw(sh).rounded_rectangle([self.px(6), self.px(10), box.width - self.px(6), box.height - 1], r, fill=40)
                    box.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(self.px(8))))
                d.rounded_rectangle([0, 0, box.width - 1, box.height - self.px(6)], r, fill=rgba(st.get('cap_bg') or '#FFFFFFE6'))
                box.alpha_composite(img, (px_, py_ - self.px(3))); img = box
            else: img = self.halo(img)
        self._txt[k] = img; return img

    def halo(self, img):
        """沒有底框的字幕：後面墊一層跟背景同色的柔光，壓在照片上也看得清楚"""
        pad = self.px(30); big = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2)); big.alpha_composite(img, (pad, pad))
        a = big.getchannel('A').filter(ImageFilter.MaxFilter(2 * (self.px(10) // 2) + 1)).filter(ImageFilter.GaussianBlur(self.px(14))).point(lambda v: min(255, int(v * 1.6)))
        out = Image.new('RGBA', big.size, rgba(self.st['bg'])[:3] + (0,)); out.putalpha(a.point(lambda v: int(v * 0.85))); out.alpha_composite(big); return out

    def draw_caption(self, scene, c, emph, lt):
        img = self.caption_img(c, emph); y = self.px(1325)
        if self.st.get('motion') == 'soft':   # 淡入＋往上一點點
            a = clamp(lt / 0.16); y += self.px(14) * (1 - out3(lt / 0.2))
            if a < 1: img = img.copy(); img.putalpha(img.getchannel('A').point(lambda v: int(v * a)))
        else:
            s = 0.9 + 0.1 * back(lt / 0.14)
            if s != 1: img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
        scene.alpha_composite(img, (int(self.w / 2 - img.width / 2), int(y - img.height / 2)))

    def draw_hook(self, scene, hook, t):
        until = hook.get('until', 3.0)
        if t > until + 0.3: return
        if self.st.get('hook_style') == 'elegant': return self.draw_hook_elegant(scene, hook, t, until)
        if self.st.get('hook_style') == 'collage': return self.draw_hook_collage(scene, hook, t, until)
        k = back(t / 0.28, 2.2) if t < until else 1 - out3((t - until) / 0.3)
        if k <= 0.02: return
        lines = hook['text'].split('\n') if '\n' in hook['text'] else chunks(hook['text'], hook.get('max', 8))[:2]
        y = self.px(hook.get('y', 360))
        if hook.get('sub'):
            sub = self.text_img(hook['sub'], self.px(50), self.st['ink'], 'white', 0, fontp=self.fb)
            pill = Image.new('RGBA', (sub.width + self.px(50), sub.height + self.px(10))); d = ImageDraw.Draw(pill)
            d.rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], radius=pill.height // 2, fill=self.st['hl']); pill.alpha_composite(sub, (self.px(25), self.px(5)))
            self.paste_scaled(scene, pill, self.w / 2, y - self.px(80), k);
        for j, ln in enumerate(lines):
            img = self.text_img(ln, self.px(hook.get('size', 118)), self.st['accent'] if j == len(lines) - 1 and len(lines) > 1 else self.st['ink'],
                                'white', self.px(14), emph=hook.get('emph', []), hl=self.st['accent'])
            kk = back((t - 0.08 * j) / 0.28, 2.2) if t < until else k
            self.paste_scaled(scene, img, self.w / 2, y + self.px(60) + j * self.px(150), max(0, kk) * (1 + 0.5 * (1 - clamp(t / 0.2))) if t < until else kk)

    LAYOUTS = {'center': (1.12, 0.5, 880), 'left': (0.95, 0.33, 920), 'right': (0.95, 0.6, 920), 'close': (1.3, 0.5, 960),
               'low_left': (0.72, 0.32, 1080), 'low_right': (0.72, 0.6, 1080), 'small': (0.62, 0.5, 1080),
               'side_l': (0.62, 0.22, 1180), 'side_r': (0.62, 0.7, 1180)}
    MEDIA_LAY = {'card': (0.6, 0.5, 1130), 'full': (0.42, 0.7, 1170)}

    def lay_name(self, i):
        L = self.lines[i]
        if isinstance(L.get('head'), dict): return 'custom'
        if L.get('layout'): return L['layout']
        if self.st.get('stage') == 'side':   # 人物當配角：放左下／右下，每個新段落換邊
            k = sum(1 for l in self.lines[1:i + 1] if l.get('banner') or l.get('part') not in (None, self.lines[self.lines.index(l) - 1].get('part')))
            return 'side_r' if k % 2 == 0 else 'side_l'
        return 'center'

    def layout_of(self, i):
        """這句人物的 (大小, x 比例, y 像素)：素材優先，其次 head 自訂，其次 layout 版型"""
        m = self.media_mode(i)
        if m in self.MEDIA_LAY: return self.MEDIA_LAY[m]
        L = self.lines[i]; h = L.get('head')
        if isinstance(h, dict):   # 自訂：x、y 是畫面比例（0～1），size 是大小倍數
            return (float(h.get('size', 1.0)), float(h.get('x', 0.5)), float(h.get('y', 0.45)) * H)
        return self.LAYOUTS.get(self.lay_name(i), self.LAYOUTS['center'])

    def big_text(self, i):
        L = self.lines[i]; b = L.get('big')
        if b is False or b == '': return None
        if self.st.get('stage') == 'side' and L.get('banner') and not self.media_mode(i): return None   # 這句是步驟清單卡
        if b: return b
        lay = self.lay_name(i)
        if lay in ('center', 'close'): return None
        e = L.get('emph') or []
        if lay in ('side_l', 'side_r') and L.get('banner'): return None   # 有步驟清單卡就不放大字
        if e: return e[0]
        if lay in ('side_l', 'side_r') and not L.get('prop'):   # 卡片不能空著：放這句（最多 12 字，分兩行）
            t = re.sub(r'[，。！？、,.!?「」]', ' ', L['text']).split(); t = max(t, key=len) if t else L['text']
            return t[:12] if len(t) <= 6 else t[:(len(t[:12]) + 1) // 2] + '\n' + t[(len(t[:12]) + 1) // 2:12]
        return None

    def draw_big(self, scene, i, lt, left):
        txt = self.big_text(i)
        if not txt: return
        lay = self.lay_name(i); st = self.st
        if lay == 'custom':
            hx = self.layout_of(i)[1]; lay = 'left' if hx < 0.45 else 'right' if hx > 0.55 else 'small'
        stage = lay in ('side_l', 'side_r')
        side = lay in ('left', 'right')
        k = ('big', txt, side, stage)
        if k not in self._txt:
            if '\n' in txt: lines = txt.split('\n')
            elif side and len(txt) > 3: h = (len(txt) + 1) // 2; lines = [txt[:h], txt[h:]]
            else: lines = chunks(txt, 6)[:2]
            n = max(len(x) for x in lines); size = self.px(min(170 if stage else 150, int((400 if side else 760 if stage else 900) / max(1, n)), int(440 / (1.3 * len(lines))) if stage else 999))
            light = sum(hexrgb(st['accent'])) < 600
            imgs = [self.text_img(x, size, st['ink'], 'same', max(1, self.px(3)), sp=self.px(4)) for x in lines[:-1]]
            last = self.text_img(lines[-1], size, st['bg'] if light else st['ink'], 'same', max(1, self.px(3)), sp=self.px(4))
            imgs.append(self.block(last, st['accent']))   # 最後一行：色塊反白
            if stage:   # 卡片裡：深色粗字，最後一行強調色粗邊
                ac = st['accent'] if st['accent'] != '#FFE14D' else '#F26B1D'
                imgs = [self.text_img(x, size, st['ink'], 'same', max(2, int(size * 0.05)), sp=self.px(3)) for x in lines[:-1]] + [self.heavy2(lines[-1], size, ac)]
            elif st.get('big_style') == 'heavy':   # 白字粗黑邊＋往右下的陰影（拼貼風）
                imgs = [self.heavy(x, size, j == len(lines) - 1) for j, x in enumerate(lines)]
            self._txt[k] = imgs
        imgs = self._txt[k]
        cx = {'left': 0.76, 'right': 0.26}.get(lay, 0.5) * self.w
        if stage: cx = self.px((self.CARD[0] + self.CARD[2]) / 2)
        hb = getattr(self, '_head_box', None)
        if side and hb:   # 放在臉和畫面邊緣中間，不壓到臉
            wmax = max(im.width for im in imgs)
            cx = (hb[1] + self.px(960)) / 2 if lay == 'left' else (self.px(40) + hb[0]) / 2
            cx = min(max(cx, self.px(30) + wmax / 2), self.px(960) - wmax / 2)
        lh = imgs[0].height * 0.95; cy = (self.px(860) if side else self.px(615) if stage else self.px(330 if lay == 'close' else 520)) - lh * (len(imgs) - 1) / 2
        out = clamp(left / 0.2)
        for j, im in enumerate(imgs):
            tj = lt - 0.25 - 0.1 * j; a = clamp(tj / 0.25) * out
            if a <= 0: continue
            y = cy + j * lh + self.px(24) * (1 - out3(tj / 0.35))
            scene.alpha_composite(self.fade(im, a), (int(cx - im.width / 2), int(y - im.height / 2)))
        if side:   # 字下面一條短線
            a = clamp((lt - 0.5) / 0.3) * out
            if a > 0:
                d = ImageDraw.Draw(scene); yl = cy + len(imgs) * lh - lh * 0.35; hw = self.px(40) * out3((lt - 0.5) / 0.4)
                d.line([(cx - hw, yl), (cx + hw, yl)], fill=hexrgb(st['accent']) + (int(255 * a),), width=max(1, self.px(5)))

    CARD = (70, 290, 950, 880)   # 內容卡片範圍（1080 寬的座標），右邊留給平台按鈕

    def draw_card(self, scene, since):
        st = self.st
        if 'card_bg' not in self._txt:
            x0, y0, x1, y1 = [self.px(v) for v in self.CARD]; lw = self.px(7); off = self.px(14)
            im = Image.new('RGBA', (x1 - x0 + off + lw, y1 - y0 + off + lw)); d = ImageDraw.Draw(im); r = self.px(34); ink = rgba(st['ink'])
            d.rounded_rectangle([off, off, im.width - 1, im.height - 1], r, fill=ink)
            d.rounded_rectangle([0, 0, x1 - x0, y1 - y0], r, fill='#FFFFFF', outline=ink, width=lw)
            title = st.get('card_title') or (self.D.get('hook') or {}).get('text', '').replace('\n', '')
            if title:
                tt = self.text_img(title, self.px(46), st['ink'], 'same', self.px(2), sp=self.px(2))
                im.alpha_composite(tt, ((x1 - x0) // 2 - tt.width // 2, self.px(30)))
                ac = st['accent'] if st['accent'] != '#FFE14D' else '#F26B1D'
                d.line([((x1 - x0) // 2 - self.px(40), self.px(30) + tt.height + self.px(8)), ((x1 - x0) // 2 + self.px(40), self.px(30) + tt.height + self.px(8))], fill=ac, width=self.px(6))
            self._txt['card_bg'] = im
        im = self._txt['card_bg']; k = back(since / 0.35, 1.4)
        self.paste_scaled(scene, im, self.px((self.CARD[0] + self.CARD[2]) / 2) + im.width * 0.0, self.px((self.CARD[1] + self.CARD[3]) / 2) + self.px(7), k)

    def draw_steps(self, scene, i, lt, left):
        """步驟清單卡：每個有標籤的句子加一行，前面的保留，現在這行亮起來（人物當配角時用）"""
        st = self.st; rows = [(j, l['banner']) for j, l in enumerate(self.lines[:i + 1]) if l.get('banner')]
        k = ('steps', i)
        if k not in self._txt:
            f = self.px(58); W2 = self.px(820); rh = self.px(118); pad = self.px(10)
            card = Image.new('RGBA', (W2 + self.px(14), pad * 2 + rh * len(rows) + self.px(14))); d = ImageDraw.Draw(card)
            ink = rgba(st['ink']); dark = sum(hexrgb(st['bg'])) < 300
            if not self.st.get('stage') == 'side':
                d.rounded_rectangle([self.px(12), self.px(12), W2 + self.px(12), card.height - 1], self.px(28), fill=ink)
                d.rounded_rectangle([0, 0, W2, card.height - self.px(14)], self.px(28), fill='#FFFFFF', outline=ink, width=self.px(6))
            ac = st['accent'] if st['accent'] != '#FFE14D' else '#F26B1D'
            for r, (j, txt) in enumerate(rows):
                y0 = pad + r * rh; cur = j == i
                if cur: d.rounded_rectangle([self.px(18), y0 + self.px(6), W2 - self.px(18), y0 + rh - self.px(6)], self.px(20), fill=rgba(ac)[:3] + (40,), outline=ac, width=self.px(4))
                cx0 = self.px(70); cy0 = y0 + rh // 2; R = self.px(32)
                d.ellipse([cx0 - R, cy0 - R, cx0 + R, cy0 + R], fill=ac if cur else rgba(st['ink'])[:3] + (60,))
                d.text((cx0, cy0), str(r + 1), font=ImageFont.truetype(self.fB, self.px(40)), fill='#FFFFFF', anchor='mm', stroke_width=1, stroke_fill='#FFFFFF')
                tt = re.sub(r'^第\s*[0-9一二三四五六七八九十]+\s*[步招個點]\s*', '', txt) or txt
                im = self.text_img(tt, f, st['ink'] if cur else '#8A8580', 'same', self.px(2) if cur else 0, sp=self.px(2))
                card.alpha_composite(im, (self.px(124), int(cy0 - im.height / 2)))
            self._txt[k] = card
        card = self._txt[k]; a = clamp(left / 0.2)
        sc = (back(lt / 0.3, 1.6) if not any(l.get('banner') for l in self.lines[max(0, i - 3):i]) else 1.0)
        self.paste_scaled(scene, self.fade(card, a) if a < 1 else card, self.px((self.CARD[0] + self.CARD[2]) / 2), self.px(395) + card.height / 2, sc)

    def prop_start(self, L):
        hk = self.D.get('hook'); s = L['start']
        return max(s, hk.get('until', 3.0) + 0.15) if hk else s

    def card(self, img, fill, outline, tail=False, rot=0, padx=None, pady=None):
        """粗框卡片＋往右下的實心陰影（拼貼風）"""
        padx = padx or self.px(34); pady = pady or self.px(14); lw = self.px(6); off = self.px(9); th = self.px(28) if tail else 0
        w, h = img.width + padx * 2, img.height + pady * 2
        c = Image.new('RGBA', (w + off + lw * 2, h + off + lw * 2 + th)); d = ImageDraw.Draw(c); r = self.px(22)
        oc = rgba(outline)
        d.rounded_rectangle([lw + off, lw + off, lw + off + w, lw + off + h], r, fill=oc)
        d.rounded_rectangle([lw, lw, lw + w, lw + h], r, fill=fill, outline=oc, width=lw)
        if tail:
            x0 = lw + self.px(60); y0 = lw + h - lw
            d.polygon([(x0, y0), (x0 + self.px(44), y0), (x0 - self.px(6), y0 + th + self.px(6))], fill=fill)
            d.line([(x0 - self.px(6), y0 + th + self.px(6)), (x0, y0 + lw)], fill=oc, width=lw); d.line([(x0 - self.px(6), y0 + th + self.px(6)), (x0 + self.px(44), y0 + lw)], fill=oc, width=lw)
        c.alpha_composite(img, (lw + padx, lw + pady))
        return c.rotate(rot, Image.BICUBIC, expand=True) if rot else c

    def heavy2(self, txt, size, fill):
        st = self.st; sw = max(2, int(size * 0.1)); off = max(3, int(size * 0.08))
        a = self.text_img(txt, size, fill, st['ink'], sw, sp=self.px(3)); sh = self.text_img(txt, size, st['ink'], st['ink'], sw, sp=self.px(3))
        out = Image.new('RGBA', (a.width + off, a.height + off)); out.alpha_composite(sh, (off, off)); out.alpha_composite(a, (0, 0)); return out

    def heavy(self, txt, size, accent=False):
        """超粗大字：白字（或強調色）＋深色粗邊＋右下陰影"""
        st = self.st; fill = st['accent'] if accent else st.get('title_color', '#FFFFFF')
        sw = max(2, int(size * 0.09)); off = max(2, int(size * 0.07))
        a = self.text_img(txt, size, fill, st['ink'], sw, sp=self.px(2))
        sh = self.text_img(txt, size, st['ink'], st['ink'], sw, sp=self.px(2))
        out = Image.new('RGBA', (a.width + off, a.height + off)); out.alpha_composite(sh, (off, off)); out.alpha_composite(a, (0, 0)); return out

    def draw_hook_collage(self, scene, hook, t, until):
        """拼貼風開場：系列小標膠囊 → 兩行超粗標題（重點字換色）→ 斜的色帶 → 小塗鴉"""
        st = self.st; out = 1 - out3((t - until) / 0.25) if t > until else 1.0
        if out <= 0: return
        y = self.px(hook.get('y', 330)); key = ('hc', hook['text'], hook.get('sub'), hook.get('ribbon'))
        if key not in self._txt:
            parts = {}
            if hook.get('sub'):
                tx = self.text_img(hook['sub'], self.px(44), st['ink'], 'same', self.px(2), sp=self.px(2))
                dot = self.px(14); pill = Image.new('RGBA', (tx.width + dot * 2 + self.px(70), tx.height + self.px(22))); d = ImageDraw.Draw(pill)
                d.rounded_rectangle([0, 0, pill.width - 1, pill.height - 1], pill.height // 2, fill='#FFFFFF', outline=st['ink'], width=self.px(4))
                cy_ = pill.height // 2; d.ellipse([self.px(26), cy_ - dot // 2, self.px(26) + dot, cy_ + dot // 2], fill=st['accent'] if st['accent'] != '#FFE14D' else '#F26B1D')
                pill.alpha_composite(tx, (self.px(26) + dot + self.px(16), self.px(11))); parts['pill'] = pill
            lines = hook['text'].split('\n') if '\n' in hook['text'] else chunks(hook['text'], 7)[:2]
            n = max(len(x) for x in lines); size = self.px(min(140, int(940 / max(1, n))))
            em = hook.get('emph', [])
            ims = []; fx = st.get('title_fx', 'outline')
            for j, ln in enumerate(lines):
                tcol = st.get('title_color', st['ink']); hot = any(e and e in ln for e in em) or (not em and j == len(lines) - 1 and len(lines) > 1)
                if fx == 'heavy':      # 全部白字粗黑邊＋陰影，重點行黃色
                    ims.append(self.heavy2(ln, size, '#FFE14D' if hot else '#FFFFFF'))
                elif fx == 'block' and hot:   # 重點行放在色塊上反白
                    ims.append(self.block(self.text_img(ln, size, '#FFFFFF' if sum(hexrgb(st['accent'])) < 600 else st['ink'], 'same', max(2, int(size * 0.05)), sp=self.px(3)), st['accent'], self.px(30), self.px(8)))
                elif fx == 'outline' and hot:   # 重點行：強調色＋深色粗邊＋陰影
                    ims.append(self.heavy2(ln, size, st['accent'] if st['accent'] != '#FFE14D' else '#FFE14D'))
                else:
                    ims.append(self.text_img(ln, size, tcol, 'same', max(2, int(size * 0.05)), sp=self.px(3)))
            parts['title'] = ims
            if hook.get('ribbon'):
                rb = hook['ribbon']; segs = rb.split('•'); f = self.px(52)
                ts = [self.text_img(sg.strip(), f, '#FFFFFF' if j == 0 else st.get('ribbon_hl', '#FFC83D'), 'same', self.px(2), sp=self.px(2)) for j, sg in enumerate(segs)]
                dotw = self.px(40); tw = sum(x.width for x in ts) + dotw * (len(ts) - 1)
                band = Image.new('RGBA', (tw + self.px(90), ts[0].height + self.px(24))); d = ImageDraw.Draw(band); d.rectangle([0, 0, band.width, band.height], fill=st.get('ribbon', '#2449B8'))
                x = self.px(45)
                for j, im in enumerate(ts):
                    if j: d.ellipse([x + dotw // 2 - self.px(5), band.height // 2 - self.px(5), x + dotw // 2 + self.px(5), band.height // 2 + self.px(5)], fill='#FFFFFF'); x += dotw
                    band.alpha_composite(im, (x, self.px(12))); x += im.width
                parts['ribbon'] = band.rotate(-1.5, Image.BICUBIC, expand=True)
            self._txt[key] = parts
        P = self._txt[key]; yy = y
        if 'pill' in P:
            self.paste_scaled(scene, P['pill'], self.w / 2, yy - self.px(70), back(t / 0.3, 2) * out)
        lh = P['title'][0].height * 0.98
        for j, im in enumerate(P['title']):
            self.paste_scaled(scene, im, self.w / 2, yy + self.px(70) + j * lh, back((t - 0.1 - 0.1 * j) / 0.3, 2) * out)
        ty = yy + self.px(70) + len(P['title']) * lh
        if 'ribbon' in P:
            k = out3((t - 0.35) / 0.3)
            if k > 0:
                rb = P['ribbon']; vis = rb.crop((0, 0, max(1, int(rb.width * k)), rb.height))
                if out < 1: vis = self.fade(vis, out)
                scene.alpha_composite(vis, (int(self.w / 2 - rb.width / 2), int(ty - self.px(10))))
        if st.get('doodle') and t > 0.3:   # 塗鴉：左邊三條放射線、右邊閃亮星星
            a = clamp((t - 0.3) / 0.2) * out; d = ImageDraw.Draw(scene); oc = hexrgb(st['accent'] if st['accent'] != '#FFE14D' else '#1E1E1E') + (int(255 * a),)
            w0 = P['title'][0].width; x0 = self.w / 2 - w0 / 2 - self.px(30); y0 = yy + self.px(10); lw = self.px(9)
            for ang in (200, 235, 270):
                r1, r2 = self.px(20), self.px(70); ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                d.line([(x0 + ca * r1, y0 + sa * r1), (x0 + ca * r2, y0 + sa * r2)], fill=oc, width=lw)
            sx = self.w / 2 + w0 / 2 + self.px(50); sy = yy - self.px(40); R = self.px(34) * (0.9 + 0.1 * math.sin(t * 6)); r = R * 0.28
            pts = [(sx + (R if q % 2 == 0 else r) * math.cos(math.radians(q * 45 - 90)), sy + (R if q % 2 == 0 else r) * math.sin(math.radians(q * 45 - 90))) for q in range(8)]
            d.polygon(pts, fill=(255, 255, 255, int(255 * a)), outline=hexrgb(st['ink']) + (int(255 * a),), width=self.px(5))

    def block(self, img, color, padx=None, pady=None):
        """字放在色塊上（重點字用，比較吸睛）"""
        padx = padx or self.px(26); pady = pady or self.px(4)
        b = Image.new('RGBA', (img.width + padx * 2, img.height + pady * 2)); d = ImageDraw.Draw(b)
        d.rounded_rectangle([0, pady + img.height * 0.08, b.width - 1, b.height - 1 - img.height * 0.04], radius=self.px(14), fill=color)
        b.alpha_composite(img, (padx, pady)); return b

    def fade(self, img, a):
        if a >= 1: return img
        img = img.copy(); img.putalpha(img.getchannel('A').point(lambda v: int(v * max(0, a)))); return img

    def draw_hook_elegant(self, scene, hook, t, until):
        """高級感開場：小標細線＋大字淡入往上，不彈跳"""
        st = self.st; out = 1 - out3((t - until) / 0.3) if t > until else 1.0
        lines = hook['text'].split('\n') if '\n' in hook['text'] else chunks(hook['text'], hook.get('max', 8))[:2]
        y = self.px(hook.get('y', 380))
        if hook.get('sub'):
            k = ('hsub', hook['sub'])
            if k not in self._txt:
                sub = self.text_img(hook['sub'], self.px(40), st['accent'], 'same', 0, fontp=self.fb, sp=self.px(8))
                L = self.px(56); g = self.px(22); im = Image.new('RGBA', (sub.width + 2 * (L + g), sub.height)); d = ImageDraw.Draw(im)
                lw = max(1, self.px(3)); cy = sub.height // 2
                d.line([(0, cy), (L, cy)], fill=st['accent'], width=lw); d.line([(im.width - L, cy), (im.width, cy)], fill=st['accent'], width=lw)
                im.alpha_composite(sub, (L + g, 0)); self._txt[k] = im
            a = clamp(t / 0.3) * out; im = self.fade(self._txt[k], a)
            scene.alpha_composite(im, (int(self.w / 2 - im.width / 2), int(y - self.px(70) - im.height / 2 + self.px(16) * (1 - out3(t / 0.35)))))
        for j, ln in enumerate(lines):
            last = j == len(lines) - 1 and len(lines) > 1
            light = sum(hexrgb(st['accent'])) < 600
            if last:
                img = self.block(self.text_img(ln, self.px(hook.get('size', 124)), st['bg'] if light else st['ink'], 'same', self.px(3), sp=self.px(4)), st['accent'], self.px(30), self.px(6))
            else:
                img = self.text_img(ln, self.px(hook.get('size', 124)), st['ink'], 'same', self.px(3), emph=hook.get('emph', []), hl=st['accent'], sp=self.px(4))
            tj = t - 0.12 - 0.1 * j; a = clamp(tj / 0.3) * out
            if a <= 0: continue
            yy = y + self.px(40) + j * self.px(160) + self.px(26) * (1 - out3(tj / 0.4))
            scene.alpha_composite(self.fade(img, a), (int(self.w / 2 - img.width / 2), int(yy - img.height / 2)))

    def draw_banner(self, scene, text, lt, left):
        bs = self.st.get('banner_style', 'solid')
        if bs == 'bubble':   # 對話框：白底粗框＋小尾巴＋陰影
            k = ('bub', text)
            if k not in self._txt:
                st = self.st; t = self.text_img(text, self.px(56), st['ink'], 'same', self.px(3), sp=self.px(3))
                self._txt[k] = self.card(t, '#FFFFFF', st['ink'], tail=True)
            tag = self._txt[k]; sc = back(lt / 0.3, 2.0) * clamp(left / 0.15)
            self.paste_scaled(scene, tag, self.w / 2, self.px(300), sc); return
        if bs != 'solid':   # 高級感標籤：淡入、細框或細線，不從旁邊飛進來
            k = ('ban', text, bs)
            if k not in self._txt:
                st = self.st
                if bs == 'outline':
                    img = self.text_img(text, self.px(48), st['accent'], 'same', self.px(1), sp=self.px(4))
                    tag = Image.new('RGBA', (img.width + self.px(64), img.height + self.px(18))); d = ImageDraw.Draw(tag)
                    fill = rgba(st['bg']) [:3] + (235,)
                    d.rounded_rectangle([0, 0, tag.width - 1, tag.height - 1], radius=tag.height // 2, fill=fill, outline=st['accent'], width=max(1, self.px(3)))
                    tag.alpha_composite(img, (self.px(32), self.px(9)))
                else:   # line：細線＋字
                    img = self.text_img(text, self.px(46), st['accent'], 'same', self.px(1), sp=self.px(6))
                    L = self.px(70); g = self.px(20); tag = Image.new('RGBA', (img.width + 2 * (L + g), img.height)); d = ImageDraw.Draw(tag)
                    cy = img.height // 2; lw = max(1, self.px(3))
                    d.line([(0, cy), (L, cy)], fill=st['accent'], width=lw); d.line([(tag.width - L, cy), (tag.width, cy)], fill=st['accent'], width=lw)
                    tag.alpha_composite(img, (L + g, 0))
                self._txt[k] = tag
            tag = self._txt[k]; a = clamp(lt / 0.25) * clamp(left / 0.2)
            y = self.px(300) - self.px(12) * (1 - out3(lt / 0.3))
            scene.alpha_composite(self.fade(tag, a), (int(self.w / 2 - tag.width / 2), int(y - tag.height / 2)))
            return
        img = self.text_img(text, self.px(64), 'white', self.st['accent'], 0)
        tag = Image.new('RGBA', (img.width + self.px(60), img.height + self.px(16))); d = ImageDraw.Draw(tag)
        d.rounded_rectangle([0, 0, tag.width - 1, tag.height - 1], radius=self.px(22), fill=self.st['accent'], outline='white', width=self.px(6))
        tag.alpha_composite(img, (self.px(30), self.px(8)))
        x = self.w / 2 - self.px(900) * (1 - out3(lt / 0.3)) + self.px(900) * (1 - out3(left / 0.25)) if left < 0.25 else self.w / 2 - self.px(900) * (1 - out3(lt / 0.3))
        scene.alpha_composite(tag, (int(x - tag.width / 2), int(self.px(300) - tag.height / 2)))

    def paste_scaled(self, scene, img, cx, cy, s):
        if s <= 0.02: return
        if abs(s - 1) > 0.01: img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
        scene.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))

    # ---------- 音效 ----------
    def sfx_events(self):
        ev = []
        if self.D.get('hook'): ev += [(0.02, 'r_whoosh', .3), (0.2, 'pop', .3)]
        for i, l in enumerate(self.lines):
            s = l['start']; want = l.get('sfx')
            if want == 'none': continue
            if want:
                for w in ([want] if isinstance(want, str) else want): ev.append((max(0, s - 0.03), w, .32))
            else:
                if i > 0 and l.get('face') != self.lines[i - 1].get('face'): ev.append((max(0, s - 0.02), 'pop', .22))
                if l.get('cam') == 'shake': ev.append((s, 'boom', .35))
                if l.get('cam') == 'punch': ev.append((s, 'r_pop', .3))
                if not self.trans_of(i) and (l.get('cam') in ('slide_l', 'slide_r') or (l.get('banner') and not (self.D.get('hook') and s < self.D['hook'].get('until', 3)))): ev.append((s, 'whoosh', .25))
            if self.trans_of(i): ev.append((max(0, s - 0.05), 'whoosh_long' if self.trans_of(i) == 'zoom' else 'r_whoosh', .3))
            props = l.get('prop') or []
            ps = self.prop_start(l)
            if self.big_text(i) and not self.media_mode(i) and not l.get('prop_pos'): props = []
            if ps < l['end']:
                for k, _ in enumerate([props] if isinstance(props, str) else props): ev.append((ps + 0.12 + 0.18 * k, 'bloop', .24))
        return ev

    # ---------- 輸出 ----------
    def render(self, out, stills=None):
        self.cplan = self.caption_plan()
        if stills:
            os.makedirs(os.path.join(self.base, 'check'), exist_ok=True); outs = []
            for s in stills:
                p = os.path.join(self.base, 'check', f'still_{s:06.2f}.png'); self.frame(int(s * FPS)).save(p); outs.append(p)
            print('\n'.join(outs)); return outs
        nf = int(self.dur * FPS); tmpv = out + '.video.mp4'
        crf = '20' if self.S >= 1 else '26'
        pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{self.w}x{self.h}', '-r', str(FPS), '-i', '-',
                               '-c:v', 'libx264', '-preset', 'medium' if self.S >= 1 else 'veryfast', '-crf', crf, '-pix_fmt', 'yuv420p', tmpv], stdin=subprocess.PIPE)
        for fi in range(nf):
            pr.stdin.write(self.frame(fi).tobytes())
            if fi % (FPS * 5) == 0: print(f'  算圖 {fi / FPS:5.1f}/{self.dur:.1f} 秒', flush=True)
        pr.stdin.close(); pr.wait()
        if pr.returncode: raise SystemExit('ffmpeg 編碼失敗')
        # 音軌：人聲＋音效＋配樂（自動閃避）
        sfxw = os.path.join(self.base, 'sfx.wav'); SFX.build(self.sfx_events(), self.dur, sfxw)
        ins = ['-i', tmpv]; fl = []; n = 1
        if self.D.get('voice'):
            ins += ['-i', os.path.join(self.base, self.D['voice'])]; fl.append(f'[{n}:a]aresample=48000,pan=stereo|c0=c0|c1=c0,highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=80[v]'); n += 1
        else:
            fl.append(f'anullsrc=r=48000:cl=stereo,atrim=0:{self.dur}[v]')
        ins += ['-i', sfxw]; fl.append(f'[{n}:a]volume={self.D.get("sfx_gain", 0.8)}[s]'); n += 1
        bgm = self.D.get('bgm')
        if bgm:
            bp = bgm if os.path.isabs(bgm) else os.path.join(self.base, bgm)
            ins += ['-stream_loop', '-1', '-i', bp]
            fl.append(f'[{n}:a]aresample=48000,volume={self.D.get("bgm_db", -20)}dB,atrim=0:{self.dur},afade=t=out:st={max(0, self.dur - 1.5)}:d=1.5[b0]')
            fl.append('[v]asplit[v][vk]'); fl.append('[b0][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=300[b]')
            fl.append('[v][s][b]amix=inputs=3:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]')
        else:
            fl.append('[v][s]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[a]')
        run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
             '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-t', f'{self.dur:.3f}', '-movflags', '+faststart', out])
        os.remove(tmpv)
        print(f'✓ 出片完成：{out}（{self.dur:.1f} 秒，{self.w}×{self.h}）')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('director'); ap.add_argument('--preview', action='store_true'); ap.add_argument('--out')
    ap.add_argument('--stills', help='逗號分隔秒數，只輸出靜態畫面')
    a = ap.parse_args()
    r = R(a.director, 0.5 if a.preview else 1.0)
    base = os.path.dirname(os.path.abspath(a.director))
    out = a.out or os.path.join(base, 'preview.mp4' if a.preview else 'final.mp4')
    r.render(out, [float(x) for x in a.stills.split(',')] if a.stills else None)
