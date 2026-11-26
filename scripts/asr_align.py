"""用語音辨識把「自己錄的整篇旁白」對到導演表每一句（比只看停頓準：句子黏在一起、念錯重念都對得上）。
voice.py align 會自動呼叫；第一次用會自動安裝 sherpa-onnx、pypinyin，並下載中文辨識模型（約 80MB，存在 ~/.cache/avatar-anim-video/）。
全部在本機跑，不用金鑰、不上傳聲音。"""
import os, subprocess, sys, tarfile, urllib.request
import numpy as np

MODEL = 'sherpa-onnx-paraformer-zh-small-2024-03-09'
URL = f'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL}.tar.bz2'
CACHE = os.path.join(os.path.expanduser('~'), '.cache', 'avatar-anim-video')
SR = 16000
PUNCT = set('，。！？、；：,.!?;:…「」『』（）()"\'～~— \t')


def _pip(mod, pkg):
    try: return __import__(mod)
    except ImportError:
        print(f'  第一次使用，安裝 {pkg}…'); subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg], check=True)
        return __import__(mod)


def model_dir():
    for d in [os.environ.get('AVATAR_ASR_MODEL', ''), os.path.join(CACHE, MODEL)]:
        if d and os.path.exists(os.path.join(d, 'model.int8.onnx')): return d
    os.makedirs(CACHE, exist_ok=True); tb = os.path.join(CACHE, MODEL + '.tar.bz2')
    print('  第一次使用，下載中文語音辨識模型（約 80MB）…')
    urllib.request.urlretrieve(URL, tb)
    with tarfile.open(tb) as t: t.extractall(CACHE)
    os.remove(tb); return os.path.join(CACHE, MODEL)


def recognizer():
    _pip('pypinyin', 'pypinyin'); so = _pip('sherpa_onnx', 'sherpa-onnx'); d = model_dir()
    return so.OfflineRecognizer.from_paraformer(paraformer=os.path.join(d, 'model.int8.onnx'), tokens=os.path.join(d, 'tokens.txt'), num_threads=4)


def load_pcm(path):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True)
    return np.frombuffer(r.stdout, np.float32)


def speech_chunks(x, gap=0.12, db=-35):
    """依很短的停頓切成小段（之後用辨識結果決定哪幾段屬於哪一句）"""
    hop = int(SR * 0.02); n = len(x) // hop
    rms = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    thr = max(db, np.percentile(rms, 95) - 32)
    on = rms > thr; segs = []; s = None; quiet = 0
    for i, v in enumerate(on):
        if v:
            if s is None: s = i
            quiet = 0
        elif s is not None:
            quiet += 1
            if quiet * 0.02 >= gap: segs.append([s * 0.02, (i - quiet + 1) * 0.02]); s = None; quiet = 0
    if s is not None: segs.append([s * 0.02, n * 0.02])
    out = []
    for a, b in segs:   # 太短的併到前一段
        if out and (b - a < 0.25 or a - out[-1][1] < 0.05): out[-1][1] = b
        else: out.append([a, b])
    return out


def norm(text):
    from pypinyin import lazy_pinyin
    chars = [c for c in text if c not in PUNCT]
    return [p.lower() for p in lazy_pinyin(''.join(chars))]


def _cost(p, q):
    if p == q: return 0
    if p[:1] == q[:1] or p[-2:] == q[-2:]: return 1
    return 2


def align_lines(audio, lines):
    """回傳每句 [start, end] 秒數；lines 是台詞字串清單"""
    rec = recognizer(); x = load_pcm(audio); chunks = speech_chunks(x)
    hyp, htime = [], []   # 每小段辨識，字的時間在段內平均分配
    for a, b in chunks:
        s = rec.create_stream(); s.accept_waveform(SR, x[int(a * SR):int(b * SR)]); rec.decode_stream(s)
        py = norm(s.result.text)
        for k, p in enumerate(py):
            hyp.append(p); htime.append((a + (b - a) * k / len(py), a + (b - a) * (k + 1) / len(py)))
    if not hyp: raise RuntimeError('辨識不到任何聲音')
    ref, owner = [], []
    for i, t in enumerate(lines):
        py = norm(t); ref += py; owner += [i] * len(py)
    # 全域對齊：同音 0、相似音 1、不同 2；腳本字沒念到 1；錄音多出來的字（念錯重念）0.6
    n, m = len(ref), len(hyp); D = np.zeros((n + 1, m + 1)); D[:, 0] = np.arange(n + 1); D[0, :] = np.arange(m + 1) * 0.6
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j - 1] + _cost(ref[i - 1], hyp[j - 1]), D[i - 1, j] + 1, D[i, j - 1] + 0.6)
    i, j, match = n, m, {}
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + _cost(ref[i - 1], hyp[j - 1]): match[i - 1] = j - 1; i -= 1; j -= 1
        elif D[i, j] == D[i, j - 1] + 0.6: j -= 1
        else: i -= 1
    spans, lead, trail = [], [], []
    for li in range(len(lines)):
        ks = [k for k in range(n) if owner[k] == li]; js = [match[k] for k in ks if k in match]
        spans.append([htime[min(js)][0], htime[max(js)][1]] if js else None)
        lead.append(next((c for c, k in enumerate(ks) if k in match), len(ks)))             # 句首有幾個字沒對到
        trail.append(next((c for c, k in enumerate(reversed(ks)) if k in match), len(ks)))  # 句尾有幾個字沒對到
    for li, sp in enumerate(spans):   # 完全沒對到的句子：用前後句內插
        if sp is None:
            a = spans[li - 1][1] if li and spans[li - 1] else 0
            b = next((s[0] for s in spans[li + 1:] if s), len(x) / SR); spans[li] = [a, b]
    # 沒被任何句子用到的小段（太短辨識不出來，例如「第二步」）：給句首或句尾缺字的那句
    for a, b in chunks:
        if any(sp[0] < b - 0.02 and sp[1] > a + 0.02 for sp in spans): continue
        nxt = next((k for k, sp in enumerate(spans) if sp[0] >= b - 0.02), None)
        prv = max((k for k, sp in enumerate(spans) if sp[1] <= a + 0.02), default=None)
        pick = nxt if prv is None else prv if nxt is None else (nxt if lead[nxt] >= trail[prv] else prv)
        if pick is None: continue
        spans[pick][0] = min(spans[pick][0], a); spans[pick][1] = max(spans[pick][1], b)
    starts = [c[0] for c in chunks]; ends = [c[1] for c in chunks]
    def snap(t, edges, lim=0.15):
        e = min(edges, key=lambda v: abs(v - t)); return e if abs(e - t) <= lim else t
    out = [[snap(a, starts), snap(b, ends)] for a, b in spans]
    for k in range(1, len(out)):   # 不重疊
        if out[k][0] < out[k - 1][1]: mid = (out[k][0] + out[k - 1][1]) / 2; out[k - 1][1] = mid; out[k][0] = mid
    return refine(x, out, [norm(t) for t in lines], rec)


def frame_db(x, hop=0.01):
    h = int(SR * hop); n = len(x) // h
    return 20 * np.log10(np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)


def _py(rec, y):
    if len(y) < SR * 0.25: return []
    s = rec.create_stream(); s.accept_waveform(SR, y); rec.decode_stream(s); return norm(s.result.text)


def _edge_score(prev_ref, next_ref, hp, hn):
    """切點好不好：前段結尾＝上一句最後的字、後段開頭＝下一句開頭的字；字跑錯邊扣分"""
    ok = lambda a, b: _cost(a, b) <= 1
    sc = 0.0
    if prev_ref and hp:
        sc += ok(prev_ref[-1], hp[-1]) + 0.5 * (len(prev_ref) > 1 and len(hp) > 1 and ok(prev_ref[-2], hp[-2]))
        if next_ref and ok(next_ref[0], hp[-1]) and not ok(prev_ref[-1], hp[-1]): sc -= 1.5   # 下一句的字跑到這句尾巴
    if next_ref and hn:
        sc += ok(next_ref[0], hn[0]) + 0.5 * (len(next_ref) > 1 and len(hn) > 1 and ok(next_ref[1], hn[1]))
        if prev_ref and ok(prev_ref[-1], hn[0]) and not ok(next_ref[0], hn[0]): sc -= 1.5     # 上一句的字跑到下一句開頭
    return sc


def refine(x, spans, refs, rec, win=0.3, look=1.6):
    """句子黏在一起時（中間沒停頓），切點改到估計點 ±0.3 秒內最安靜的地方（10ms 一格），
    再用辨識檢查前後兩句的頭尾字有沒有跑錯邊（字被切半、整個詞跑到下一句），選最好的切點；
    ±0.3 秒內找不到頭尾都對的切點，就放寬到 ±0.8 秒再找一次。"""
    db = frame_db(x); hop = 0.01; out = [list(v) for v in spans]

    def score(k, f):
        c = f * hop; d = db[min(f, len(db) - 1)]
        hp = _py(rec, x[int(max(out[k - 1][0], c - look) * SR):int(c * SR)])
        hn = _py(rec, x[int(c * SR):int(min(out[k][1], c + look) * SR)])
        return _edge_score(refs[k - 1], refs[k], hp, hn) + (0.3 if d < -40 else 0) + max(0, -40 - d) * 0.005

    for k in range(1, len(out)):
        a, b = out[k - 1][1], out[k][0]
        if b - a > 0.12: continue   # 中間本來就有停頓，不用動
        t0 = (a + b) / 2; f0 = int(round(t0 / hop)); best = (score(k, f0), f0); full = 3.3
        for w in (win, 0.8):
            if best[0] >= full - 0.5: break
            lo = max(int((t0 - w) / hop), int(out[k - 1][0] / hop) + 20); hi = min(int((t0 + w) / hop), int(out[k][1] / hop) - 20, len(db) - 2)
            if hi <= lo: continue
            seg = db[lo:hi + 1]
            mins = [lo + i for i in range(1, len(seg) - 1) if seg[i] <= seg[i - 1] and seg[i] <= seg[i + 1]]
            for f in sorted(set(sorted(mins, key=lambda f: db[f])[:6 if w == win else 10])):
                sc = score(k, f)
                if sc > best[0] + 1e-6: best = (sc, f)
        out[k - 1][1] = out[k][0] = best[1] * hop
    return out


def compare(lines, audios):
    """每句錄音再辨識一次，跟腳本比：回傳 [(第幾句, 腳本, 辨識到的字, 不一樣的地方)]（字幕要照實際念的改）"""
    import difflib
    rec = recognizer(); res = []
    for i, (t, f) in enumerate(zip(lines, audios), 1):
        y = load_pcm(f); s = rec.create_stream(); s.accept_waveform(SR, y); rec.decode_stream(s); heard = s.result.text.strip()
        r, h = norm(t), norm(heard)
        sm = difflib.SequenceMatcher(None, r, h, autojunk=False); diff = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal': continue
            if op == 'replace' and i2 - i1 == j2 - j1 and all(_cost(r[a], h[b]) <= 1 for a, b in zip(range(i1, i2), range(j1, j2))): continue   # 只是辨識成近音字
            diff.append((op, ' '.join(r[i1:i2]), ' '.join(h[j1:j2])))
        res.append((i, t, heard, diff))
    return res


def recognize(path):
    """辨識單一檔案（自查用：確認每句錄音念的是哪句）"""
    rec = recognizer(); s = rec.create_stream(); s.accept_waveform(SR, load_pcm(path)); rec.decode_stream(s); return s.result.text
