"""表情庫工具
  python faces.py demo  faces/                 複製內建示範角色（先試流程用）
  python faces.py split 總表.png faces/ [--grid 4x4]   把 GPT 生的 4×4 表情總表切成 16 張、去背、統一大小
  python faces.py cutout faces/                把單張表情圖去背（純色或白色背景），結果放 faces/cut/
  python faces.py check faces/                 檢查缺哪些表情，並輸出 faces/_總覽.jpg
"""
import argparse, os, sys, shutil, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import FACES, GRID16, REQUIRED, ASSETS, find_face, resolve_face, font

SIDE = 1000


def has_alpha(im):
    if im.mode != 'RGBA': return False
    a = np.asarray(im.getchannel('A'))
    return (a < 20).mean() > 0.05


def chroma(a, bg):
    """綠幕／藍幕去背：看「綠（藍）比其他顏色多多少」算透明度，邊緣去溢色"""
    a = a.astype(np.float32); k = 1 if bg[1] >= bg[2] else 2; o = [c for c in (0, 1, 2) if c != k]
    dom = a[..., k] - np.maximum(a[..., o[0]], a[..., o[1]])
    alpha = np.clip(1 - (dom - 25) / 70, 0, 1)                    # 綠多 70 以上＝全透明，25 以下＝全不透明
    a[..., k] = np.minimum(a[..., k], np.maximum(a[..., o[0]], a[..., o[1]]) + 8)   # 去掉頭髮邊緣的綠光
    out = np.dstack([a, alpha * 255]).astype(np.uint8)
    im = Image.fromarray(out, 'RGBA').copy()
    al = im.getchannel('A').filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    im.putalpha(al); return im


def cutout(im, tol=38):
    """去背：綠幕／藍幕用色鍵；白色或純色背景從四周邊緣把同色、連在一起的區域變透明（臉裡面的白色不會被挖掉）"""
    im = im.convert('RGBA')
    if has_alpha(im): return im
    a = np.asarray(im).astype(np.int16)[..., :3]
    h, w = a.shape[:2]
    border = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = np.median(border, 0)
    if max(bg[1], bg[2]) - max(bg[0], min(bg[1], bg[2])) > 80: return chroma(a, bg)
    dist = np.sqrt(((a - bg) ** 2).sum(-1))
    mask = Image.fromarray(np.where(dist < tol, 255, 0).astype(np.uint8)).copy()  # copy：fromarray 的圖是唯讀，floodfill 會失效
    for x in range(0, w, 8):
        for y in (0, h - 1):
            if mask.getpixel((x, y)) == 255: ImageDraw.floodfill(mask, (x, y), 128)
    for y in range(0, h, 8):
        for x in (0, w - 1):
            if mask.getpixel((x, y)) == 255: ImageDraw.floodfill(mask, (x, y), 128)
    m = np.asarray(mask)
    alpha = Image.fromarray(np.where(m == 128, 0, 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    im.putalpha(alpha)
    return im


def fit_box(ims, pad=0.04):
    """多張圖用同一個裁切框（保持角色大小一致），回傳裁好、放進正方形的圖"""
    boxes = [im.getchannel('A').point(lambda v: 255 if v > 30 else 0).getbbox() for im in ims]
    boxes = [b for b in boxes if b]
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes); x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    side = int(max(x1 - x0, y1 - y0) * (1 + pad * 2)); cx = (x0 + x1) / 2; cy = (y0 + y1) / 2
    out = []
    for im in ims:
        c = Image.new('RGBA', (side, side))
        c.alpha_composite(im, (int(side / 2 - cx), int(side / 2 - cy)))
        out.append(c.resize((SIDE, SIDE), Image.LANCZOS))
    return out


def cmd_split(a):
    src = Image.open(a.sheet).convert('RGBA')
    cols, rows = map(int, a.grid.lower().split('x'))
    order = a.order.split(',') if a.order else GRID16
    cw, ch = src.width / cols, src.height / rows
    cells = []
    for i in range(min(cols * rows, len(order))):
        r, c = divmod(i, cols)
        m = int(min(cw, ch) * a.margin)
        cell = src.crop((int(c * cw) + m, int(r * ch) + m, int((c + 1) * cw) - m, int((r + 1) * ch) - m))
        cells.append(cutout(cell, a.tol))
    cells = fit_box(cells)
    os.makedirs(a.out, exist_ok=True)
    for k, im in zip(order, cells): im.save(os.path.join(a.out, k + '.png'))
    print(f'切好 {len(cells)} 張 → {a.out}')
    sheet(a.out)


def cmd_cutout(a):
    files = [f for f in glob.glob(os.path.join(a.dir, '*')) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) and not os.path.basename(f).startswith('_')]
    ims = [cutout(Image.open(f), a.tol) for f in files]
    ims = fit_box(ims) if a.same_box else [fit_box([im])[0] for im in ims]
    out = os.path.join(a.dir, 'cut'); os.makedirs(out, exist_ok=True)
    for f, im in zip(files, ims): im.save(os.path.join(out, os.path.splitext(os.path.basename(f))[0] + '.png'))
    print(f'去背 {len(ims)} 張 → {out}（之後 render 會優先用 cut/ 裡的）')
    sheet(a.dir)


def sheet(d):
    keys = [k for k, _, _ in FACES] + ['neutral_talk', 'smile_talk']
    zh = {k: z for k, z, _ in FACES}; zh.update({'neutral_talk': '平常(張嘴)', 'smile_talk': '微笑(張嘴)'})
    cols = 5; rows = (len(keys) + cols - 1) // cols; S = 260
    out = Image.new('RGB', (cols * S, rows * (S + 50)), '#f3f0ea'); dr = ImageDraw.Draw(out); f = ImageFont.truetype(font('bold'), 26)
    for i, k in enumerate(keys):
        x, y = i % cols * S, i // cols * (S + 50)
        p = find_face(d, k)
        if p:
            im = Image.open(p).convert('RGBA'); im.thumbnail((S - 20, S - 20)); out.paste(im, (x + 10, y + 10), im)
            dr.text((x + S / 2, y + S + 22), f'{zh[k]} {k}', font=f, fill='#333', anchor='mm')
        else:
            dr.rectangle([x + 10, y + 10, x + S - 10, y + S - 10], outline='#c33', width=3)
            dr.text((x + S / 2, y + S / 2), '缺', font=ImageFont.truetype(font('black'), 80), fill='#c33', anchor='mm')
            dr.text((x + S / 2, y + S + 22), f'{zh[k]} {k}', font=f, fill='#c33', anchor='mm')
    p = os.path.join(d, '_總覽.jpg'); out.save(p, quality=88); print('總覽圖：' + p)
    return p


def cmd_check(a):
    d = a.dir; ok = True
    print('表情庫：' + os.path.abspath(d))
    for k, zh, use in FACES:
        p = find_face(d, k)
        if p:
            im = Image.open(p); t = '透明背景' if has_alpha(im.convert('RGBA')) else '⚠ 不是透明背景（跑 cutout）'
            print(f'  ✓ {zh:3} {k:10} {im.width}×{im.height} {t}')
        else:
            sub, _ = resolve_face(d, k)
            flag = '✗ 必備' if k in REQUIRED else '－'
            if k in REQUIRED: ok = False
            print(f'  {flag} {zh:3} {k:10} 缺，' + (f'會先用 {sub} 代替' if sub else '沒有可代替的'))
    for k in ['neutral_talk', 'smile_talk']:
        print(f'  {"✓" if find_face(d, k) else "－"} {k}（張嘴版，有的話講話會對嘴）')
    sheet(d)
    print('結果：' + ('可以出片' if ok else '缺必備表情（平常、微笑、驚訝、思考），請補上'))
    sys.exit(0 if ok else 1)


def cmd_demo(a):
    os.makedirs(a.dir, exist_ok=True)
    for f in glob.glob(os.path.join(ASSETS, 'demo_faces', '*.png')): shutil.copy(f, a.dir)
    print('已複製示範角色到 ' + a.dir); sheet(a.dir)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('split'); p.add_argument('sheet'); p.add_argument('out'); p.add_argument('--grid', default='4x4')
    p.add_argument('--order', help='逗號分隔，預設照 GRID16'); p.add_argument('--margin', type=float, default=0.02); p.add_argument('--tol', type=int, default=38)
    p.set_defaults(f=cmd_split)
    p = sp.add_parser('cutout'); p.add_argument('dir'); p.add_argument('--tol', type=int, default=38)
    p.add_argument('--same-box', action='store_true', help='所有圖用同一個裁切框（同一批生成、構圖一樣時用）'); p.set_defaults(f=cmd_cutout)
    p = sp.add_parser('check'); p.add_argument('dir'); p.set_defaults(f=cmd_check)
    p = sp.add_parser('demo'); p.add_argument('dir'); p.set_defaults(f=cmd_demo)
    a = ap.parse_args(); a.f(a)
