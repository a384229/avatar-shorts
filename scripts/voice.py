"""旁白：預設「自己錄」（不用 AI 配音）；AI 配音是備案。每句時間自動算好寫回導演表。
  python voice.py sheet  videos/片名/director.json                           產生 錄音稿.txt（含怎麼錄的說明）
  python voice.py align  videos/片名/director.json --audio 我錄的.m4a       【預設】自己錄整篇 → 依停頓切句對時間
  python voice.py redo   videos/片名/director.json --line 6 --audio 第6句.m4a   只重錄某一句
  python voice.py setup  --provider fish --sample voice/sample.wav            建立聲音（存 voice/voice.json）
  python voice.py say    videos/片名/director.json                           逐句配音 → audio/ 與 voice.wav，時間寫回導演表
  python voice.py silent videos/片名/director.json                           不配音，只估時間（先看畫面用）
供應商：fish（Fish Audio）、minimax（MiniMax 海螺）、elevenlabs、gptsovits（本機 GPT-SoVITS）、edge（免費微軟語音，不是你的聲音，只適合試做）
金鑰：環境變數 FISH_API_KEY／MINIMAX_API_KEY／ELEVENLABS_API_KEY，或寫在工作資料夾 voice/keys.env（一行一個 KEY=值）。金鑰不要貼到對話裡。
只用標準函式庫＋ffmpeg（edge 需要 pip install edge-tts）。"""
import argparse, hashlib, json, os, subprocess, sys, time, uuid, urllib.request, urllib.error, wave, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, run, ffprobe_dur

SR = 48000
LEAD, TAIL, GAP = 0.25, 0.7, 0.12


# ---------- 金鑰與 HTTP ----------
def key(name, workdir='.'):
    v = os.environ.get(name)
    if v: return v.strip()
    for p in [os.path.join(workdir, 'voice', 'keys.env'), os.path.join(workdir, 'keys.env'), os.path.join(workdir, '.env')]:
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                if line.strip().startswith(name + '='): return line.split('=', 1)[1].strip().strip('"\'')
    raise SystemExit(f'找不到金鑰 {name}。請在工作資料夾建立 voice/keys.env，寫一行 {name}=你的金鑰（不要貼到對話裡）。')


def http(url, data=None, headers=None, files=None, fields=None, timeout=180):
    headers = dict(headers or {})
    if files or fields:
        b = uuid.uuid4().hex; body = b''
        for k, v in (fields or {}).items():
            body += f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, path in (files or {}).items():
            body += (f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{os.path.basename(path)}"\r\n'
                     f'Content-Type: application/octet-stream\r\n\r\n').encode() + open(path, 'rb').read() + b'\r\n'
        body += f'--{b}--\r\n'.encode(); headers['Content-Type'] = f'multipart/form-data; boundary={b}'
    elif data is not None:
        body = json.dumps(data).encode(); headers['Content-Type'] = 'application/json'
    else:
        body = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body, headers), timeout=timeout) as r:
                return r.read(), r.headers.get('Content-Type', '')
        except urllib.error.HTTPError as e:
            msg = e.read()[:600].decode('utf-8', 'replace')
            if e.code in (429, 500, 502, 503) and attempt < 2: time.sleep(3 * (attempt + 1)); continue
            hint = {401: '金鑰錯誤或過期', 402: '餘額不足／方案不支援', 403: '沒有權限（方案不含聲音複製？）', 429: '太頻繁，稍後再試'}.get(e.code, '')
            raise SystemExit(f'配音服務回應錯誤 {e.code} {hint}\n{msg}')
        except urllib.error.URLError as e:
            if attempt < 2: time.sleep(3); continue
            raise SystemExit(f'連不上配音服務：{e.reason}')


# ---------- 各家供應商 ----------
def to_wav(src, dst, trim=True):
    af = ['-af', 'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,'
                 'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse'] if trim else []
    run(['ffmpeg', '-y', '-v', 'error', '-i', src] + af + ['-ac', '1', '-ar', str(SR), dst])


def setup(a):
    wd = a.workdir; vdir = os.path.join(wd, 'voice'); os.makedirs(vdir, exist_ok=True)
    cfg = {'provider': a.provider, 'speed': a.speed, 'created': time.strftime('%Y-%m-%d')}
    if a.voice_id:   # 不克隆：直接用服務內建／公開的現成聲音
        cfg.update(voice_id=a.voice_id, model=a.model or {'minimax': 'speech-2.8-hd', 'elevenlabs': 'eleven_multilingual_v2'}.get(a.provider, ''))
        if a.provider == 'minimax': cfg['base'] = a.base or 'https://api.minimax.io'
        if a.provider == 'edge': cfg['voice_id'] = a.voice_id
        save(os.path.join(vdir, 'voice.json'), cfg); print(f'✓ 使用現成聲音 {a.voice_id}（{a.provider}，沒有克隆）→ voice/voice.json')
        if a.test: out = os.path.join(vdir, 'test.wav'); synth(cfg, a.test, out, wd); print('試聽：' + out)
        return
    if a.provider != 'edge':
        if not a.sample or not os.path.exists(a.sample): raise SystemExit('請用 --sample 指定錄音檔（10～30 秒、安靜環境、正常說話速度）')
        d = ffprobe_dur(a.sample)
        print(f'錄音長度 {d:.1f} 秒')
        if d < 9.5: print('⚠ 少於 10 秒，有些服務會拒絕；建議 15～30 秒效果更像')
        clean = os.path.join(vdir, 'sample_clean.wav')
        run(['ffmpeg', '-y', '-v', 'error', '-i', a.sample, '-af', 'highpass=f=70,loudnorm=I=-18:TP=-2', '-ac', '1', '-ar', '44100', clean])
    if a.provider == 'fish':
        r, _ = http('https://api.fish.audio/model', headers={'Authorization': 'Bearer ' + key('FISH_API_KEY', wd)},
                    fields={'type': 'tts', 'title': a.name, 'train_mode': 'fast', 'visibility': 'private'}, files={'voices': clean})
        j = json.loads(r); cfg.update(voice_id=j['_id'], model=a.model or '')
    elif a.provider == 'minimax':
        base = a.base or 'https://api.minimax.io'
        hk = {'Authorization': 'Bearer ' + key('MINIMAX_API_KEY', wd)}
        r, _ = http(base + '/v1/files/upload', headers=hk, fields={'purpose': 'voice_clone'}, files={'file': clean})
        fid = json.loads(r)['file']['file_id']
        vid = 'me' + time.strftime('%Y%m%d%H%M%S')
        r, _ = http(base + '/v1/voice_clone', headers=hk, data={'file_id': fid, 'voice_id': vid, 'language_boost': 'Chinese',
                                                                   'need_noise_reduction': True, 'need_volume_normalization': True})
        j = json.loads(r)
        if j.get('base_resp', {}).get('status_code', 0) != 0: raise SystemExit('MiniMax 複製失敗：' + json.dumps(j.get('base_resp'), ensure_ascii=False))
        cfg.update(voice_id=vid, base=base, model=a.model or 'speech-2.8-hd')
        print('提醒：MiniMax 複製的聲音 7 天內沒用到會被刪除，要定期用一下或重建。')
    elif a.provider == 'elevenlabs':
        r, _ = http('https://api.elevenlabs.io/v1/voices/add', headers={'xi-api-key': key('ELEVENLABS_API_KEY', wd)},
                    fields={'name': a.name}, files={'files': clean})
        cfg.update(voice_id=json.loads(r)['voice_id'], model=a.model or 'eleven_multilingual_v2')
    elif a.provider == 'gptsovits':
        if not a.ref_text: raise SystemExit('GPT-SoVITS 要 --ref-text（錄音裡講的那句話，一字不差）。參考音檔要 3～10 秒。')
        ref = os.path.join(vdir, 'ref_3to10s.wav')
        run(['ffmpeg', '-y', '-v', 'error', '-i', clean, '-t', '9.5', ref])
        cfg.update(ref_audio=os.path.abspath(ref), ref_text=a.ref_text, url=a.base or 'http://127.0.0.1:9880')
    elif a.provider == 'edge':
        cfg.update(voice_id=a.edge_voice)
    save(os.path.join(vdir, 'voice.json'), cfg)
    print('✓ 聲音建立完成 → voice/voice.json（' + a.provider + '）')
    if a.test:
        out = os.path.join(vdir, 'test.wav'); synth(cfg, a.test, out, wd); print('試聽：' + out)


def synth(cfg, text, out, wd='.'):
    p = cfg['provider']; tmp = out + '.dl'
    if p == 'fish':
        h = {'Authorization': 'Bearer ' + key('FISH_API_KEY', wd)}
        if cfg.get('model'): h['model'] = cfg['model']
        body = {'text': text, 'reference_id': cfg['voice_id'], 'format': 'wav', 'prosody': {'speed': cfg.get('speed', 1.0)}}
        r, _ = http('https://api.fish.audio/v1/tts', body, h); open(tmp, 'wb').write(r)
    elif p == 'minimax':
        h = {'Authorization': 'Bearer ' + key('MINIMAX_API_KEY', wd)}
        body = {'model': cfg.get('model', 'speech-2.8-hd'), 'text': text, 'stream': False, 'language_boost': 'Chinese', 'output_format': 'hex',
                'voice_setting': {'voice_id': cfg['voice_id'], 'speed': cfg.get('speed', 1.0), 'vol': 1, 'pitch': 0},
                'audio_setting': {'sample_rate': 32000, 'format': 'mp3', 'channel': 1}}
        r, _ = http(cfg.get('base', 'https://api.minimax.io') + '/v1/t2a_v2', body, h); j = json.loads(r)
        if j.get('base_resp', {}).get('status_code', 0) != 0: raise SystemExit('MiniMax 配音失敗：' + json.dumps(j.get('base_resp'), ensure_ascii=False))
        open(tmp, 'wb').write(bytes.fromhex(j['data']['audio']))
    elif p == 'elevenlabs':
        h = {'xi-api-key': key('ELEVENLABS_API_KEY', wd)}
        body = {'text': text, 'model_id': cfg.get('model', 'eleven_multilingual_v2'), 'voice_settings': {'stability': 0.5, 'similarity_boost': 0.8, 'speed': cfg.get('speed', 1.0)}}
        r, _ = http(f'https://api.elevenlabs.io/v1/text-to-speech/{cfg["voice_id"]}?output_format=mp3_44100_128', body, h); open(tmp, 'wb').write(r)
    elif p == 'gptsovits':
        body = {'text': text, 'text_lang': 'zh', 'ref_audio_path': cfg['ref_audio'], 'prompt_text': cfg['ref_text'], 'prompt_lang': 'zh',
                'media_type': 'wav', 'speed_factor': cfg.get('speed', 1.0)}
        r, _ = http(cfg.get('url', 'http://127.0.0.1:9880') + '/tts', body, timeout=600); open(tmp, 'wb').write(r)
    elif p == 'edge':
        rate = f'{int(round((cfg.get("speed", 1.0) - 1) * 100)):+d}%'
        try:
            subprocess.run([sys.executable, '-m', 'edge_tts', '--voice', cfg.get('voice_id', 'zh-TW-HsiaoChenNeural'), f'--rate={rate}',
                            '--text', text, '--write-media', tmp], check=True, capture_output=True)
        except FileNotFoundError:
            raise SystemExit('請先 pip install edge-tts')
        except subprocess.CalledProcessError as e:
            raise SystemExit('edge-tts 失敗（可能沒網路或沒安裝）：' + e.stderr.decode()[-400:])
    else:
        raise SystemExit('不認得的供應商 ' + p)
    to_wav(tmp, out); os.remove(tmp)


# ---------- 組合整段配音 ----------
def read_pcm(p):
    r = subprocess.run(['ffmpeg', '-v', 'error', '-i', p, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True)
    return r.stdout


def assemble(D, path, segs):
    """segs: [(line, pcm_bytes)]，依序串起來，算每句 start/end，寫 voice.wav"""
    base = os.path.dirname(path); out = bytearray(); t = LEAD
    out += b'\0\0' * int(LEAD * SR)
    for ln, pcm in segs:
        ln['start'] = round(t, 3); dur = len(pcm) / 2 / SR; t += dur; ln['end'] = round(t, 3)
        out += pcm
        gap = ln.get('pause', GAP); out += b'\0\0' * int(gap * SR); t += gap
    out += b'\0\0' * int(TAIL * SR); t += TAIL
    w = wave.open(os.path.join(base, 'voice.wav'), 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(bytes(out)); w.close()
    D['voice'] = 'voice.wav'; D['duration'] = round(t, 3)
    save(path, D)
    print(f'✓ 旁白完成：{len(segs)} 句、總長 {t:.1f} 秒 → voice.wav（每句時間已寫回導演表）')


def say(a):
    D = load(a.director); base = os.path.dirname(os.path.abspath(a.director)); wd = a.workdir
    vj = a.voice or os.path.join(wd, 'voice', 'voice.json')
    cfg = {'provider': 'edge', 'voice_id': 'zh-TW-HsiaoChenNeural', 'speed': 1.0} if a.provider == 'edge' else load(vj)
    if a.speed: cfg['speed'] = a.speed
    adir = os.path.join(base, 'audio'); os.makedirs(adir, exist_ok=True)
    segs = []
    for i, ln in enumerate(D['lines'], 1):
        spoken = ln.get('say') or ln['text']   # say：念法跟字幕不同時用（例：數字、英文、破音字）
        h = hashlib.md5(json.dumps([spoken, cfg.get('provider'), cfg.get('voice_id'), cfg.get('speed')], ensure_ascii=False).encode()).hexdigest()[:10]
        f = os.path.join(adir, f'line_{i:02d}_{h}.wav')
        if not os.path.exists(f):
            print(f'  配音 {i:02d}：{spoken}'); synth(cfg, spoken, f, wd)
        else:
            print(f'  沿用 {i:02d}（文字沒改）')
        ln['audio'] = os.path.relpath(f, base)
        segs.append((ln, read_pcm(f)))
    D['voice_provider'] = cfg['provider']
    assemble(D, a.director, segs)


def align(a):
    """自己錄整段：用停頓切段，段數和句數對齊（多的停頓會被合併）"""
    D = load(a.director); base = os.path.dirname(os.path.abspath(a.director))
    src = os.path.join(base, 'my_voice.wav'); run(['ffmpeg', '-y', '-v', 'error', '-i', a.audio, '-ac', '1', '-ar', str(SR), src])
    total = ffprobe_dur(src); n = len(D['lines'])
    def detect(mp):
        r = subprocess.run(['ffmpeg', '-i', src, '-af', f'silencedetect=noise=-38dB:d={mp}', '-f', 'null', '-'], capture_output=True, text=True).stderr
        sil = []; s0 = None
        for line in r.splitlines():
            if 'silence_start' in line: s0 = float(line.split('silence_start:')[1])
            if 'silence_end' in line and s0 is not None: sil.append((s0, float(line.split('silence_end:')[1].split('|')[0]))); s0 = None
        sp = []; t = 0
        for s, e in sil:
            if s - t > 0.15: sp.append([t, s])
            t = e
        if total - t > 0.15: sp.append([t, total])
        return sp
    speech = None
    if not a.no_asr:   # 優先用語音辨識對句子（句子黏在一起、念錯重念都對得上）
        try:
            import asr_align
            print('  用語音辨識對句子…')
            speech = asr_align.align_lines(src, [l['text'] for l in D['lines']])
        except Exception as e:
            print(f'  ⚠ 語音辨識對句失敗（{e}），改用停頓切句')
    if speech is None:
      for mp in [a.min_pause, 0.25, 0.18, 0.1]:   # 停頓太短就放寬，直到段數夠
        speech = detect(mp)
        if len(speech) >= n: break
    while len(speech) > n:   # 合併最短的停頓
        gaps = [speech[i + 1][0] - speech[i][1] for i in range(len(speech) - 1)]; i = gaps.index(min(gaps))
        speech[i][1] = speech[i + 1][1]; del speech[i + 1]
    if len(speech) < n:
        print(f'⚠ 只找到 {len(speech)} 段話、腳本有 {n} 句：改用字數比例分配（建議每句之間停半秒再錄）')
        s, e = speech[0][0], speech[-1][1]; chars = [len(l.get('say') or l['text']) for l in D['lines']]; tot = sum(chars); t = s; speech = []
        for c in chars: d = (e - s) * c / tot; speech.append([t, t + d]); t += d
    pcm = read_pcm(src); segs = []; adir = os.path.join(base, 'audio'); os.makedirs(adir, exist_ok=True)
    dc, rec = cleaner(a)
    for i, (ln, (s, e)) in enumerate(zip(D['lines'], speech), 1):
        lo = speech[i - 2][1] if i > 1 else 0; hi = speech[i][0] if i < n else total   # 前後留白不能吃到隔壁句
        seg = fade(pcm[int(max(lo, s - .05) * SR) * 2:int(min(hi, e + .05) * SR) * 2])
        write_wav(os.path.join(adir, f'line_{i:02d}_raw.wav'), seg)
        if dc:
            nx = D['lines'][i] if i < len(D['lines']) else {}
            seg, note = dc.clean_pcm(seg, SR, ln.get('say') or ln['text'], rec, nx.get('say') or nx.get('text', ''))
            if note: print(f'  第{i}句 去卡頓：' + '、'.join(note))
        f = os.path.join(adir, f'line_{i:02d}_rec.wav'); write_wav(f, seg); ln['audio'] = os.path.relpath(f, base)
        segs.append((ln, seg))
    D['voice_provider'] = 'recorded'
    if not a.no_asr: spoken_check(D, base)
    print('每句切好的錄音在 audio/，某句要重錄：voice.py redo … --line 句號 --audio 新錄音')
    assemble(D, a.director, segs)


def cleaner(a):
    """去卡頓（declutter.py）；--raw 就不處理"""
    if getattr(a, 'raw', False): return None, None
    try:
        import declutter
    except Exception as e:
        print(f'  ⚠ 去卡頓沒辦法用（{e}），保留原始錄音'); return None, None
    rec = None if getattr(a, 'no_asr', False) else declutter.recognizer_or_none()
    return declutter, rec


def fade(pcm, ms=12):
    """每段頭尾 12ms 淡入淡出，接起來不會有喀聲"""
    import numpy as np
    x = np.frombuffer(pcm, np.int16).astype(np.float32); f = int(SR * ms / 1000)
    if len(x) > 2 * f: r = np.linspace(0, 1, f); x[:f] *= r; x[-f:] *= r[::-1]
    return x.astype(np.int16).tobytes()


def spoken_check(D, base, only=None):
    """每句錄音再辨識一次，跟字幕比；不一樣的寫進 check/念稿比對.txt，字幕要照實際念的改"""
    try:
        import asr_align
        idx = [i for i in range(len(D['lines'])) if only is None or i + 1 == only]
        res = asr_align.compare([D['lines'][i]['text'] for i in idx], [os.path.join(base, D['lines'][i]['audio']) for i in idx])
    except Exception as e:
        print(f'  ⚠ 念稿比對沒辦法做（{e}）'); return
    rows = []
    for (k, t, heard, diff), i in zip(res, idx):
        if diff: rows.append(f'第{i + 1}句\n  字幕：{t}\n  辨識：{heard}\n  差在：' + '；'.join(f'{"少念" if op == "delete" else "多念" if op == "insert" else "改念"}［{a or "-"}→{b or "-"}］' for op, a, b in diff))
    os.makedirs(os.path.join(base, 'check'), exist_ok=True)
    with open(os.path.join(base, 'check', '念稿比對.txt'), 'w') as fo:
        fo.write('實際念的跟字幕不一樣的句子（辨識會把字認成近音字或簡體，照意思判斷；確定是念的不一樣就照念的改字幕 text）\n\n' + ('\n'.join(rows) or '全部一致'))
    print(f'  念稿比對：{len(rows)} 句跟字幕不一樣' + ('，看 check/念稿比對.txt，照實際念的改字幕' if rows else '') )


def write_wav(path, pcm):
    w = wave.open(path, 'w'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm); w.close()


def redo(a):
    """只重錄某一句：換掉那句的聲音，其他句不動，重新算時間"""
    D = load(a.director); base = os.path.dirname(os.path.abspath(a.director)); n = a.line
    if not 1 <= n <= len(D['lines']): raise SystemExit(f'沒有第 {n} 句（共 {len(D["lines"])} 句）')
    for i, ln in enumerate(D['lines'], 1):
        if i != n and not (ln.get('audio') and os.path.exists(os.path.join(base, ln['audio']))):
            raise SystemExit(f'第 {i} 句沒有單句錄音檔，請整篇重跑 align 或 say')
    f = os.path.join(base, 'audio', f'line_{n:02d}_rec.wav'); to_wav(a.audio, f)
    dc, rec = cleaner(a)
    if dc:
        ln = D['lines'][n - 1]; seg, note = dc.clean_pcm(read_pcm(f), SR, ln.get('say') or ln['text'], rec); write_wav(f, seg)
        if note: print(f'  第{n}句 去卡頓：' + '、'.join(note))
    D['lines'][n - 1]['audio'] = os.path.relpath(f, base)
    if not getattr(a, 'no_asr', False): spoken_check(D, base, only=n)
    segs = [(ln, read_pcm(os.path.join(base, ln['audio']))) for ln in D['lines']]
    assemble(D, a.director, segs)


def silent(a):
    D = load(a.director); t = LEAD
    for ln in D['lines']:
        d = max(1.0, len(ln.get('say') or ln['text']) / 4.6); ln['start'] = round(t, 3); ln['end'] = round(t + d, 3); t += d + ln.get('pause', GAP)
    D['voice'] = None; D['duration'] = round(t + TAIL, 3); D['voice_provider'] = 'silent'
    save(a.director, D); print(f'✓ 已用每秒 4.6 字估時間，總長 {D["duration"]:.1f} 秒（沒有聲音，只看畫面用）')


def sheet(a):
    """錄音稿：一行一句（自己念用 text，不用 say），加上怎麼錄的說明"""
    D = load(a.director); n = len(D['lines']); sec = sum(len(l['text']) for l in D['lines']) / 4.6
    out = [f'錄音稿：{D.get("title", "")}（{n} 句，約 {sec:.0f} 秒）', '',
           '怎麼錄：手機錄音 App，嘴巴離手機一個拳頭，用平常跟朋友聊天的口氣。',
           '每句念完停 1 秒；念錯了停 2 秒，從那一句重新念就好，不用整篇重來。', '']
    out += [f'{i}. {l["text"]}' for i, l in enumerate(D['lines'], 1)]
    p = os.path.join(os.path.dirname(os.path.abspath(a.director)), '錄音稿.txt')
    open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n'); print('\n'.join(out)); print(f'\n✓ 錄音稿 → {p}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--workdir', default='.', help='工作資料夾（有 voice/ 的那層）')
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('setup'); p.add_argument('--provider', required=True, choices=['fish', 'minimax', 'elevenlabs', 'gptsovits', 'edge'])
    p.add_argument('--sample'); p.add_argument('--name', default='my-voice'); p.add_argument('--model'); p.add_argument('--base')
    p.add_argument('--ref-text'); p.add_argument('--speed', type=float, default=1.0); p.add_argument('--edge-voice', default='zh-TW-HsiaoChenNeural')
    p.add_argument('--voice-id', help='不克隆，直接用現成聲音的 ID（Fish 聲音庫的模型 ID、MiniMax 內建音色、ElevenLabs 聲音、edge 語音名稱）')
    p.add_argument('--test', help='建立後念這句試聽'); p.set_defaults(f=setup)
    p = sp.add_parser('say'); p.add_argument('director'); p.add_argument('--voice'); p.add_argument('--provider', help='edge＝不用自己的聲音、免費試做')
    p.add_argument('--speed', type=float); p.set_defaults(f=say)
    p = sp.add_parser('align'); p.add_argument('director'); p.add_argument('--audio', required=True); p.add_argument('--min-pause', type=float, default=0.35)
    p.add_argument('--no-asr', action='store_true', help='不用語音辨識，只看停頓切句')
    p.add_argument('--raw', action='store_true', help='不去卡頓，保留原始錄音（長停頓、重念都留著）'); p.set_defaults(f=align)
    p = sp.add_parser('redo'); p.add_argument('director'); p.add_argument('--line', type=int, required=True); p.add_argument('--audio', required=True)
    p.add_argument('--raw', action='store_true'); p.add_argument('--no-asr', action='store_true'); p.set_defaults(f=redo)
    p = sp.add_parser('sheet'); p.add_argument('director'); p.set_defaults(f=sheet)
    p = sp.add_parser('silent'); p.add_argument('director'); p.set_defaults(f=silent)
    a = ap.parse_args(); a.f(a)
