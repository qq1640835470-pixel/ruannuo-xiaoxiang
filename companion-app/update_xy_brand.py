"""One-time local asset packaging and two-colour UI update; no API calls."""
import json, pathlib, re, shutil
from PIL import Image

ROOT=pathlib.Path(__file__).resolve().parent
WEB=ROOT/'web'
SOURCE=pathlib.Path('C:/Users/16408/.codex/generated_images/01a1392d-c333-7e62-8eee-5c4363c9d0e0/exec-3fe407bd-4250-468c-8c3c-f9cc2d2535c3.png')
ASSETS=ROOT/'assets';ASSETS.mkdir(exist_ok=True)
shutil.copy2(SOURCE,ASSETS/'xy-sakiko-pixel.png')
shutil.copy2(SOURCE,WEB/'xy-icon.png')
im=Image.open(SOURCE).convert('RGBA')
im.save(ASSETS/'xy-sakiko-pixel.ico',format='ICO',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])

css_path=WEB/'styles.css'
css=css_path.read_text(encoding='utf-8')
if not (WEB/'styles-before-xy.css').exists():shutil.copy2(css_path,WEB/'styles-before-xy.css')
PINK='#f6c6d7';WHITE='#ffffff'
def background(m):
    prefix,value=m.groups()
    value=re.sub(r'#[0-9a-fA-F]{3,8}\b',lambda c:WHITE if c.group().lower() in ('#fff','#ffffff') else PINK,value)
    return prefix+value
css=re.sub(r'(background(?:-color)?\s*:\s*)([^;}]+)',background,css)
css=css.replace('--pink:#f4bfd2','--pink:'+PINK).replace('--blush:#ffe6f0','--blush:'+PINK)
css+='''
/* xy: exactly one flat pink and pure white for all authored surface backgrounds. */
:root{background:#ffffff;--pink:#f6c6d7;--blush:#f6c6d7;--cream:#ffffff;--line:#f6c6d7;--pink-dark:#713b51;--muted:#896575;color:#563142}
body,main,.topbar,.page{background:#ffffff}
.sidebar,.settings-drawer,.drawer-backdrop{background:#f6c6d7}
.sidebar{border-right:2px solid #f6c6d7}
.topbar{border-bottom:2px solid #f6c6d7}
.nav-item.selected,.suggestions button,.composer,.task-card,.task-form,.action-card,.connector-card,.subtle-button,.task-form input,.task-form textarea,.settings-section select,.task-controls select{background:#ffffff;box-shadow:none}
.primary-button,.send-button,.primary-button:hover,.send-button:hover,.message.user .message-text,.message-avatar,.filter-tabs button.selected,.task-card.done .task-check,.cost-notice,.status-badge,.status-badge.available,.error-banner,.local-indicator i,.suggestions button:hover{background:#f6c6d7;color:#563142}
.settings-drawer .cost-notice,.settings-drawer .status-badge,.settings-drawer .status-badge.available,.settings-drawer .primary-button,.settings-drawer .primary-button:hover{background:#ffffff;color:#563142}
.drawer-backdrop{opacity:.35;backdrop-filter:none}
.settings-drawer{box-shadow:none;border-left:2px solid #ffffff}
.drawer-header,.settings-section{border-color:#ffffff}
.local-indicator i{border:1px solid #713b51}
.brand-mark{width:38px;height:38px;object-fit:contain;image-rendering:pixelated;flex-shrink:0}
.welcome-flower{color:#b75b7d}
.message-avatar,.welcome-flower,.brand-mark{box-shadow:none}
.primary-button:hover,.send-button:hover{outline:1px solid #713b51;outline-offset:-1px}
button:disabled{cursor:default;opacity:1}
'''
css_path.write_text(css,encoding='utf-8')
html=(WEB/'index.html').read_text(encoding='utf-8')
html=html.replace('<title>一隅 · 学习生活助手</title>','<title>xy</title>').replace('content="#fff7fb"','content="#f6c6d7"')
html=html.replace('aria-label="一隅首页"','aria-label="xy首页"').replace('<span class="brand-mark">❋</span><span>一隅<small>','<img class="brand-mark" src="/xy-icon.png" alt="丰川祥子像素图标"><span>xy<small>')
html=html.replace('<link rel="stylesheet"','<link rel="icon" type="image/png" href="/xy-icon.png">\n  <link rel="stylesheet"')
(WEB/'index.html').write_text(html,encoding='utf-8')
metadata={'app_name':'xy','background_colors':[PINK,WHITE],'character':'丰川祥子','style':'Q版像素风',
          'method':'内置image_gen生成；Pillow仅封装Windows多尺寸ICO，保留透明度',
          'reference':'D:/StudyLifePlan/artifacts/bandori-rolecards/sakiko.png',
          'source':str(SOURCE),'png_size':list(im.size),'ico_sizes':sorted([list(s) for s in Image.open(ASSETS/'xy-sakiko-pixel.ico').ico.sizes()])}
(ASSETS/'icon-manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(metadata,ensure_ascii=False,indent=2))
