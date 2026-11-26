"""錄音去卡頓：每一句自己錄的聲音，自動拿掉
  1. 太長的停頓（句子中間卡住超過 0.25 秒 → 縮成 0.15 秒）
  2. 念錯重念、結巴（例：「手機…手機架好了」只留後面完整那次）
  3. 單獨的「嗯、呃、啊、欸」
voice.py align／redo 會自動呼叫；不想處理時加 --raw。全部在本機跑。
有語音辨識（asr_align 能用）就用辨識比對重複；沒有就只看停頓：停超過 0.8 秒又重講一次，視為重念，留後面那次。"""
import numpy as np

FILLER = {'en', 'e', 'a', 'ei', 'o', 'ng', 'm', 'eng', 'ai'}
MAX_GAP, KEEP_GAP, PAD, FADE = 0.25, 0.15, 0.04, 0.008


def chunks_of(x, sr, gap=0.15):
    """依停頓切成小段 [(開始秒, 結束秒)]"""
    hop = int(sr * 0.02); n = len(x) // hop
    if n == 0: return []
    rms = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    thr = max(-42, np.percentile(rms, 95) - 30); on = rms > thr
    segs, s, quiet = [], None, 0
    for i, v in enumerate(on):
        if v:
            if s is None: s = i
            quiet = 0
        elif s is not None:
            quiet += 1
            if quiet * 0.02 >= gap: segs.append([s * 0.02, (i - quiet + 1) * 0.02]); s = None; quiet = 0
    if s is not None: segs.append([s * 0.02, n * 0.02])
    out = []
    for a, b in segs:
        if out and (b - a < 0.12): out[-1][1] = b          # 太短的雜音併到前一段
        else: out.append([a, b])
    return out


def _pinyin(rec, x, sr):
    import asr_align
    if len(x) < sr * 0.25: return []          # 太短辨識器會出錯，當作聽不出來
    y = x if sr == asr_align.SR else np.interp(np.arange(0, len(x), sr / asr_align.SR), np.arange(len(x)), x).astype(np.float32)
    s = rec.create_stream(); s.accept_waveform(asr_align.SR, y); rec.decode_stream(s)
    return asr_align.norm(s.result.text)


def plan(x, sr, text, rec=None, nxt=''):
    """回傳要留下的段落 [(開始, 結束)] 和處理說明"""
    ch = chunks_of(x, sr); note = []
    if len(ch) <= 1: return ch, note
    keep = [True] * len(ch)
    if rec is not None:
        import asr_align
        ref = asr_align.norm(text); py = [_pinyin(rec, x[int(a * sr):int(b * sr)], sr) for a, b in ch]
        for k, p in enumerate(py):   # 單獨的語助詞
            if p and all(q in FILLER for q in p) and not any(q in FILLER for q in ref): keep[k] = False; note.append('語助詞')
        def cover(ks):   # 這幾段合起來對到腳本幾個字（同音或相似音都算）
            h = [q for k in ks for q in py[k]]
            if not h or not ref: return 0
            D = np.zeros((len(ref) + 1, len(h) + 1), int)
            for i in range(1, len(ref) + 1):
                for j in range(1, len(h) + 1):
                    D[i, j] = max(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1] + (asr_align._cost(ref[i - 1], h[j - 1]) <= 1))
            return D[-1, -1]
        live = [k for k in range(len(ch)) if keep[k]]; full = cover(live)
        if ref and full >= 0.55 * len(ref):   # 辨識夠準才做：拿掉某段後腳本還是一樣完整 → 那段是念錯重念／結巴
            for k in list(live):
                if len(live) < 2 or ch[k][1] - ch[k][0] > 1.6 or not py[k]: continue
                rest = [q for q in live if q != k]
                if cover(rest) >= full and cover([k]) >= 1:
                    keep[k] = False; live = rest; note.append('重念')
            # 句尾多出一小段，其實是下一句先開口又停下來（結巴）→ 拿掉
            nref = asr_align.norm(nxt)[:4] if nxt else []
            k = live[-1] if live else None
            if nref and k is not None and len(live) >= 2 and ch[k][1] - ch[k][0] <= 1.2 and py[k] \
                    and cover([q for q in live if q != k]) >= full and any(asr_align._cost(a, b) == 0 for a in py[k] for b in nref):
                keep[k] = False; live = live[:-1]; note.append('重念')
    else:
        for k in range(1, len(ch)):  # 沒辨識：停很久又重講 → 留後面那次
            if ch[k][0] - ch[k - 1][1] >= 0.8 and (ch[-1][1] - ch[k][0]) >= 0.55 * (ch[-1][1] - ch[0][0]):
                for q in range(k): keep[q] = False
                note.append('重念')
    kept = [c for c, v in zip(ch, keep) if v]
    if not kept or sum(b - a for a, b in kept) < 0.45 * sum(b - a for a, b in ch):   # 刪太多就不刪，只縮停頓
        kept = ch; note = []
    gaps = sum(1 for i in range(1, len(kept)) if kept[i][0] - kept[i - 1][1] > MAX_GAP)
    if gaps: note.append(f'縮短 {gaps} 個停頓')
    return kept, note


def clean_pcm(pcm, sr, text, rec=None, nxt=''):
    """pcm：16-bit 單聲道 bytes → (新的 bytes, 說明清單)"""
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
    if len(x) < sr * 0.3: return pcm, []
    kept, note = plan(x, sr, text, rec, nxt)
    if not kept: return pcm, []
    out = []; f = int(FADE * sr); ramp = np.linspace(0, 1, f, dtype=np.float32) if f else None
    for i, (a, b) in enumerate(kept):
        s = x[max(0, int((a - PAD) * sr)):min(len(x), int((b + PAD) * sr))].copy()
        if f and len(s) > 2 * f: s[:f] *= ramp; s[-f:] *= ramp[::-1]
        if i:
            g = min(kept[i][0] - kept[i - 1][1], KEEP_GAP) if kept[i][0] - kept[i - 1][1] > MAX_GAP else max(0, kept[i][0] - kept[i - 1][1] - 2 * PAD)
            out.append(np.zeros(int(g * sr), np.float32))
        out.append(s)
    y = np.concatenate(out)
    return (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes(), sorted(set(note), key=note.index)


def recognizer_or_none():
    try:
        import asr_align
        return asr_align.recognizer()
    except Exception:
        return None
