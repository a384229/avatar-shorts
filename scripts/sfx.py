"""可愛音效合成（不用下載素材）。名稱：pop bloop ding ding_hi ding_top boing sparkle whoosh whoosh_long tick boom glitch glass
用法：from sfx import build; build([(0.3,'whoosh',.22),(0.55,'bloop',.3)], dur=18.0, out='sfx.wav')
音量（第三個數字）是峰值，0.2–0.4 之間；人聲 -15 LUFS 時大約落在人聲下方 12 dB。"""
import numpy as np, wave
SR = 48000
def _env(n, a=.004, d=.15):
    t = np.arange(n) / SR; return np.minimum(1, t / a) * np.exp(-t / d)
def _tone(f0, f1, dur, d=.1, harm=()):
    n = int(dur * SR); t = np.arange(n) / SR; f = f0 * (f1 / f0) ** (t / dur); ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph)
    for k, g in harm: y += g * np.sin(k * ph)
    return y * _env(n, .003, d)
def _bell(f, dur=1.2, d=.35):
    n = int(dur * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for r, g, dd in [(1, 1, d), (2.0, .45, d * .6), (3.01, .25, d * .4), (4.2, .12, d * .25)]: y += g * np.sin(2 * np.pi * f * r * t) * np.exp(-t / dd)
    return y * np.minimum(1, t / .002)
def _whoosh(dur=.42):
    n = int(dur * SR); x = np.random.default_rng(3).standard_normal(n); t = np.arange(n) / SR
    y = np.zeros(n); lp = lp2 = 0
    for i in range(n):
        fc = 600 + 3400 * np.sin(np.pi * i / n); a = np.exp(-2 * np.pi * fc / SR)
        lp = (1 - a) * x[i] + a * lp; lp2 = (1 - a) * lp + a * lp2; y[i] = lp - lp2 * .6
    return y * np.sin(np.pi * t / dur) ** 2
def _ding(f):
    b = _bell(f, .9, .22) * .8; k = _tone(f * .5, f * .5, .05, d=.02) * .2; b[:len(k)] += k; return b
def _boing():
    n = int(.45 * SR); t = np.arange(n) / SR; f = 300 + 260 * np.exp(-t / .12) * np.cos(2 * np.pi * 14 * t) + 90 * np.exp(-t / .2)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, .003, .16)
def _sparkle():
    out = np.zeros(int(1.3 * SR))
    for k, f in enumerate([1568, 2093, 2637, 3136]):
        b = _bell(f, 1.0, .25) * .5; s = int(k * .06 * SR); out[s:s + len(b)] += b[:len(out) - s]
    return out
LIB = {'pop': lambda: _tone(380, 1150, .09, d=.035, harm=[(2, .15)]), 'bloop': lambda: _tone(520, 1500, .14, d=.06, harm=[(2, .2)]),
       'ding': lambda: _ding(1319), 'ding_hi': lambda: _ding(1568), 'ding_top': lambda: _ding(1760), 'boing': _boing, 'sparkle': _sparkle,
       'whoosh': lambda: _whoosh(.42), 'whoosh_long': lambda: _whoosh(.6), 'tick': lambda: _tone(2400, 2400, .03, d=.01)}

# Reels 特效包原本的音效（R 特效用）
_rng = np.random.default_rng(1)
def _lp(x, a):
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s += a * (x[i] - s); y[i] = s
    return y
def _tt(d): return np.arange(int(SR * d)) / SR
def _r_whoosh():
    d = .45; t = _tt(d); n = _rng.normal(0, 1, len(t)); env = np.sin(np.pi * t / d) ** 2; m = t / d
    return (_lp(n, .03) * (1 - m) * 3 + (n - _lp(n, .25)) * m * .8) * env * .5
def _r_pop():
    t = _tt(.12); f = 900 * np.exp(-t * 30) + 280; return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35) * .6
def _r_click():
    t = _tt(.03); n = _rng.normal(0, 1, len(t)); return (n - _lp(n, .3)) * np.exp(-t * 250) * .5
def _r_ding():
    t = _tt(.9); return (np.sin(2 * np.pi * 1318 * t) + .4 * np.sin(2 * np.pi * 2637 * t) + .2 * np.sin(2 * np.pi * 1976 * t)) * np.exp(-t * 5) * .28
LIB.update({'r_whoosh': _r_whoosh, 'r_pop': _r_pop, 'r_click': _r_click, 'r_ding': _r_ding})

# 補充：重擊、故障、碎玻璃（F04／F05／K04／K05、M04、K11 用）
def _boom():
    t = _tt(.6); f = 55 + 90 * np.exp(-t * 18); y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
    n = _rng.normal(0, 1, len(t)); y += _lp(n, .08) * np.exp(-t * 40) * 1.5; return y
def _glitch():
    out = np.zeros(int(.4 * SR)); seg = int(.04 * SR)
    for k in range(8):
        f = [180, 900, 2400, 400, 1600, 120, 3000, 700][k]; t = _tt(.04)
        sq = np.sign(np.sin(2 * np.pi * f * t)) * (.6 if k % 2 else .35); out[k * seg:k * seg + len(sq)] += sq[:len(out) - k * seg]
    return out * np.linspace(1, .4, len(out))
def _glass():
    out = np.zeros(int(1.0 * SR))
    for k in range(14):
        f = 2500 + _rng.random() * 4500; b = _bell(f, .5, .05 + _rng.random() * .08) * (.3 + _rng.random() * .4)
        s = int(_rng.random() * .25 * SR); out[s:s + len(b)] += b[:len(out) - s]
    n = _rng.normal(0, 1, int(.08 * SR)); out[:len(n)] += (n - _lp(n, .3)) * np.exp(-_tt(.08) * 40)
    return out
LIB.update({'boom': _boom, 'glitch': _glitch, 'glass': _glass})

def build(events, dur, out):
    L = int((dur + 1.5) * SR); mix = np.zeros(L)
    for t, name, g in events:
        s = LIB[name](); s = s / np.max(np.abs(s)) * g; i = int(t * SR); mix[i:i + len(s)] += s[:max(0, L - i)]
    st = np.clip(np.stack([mix, mix], 1), -1, 1)
    w = wave.open(out, 'w'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((st * 32767).astype(np.int16).tobytes()); w.close()
