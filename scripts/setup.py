"""環境檢查＋建立工作資料夾
  python setup.py [工作資料夾]     檢查 Python／ffmpeg／套件，建立 faces/ voice/ props/ videos/
"""
import os, shutil, subprocess, sys
ok = True
def say(c, m, fix=''):
    global ok
    print(('✓ ' if c else '✗ ') + m + ('' if c else f'\n    → {fix}'))
    ok &= bool(c)
say(sys.version_info >= (3, 9), f'Python {sys.version.split()[0]}', '請安裝 Python 3.9 以上（python.org）')
for mod, pkg in [('PIL', 'pillow'), ('numpy', 'numpy'), ('fontTools', 'fonttools')]:
    try: __import__(mod); say(True, f'套件 {pkg}')
    except ImportError:
        print(f'  安裝 {pkg}…'); r = subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', pkg]); say(r.returncode == 0, f'套件 {pkg}', f'手動執行：{sys.executable} -m pip install {pkg}')
ff = shutil.which('ffmpeg')
say(ff, 'ffmpeg' + (f'（{ff}）' if ff else ''), 'Mac：brew install ffmpeg；Windows：winget install Gyan.FFmpeg（裝完重開終端機）')
wd = sys.argv[1] if len(sys.argv) > 1 else '.'
for d in ['faces', 'voice', 'props', 'videos']: os.makedirs(os.path.join(wd, d), exist_ok=True)
gi = os.path.join(wd, '.gitignore')
if not os.path.exists(gi): open(gi, 'w').write('voice/keys.env\n')
print(f'工作資料夾：{os.path.abspath(wd)}（faces/ 表情庫、voice/ 聲音庫、props/ 自己的道具、videos/ 每支片）')
print('環境 OK，可以開始' if ok else '請先修好上面 ✗ 的項目')
