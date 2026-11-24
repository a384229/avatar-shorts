"""內建配樂產生器：用程式即時合成背景音樂（沒有版權問題，可商用）。
  python music.py list                                   看有哪些風格
  python music.py make 輕快 --sec 30 --out bgm.wav        做一首 30 秒的配樂
  python music.py make 可愛 --director videos/片名/director.json   長度自動配合影片，並寫進導演表 bgm
風格：輕快（明亮流行）、可愛（木琴、彈跳）、科技（電子琶音）、溫馨（鋼琴慢板）、熱血（重拍、加速感）
只用 numpy。"""
import argparse, json, os, sys, wave
import numpy as np

SR = 44100
STYLES = {
    '輕快': dict(bpm=112, key=0, mode='major', prog=[0, 4, 5, 3], lead='pluck', drums='pop', pad=.18, desc='明亮流行，適合教學、清單、生活技巧'),
    '可愛': dict(bpm=122, key=5, mode='major', prog=[0, 3, 4, 0], lead='marimba', drums='light', pad=.10, desc='木琴彈跳感，適合輕鬆、搞笑、萌系'),
    '科技': dict(bpm=118, key=9, mode='minor', prog=[0, 5, 3, 4], lead='arp', drums='tech', pad=.22, desc='電子琶音，適合 AI、工具、科技、商業'),
    '溫馨': dict(bpm=84, key=7, mode='major', prog=[0, 5, 3, 4], lead='piano', drums='none', pad=.25, desc='鋼琴慢板，適合故事、感謝、心情'),
    '熱血': dict(bpm=128, key=2, mode='minor', prog=[0, 5, 6, 4], lead='saw', drums='rock', pad=.2, desc='重拍有衝勁，適合挑戰、成果、激勵'),
}
SCALE = {'major': [0, 2, 4, 5, 7, 9, 11], 'minor': [0, 2, 3, 5, 7, 8, 10]}


def hz(n): return 440 * 2 ** ((n - 69) / 12)
def env(n, a=.005, d=.3, s=0.0, total=None):
    t = np.arange(n) / SR; e = np.minimum(1, t / a) * (s + (1 - s) * np.exp(-t / d)); return e


def tone(f, dur, kind):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == 'pluck': y = np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t) + .15 * np.sin(6 * np.pi * f * t); return y * env(n, .003, .18)
    if kind == 'marimba': y = np.sin(2 * np.pi * f * t) + .25 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t / .03); return y * env(n, .002, .22)
    if kind == 'arp': ph = (f * t) % 1; y = (2 * ph - 1) * .5 + np.sign(np.sin(2 * np.pi * f * t)) * .25; return _lp(y, .25) * env(n, .003, .12)
    if kind == 'piano': y = sum(g * np.sin(2 * np.pi * f * k * t) * np.exp(-t * k * .8) for k, g in [(1, 1), (2, .4), (3, .2), (4, .08)]); return y * env(n, .004, .9)
    if kind == 'saw': ph = (f * t) % 1; return _lp(2 * ph - 1, .18) * env(n, .004, .25, .3)
    if kind == 'pad': y = sum(np.sin(2 * np.pi * f * (1 + dt) * t) for dt in (-.004, 0, .004)) / 3; return y * np.minimum(1, t / .3) * np.minimum(1, (dur - t) / .3 + .01)
    if kind == 'bass': y = np.sin(2 * np.pi * f * t) + .3 * np.sin(4 * np.pi * f * t); return y * env(n, .004, .35, .4)


def _lp(x, a):
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y


def drum(kind, rng):
    if kind == 'kick': n = int(.3 * SR); t = np.arange(n) / SR; f = 50 + 110 * np.exp(-t * 30); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    if kind == 'snare': n = int(.2 * SR); t = np.arange(n) / SR; return (rng.normal(0, 1, n) * .7 + np.sin(2 * np.pi * 190 * t) * .4) * np.exp(-t * 22)
    if kind == 'hat': n = int(.05 * SR); x = rng.normal(0, 1, n); x = x - _lp(x, .4); return x * np.exp(-np.arange(n) / SR * 90) * .5
    if kind == 'clap': n = int(.15 * SR); x = rng.normal(0, 1, n); return (x - _lp(x, .2)) * np.exp(-np.arange(n) / SR * 25)


def make(style, sec):
    st = STYLES[style]; rng = np.random.default_rng(7); beat = 60 / st['bpm']; bar = beat * 4
    bars = int(np.ceil(sec / bar)) + 1; L = int(bars * bar * SR) + SR; mix = np.zeros(L)
    sc = SCALE[st['mode']]; root = 48 + st['key']
    def put(y, t, g):
        i = int(t * SR); mix[i:i + len(y)] += y[:max(0, L - i)] * g
    for b in range(bars):
        deg = st['prog'][b % 4]; chord = [root + 12 + sc[(deg + k) % 7] + 12 * ((deg + k) // 7) for k in (0, 2, 4)]
        t0 = b * bar
        if st['pad']:
            for n in chord: put(tone(hz(n), bar, 'pad'), t0, st['pad'] / 3)
        put(tone(hz(chord[0] - 12), beat * 1.8, 'bass'), t0, .35); put(tone(hz(chord[0] - 12), beat * 1.8, 'bass'), t0 + beat * 2, .3)
        # 旋律：和弦音型（每拍 2 個音），每 2 小節換花樣
        pat = [0, 1, 2, 1, 2, 3, 2, 1] if b % 2 == 0 else [2, 1, 0, 1, 3, 2, 1, 2]
        step = beat / 2 if st['lead'] != 'piano' else beat
        cnt = int(bar / step)
        for k in range(cnt):
            n = chord[pat[k % 8] % 3] + (12 if pat[k % 8] == 3 else 0) + 12
            put(tone(hz(n), step * 1.6, st['lead']), t0 + k * step, .16 if st['lead'] != 'piano' else .2)
        d = st['drums']
        if d == 'none': continue
        for k in range(4):
            tb = t0 + k * beat
            if d in ('pop', 'tech', 'rock') or (d == 'light' and k in (0, 2)): put(drum('kick', rng), tb, .55 if d != 'light' else .35)
            if k in (1, 3): put(drum('clap' if d in ('pop', 'light') else 'snare', rng), tb, .25 if d == 'light' else .3)
            put(drum('hat', rng), tb + beat / 2, .18)
            if d in ('tech', 'rock'): put(drum('hat', rng), tb, .12)
    y = mix[:int(sec * SR)]
    fo = int(min(1.5, sec / 4) * SR); y[-fo:] *= np.linspace(1, 0, fo); fi = int(.05 * SR); y[:fi] *= np.linspace(0, 1, fi)
    y = y / (np.max(np.abs(y)) + 1e-9) * .8
    st2 = np.stack([y, np.roll(y, int(.012 * SR)) * .9 + y * .1], 1)   # 一點立體感
    return st2


def save(y, out):
    w = wave.open(out, 'w'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('list')
    p = sp.add_parser('make'); p.add_argument('style', choices=list(STYLES)); p.add_argument('--sec', type=float, default=30); p.add_argument('--out'); p.add_argument('--director')
    a = ap.parse_args()
    if a.cmd == 'list':
        for k, v in STYLES.items(): print(f'{k}：{v["desc"]}（{v["bpm"]} BPM）')
        sys.exit()
    sec = a.sec
    if a.director:
        D = json.load(open(a.director, encoding='utf-8')); sec = D.get('duration') or sec
        out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.director)), f'bgm_{a.style}.wav')
    else:
        out = a.out or f'bgm_{a.style}.wav'
    save(make(a.style, sec), out)
    if a.director:
        D['bgm'] = os.path.basename(out); D.setdefault('bgm_db', -20)
        json.dump(D, open(a.director, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print('已寫進導演表 bgm（講話時會自動變小聲）')
    print(f'✓ 配樂 {a.style} {sec:.1f} 秒 → {out}')
