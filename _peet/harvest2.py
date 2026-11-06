import re,os,json,io,urllib.request
from PIL import Image
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
def fetch(u):
    return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=35).read().decode('utf-8','replace')
def img_near(h, kw, span=2500):
    best=None
    for m in re.finditer(kw, h, re.I):
        seg=h[max(0,m.start()-span):m.start()+span]
        cands=re.findall(r'<img[^>]+src="([^"]+\.(?:png|jpg|jpeg|webp)[^"]*)"',seg,re.I)
        cands=[c for c in cands if not re.search(r'logo|favicon|icon|emblem',c,re.I)]
        if cands: return cands[0]
    return best
def harvest(slug, pages):
    for pg in pages:
        try: h=fetch(pg)
        except Exception: continue
        u=img_near(h, r'>[^<]*master\s?plan[^<]*<')
        if not u: u=img_near(h, r'master\s?plan')
        if u: return u,pg
    return None,None
todo=[]
base='https://www.peet.com.au/communities/'
for u in [x.strip() for x in open('_peet/community_urls.txt') if x.strip()]:
    slug=u.rstrip('/').split('/')[-1]
    if os.path.exists(f'_peet/masterplans/{slug}.png'): continue
    todo.append((slug,u))
print('missing:',len(todo),flush=True)
rows=[]
for slug,u in todo:
    url,pg=harvest(slug,[u.rstrip('/')+'/about/', u])
    if not url: print(f'{slug:24} no masterplan found',flush=True); rows.append([slug,'none','','',0,0]); continue
    try:
        raw=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=45).read()
        im=Image.open(io.BytesIO(raw)); w,hh=im.size
        im.convert('RGB').save(f'_peet/masterplans/{slug}.png','PNG')
        n=im.copy(); n.thumbnail((2200,2200)); n.convert('RGB').save(f'_peet/masterplans/normalised/{slug}.png','PNG')
        rows.append([slug,'content-block',url,w,hh,round(len(raw)/1024)])
        print(f'{slug:24} OK {w}x{hh} {url[-45:]}',flush=True)
    except Exception as e:
        print(f'{slug:24} ERR {str(e)[:50]}',flush=True); rows.append([slug,'err',url,0,0,0])
json.dump(rows,open('_peet/harvest2_rows.json','w'))
