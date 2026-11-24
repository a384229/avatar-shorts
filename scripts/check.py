"""出片自查：導演表＋成品影片一起檢查，輸出 check/自查.md 與 check/總覽.jpg（每句一格）給 Claude 看圖確認。
  python check.py videos/片名/director.json [--video final.mp4]
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, W, H, FPS
from direct import lint
from PIL import Image, ImageDraw, ImageFont
from common import font


def probe(p):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', p], capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('director'); ap.add_argument('--video'); a = ap.parse_args()
    D = load(a.director); base = os.path.dirname(os.path.abspath(a.director))
    vid = a.video or os.path.join(base, 'final.mp4')
    if not os.path.exists(vid): vid = os.path.join(base, 'preview.mp4')
    out = []; bad = 0
    def ok(c, msg, fix=''):
        nonlocal bad
        out.append(('✓ ' if c else '✗ ') + msg + ('' if c or not fix else f'　→ {fix}'))
        if not c: bad += 1
    print('── 導演表 ──'); errs, warns = lint(a.director)
    ok(not errs, f'導演表 {len(errs)} 個錯誤', '照上面 ✗ 修')
    for w in warns: out.append('⚠ ' + w)
    if not os.path.exists(vid): print('還沒出片'); return
    j = probe(vid); vs = [s for s in j['streams'] if s['codec_type'] == 'video'][0]; au = [s for s in j['streams'] if s['codec_type'] == 'audio']
    full = vs['width'] == W
    ok(vs['width'] * 16 == vs['height'] * 9, f'直式 9:16（{vs["width"]}×{vs["height"]}）')
    ok(vs['codec_name'] == 'h264' and vs.get('pix_fmt') == 'yuv420p', f'影像 {vs["codec_name"]} {vs.get("pix_fmt")}（各平台都能播）')
    ok(bool(au) and au[0]['codec_name'] == 'aac', '聲音 AAC')
    dur = float(j['format']['duration']); ok(abs(dur - D.get('duration', dur)) < 0.3, f'長度 {dur:.1f} 秒，和導演表一致')
    # 音量
    r = subprocess.run(['ffmpeg', '-i', vid, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', r); P = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', r)
    if I: ok(-16 <= float(I[-1]) <= -12, f'整體音量 {I[-1]} LUFS（目標 -14）', '重新出片會自動標準化；還是不對就檢查配音檔')
    if P: ok(float(P[-1]) <= -0.5, f'最大峰值 {P[-1]} dBFS（不破音）')
    # 黑畫面、無聲
    r = subprocess.run(['ffmpeg', '-i', vid, '-vf', 'blackdetect=d=0.3:pix_th=0.08', '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    ok('black_start' not in r, '沒有黑畫面')
    if D.get('voice'):
        r = subprocess.run(['ffmpeg', '-i', os.path.join(base, D['voice']), '-af', 'silencedetect=noise=-45dB:d=1.2', '-f', 'null', '-'], capture_output=True, text=True).stderr
        gaps = [float(x) for x in re.findall(r'silence_end: [\d.]+ \| silence_duration: ([\d.]+)', r)]
        gaps = gaps[:-1] if gaps else gaps
        ok(not gaps, '句子中間沒有超過 1.2 秒的空白' if not gaps else f'有 {len(gaps)} 段超過 1.2 秒的空白', '縮短該句 pause 或重配音')
        ok(D['lines'][0]['start'] <= 0.5, f'第一句 {D["lines"][0]["start"]:.2f} 秒就開口（0.5 秒內）')
    ok(bool(D.get('hook')) and D['hook'].get('until', 3) >= 1.5, '前 3 秒有開場大字（靜音也看得懂）')
    # 總覽圖：開頭 0.3 秒＋每句中間
    times = [0.3] + [round((l['start'] + l['end']) / 2, 2) for l in D['lines']]
    cw, ch = 270, 480; cols = 6; rows = (len(times) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * cw, rows * (ch + 40)), '#222'); dr = ImageDraw.Draw(sheet); f = ImageFont.truetype(font('bold'), 22)
    os.makedirs(os.path.join(base, 'check'), exist_ok=True)
    for k, t in enumerate(times):
        tmp = os.path.join(base, 'check', '_f.png')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', vid, '-frames:v', '1', '-vf', f'scale={cw}:{ch}', tmp])
        x, y = k % cols * cw, k // cols * (ch + 40)
        if os.path.exists(tmp):
            im = Image.open(tmp); sheet.paste(im, (x, y))
            g = ImageDraw.Draw(sheet, 'RGBA')   # 安全區（上 250、下 450、右 120）
            g.rectangle([x, y, x + cw, y + 250 * ch // H], fill=(255, 0, 0, 40)); g.rectangle([x, y + (H - 450) * ch // H, x + cw, y + ch], fill=(255, 0, 0, 40))
            g.rectangle([x + (W - 120) * cw // W, y, x + cw, y + ch], fill=(255, 0, 0, 30))
        label = '開場' if k == 0 else f'第{k}句 {t:.1f}s'
        dr.text((x + cw / 2, y + ch + 20), label, font=f, fill='white', anchor='mm')
    sp = os.path.join(base, 'check', '總覽.jpg'); sheet.save(sp, quality=85)
    out.append(f'\n總覽圖：{sp}（紅色是平台介面會蓋住的區域，字和道具不要放在裡面）')
    md = f'# 出片自查：{D.get("title", "")}\n\n影片：{vid}\n\n' + '\n'.join('- ' + o if not o.startswith('\n') else o for o in out) + \
         '\n\n## Claude 看總覽圖要確認\n- 表情和台詞情緒對得上嗎？\n- 道具有沒有擋到臉、字幕？\n- 字幕有沒有壓到大頭、有沒有進紅色區？\n- 開場 0.5 秒內有大字＋強畫面嗎？\n'
    open(os.path.join(base, 'check', '自查.md'), 'w', encoding='utf-8').write(md)
    print('\n── 成品 ──'); print('\n'.join(out)); print(f'\n自查結果：{"✓ 全部通過" if not bad else f"✗ {bad} 項沒過"}（報告 check/自查.md）')


if __name__ == '__main__':
    main()
