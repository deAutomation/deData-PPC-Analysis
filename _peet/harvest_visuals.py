import re,os,json,urllib.request,io
from PIL import Image
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
os.makedirs('_peet/masterplans',exist_ok=True); os.makedirs('_peet/masterplans/normalised',exist_ok=True)
IMG=re.compile(r'https://www\.peet\.com\.au/[^"\'\s)]+?\.(?:png|jpg|jpeg|webp)', re.I)
BAD=re.compile(r'logo|favicon|icon|emblem|sprite|placeholder', re.I)
def pick(imgs, og):
    m=[i for i in imgs if re.search(r'master.?plan|masterplan',i,re.I) and not BAD.search(i)]
    if m: return m[0],'masterplan'
    m=[i for i in imgs if re.search(r'aerial|site.?plan|estate.?map|community.?map|[-_]map',i,re.I) and not BAD.search(i)]
    if m: return m[0],'map-or-aerial'
    return (og[0],'og-hero') if og else (None,'none')
rows=[]
for u in [x.strip() for x in open('_peet/community_urls.txt') if x.strip()]:
    slug=u.rstrip('/').split('/')[-1]
    p=f'_peet/pages/{slug}.html'
    if not os.path.exists(p): continue
    h=open(p,encoding='utf-8',errors='replace').read()
    imgs=sorted(set(IMG.findall(h))); og=re.findall(r'property="og:image" content="([^"]+)"',h)
    url,kind=pick(imgs,og)
    if not url: rows.append((slug,'none','','',0,0,0)); continue
    try:
        raw=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60).read()
        im=Image.open(io.BytesIO(raw)); w,hh=im.size
        out=f'_peet/masterplans/{slug}.png'
        im.convert('RGB').save(out,'PNG')
        n=im.copy(); n.thumbnail((2200,2200)); n.convert('RGB').save(f'_peet/masterplans/normalised/{slug}.png','PNG')
        rows.append((slug,kind,url,len(raw),w,hh,round(len(raw)/1024)))
    except Exception as e:
        rows.append((slug,'ERR '+str(e)[:30],url,0,0,0,0))
json.dump(rows,open('_peet/masterplan_manifest.json','w'))
for r in rows: print(f'{r[0]:24} {r[1]:14} {r[2] and str(r[4])+"x"+str(r[5]) or "":10} {(r[6] if len(r)>6 else "")}')
