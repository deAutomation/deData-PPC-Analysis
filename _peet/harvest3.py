import re,os,json,io,urllib.request
from PIL import Image
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
def fetch(u): return urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=35).read().decode('utf-8','replace')
IMG=re.compile(r'https://www\.peet\.com\.au/([a-z\-]+)/([a-z0-9\-]+)/wp-content/uploads/[^"\'\s)]+?\.(?:png|jpg|jpeg|webp)',re.I)
rows=[]
for line in [x.strip() for x in open('_peet/community_urls.txt') if x.strip()]:
    slug=line.rstrip('/').split('/')[-1]
    pages=[f'_peet/pages/{slug}.html']
    found=None
    for pg in pages+[None]:
        if pg is None:
            try: h=fetch(line.rstrip('/')+'/about/')
            except Exception: break
        else:
            if not os.path.exists(pg): continue
            h=open(pg,encoding='utf-8',errors='replace').read()
        # only this estate's own upload path
        cands=[m.group(0) for m in IMG.finditer(h) if m.group(2)==slug]
        mp=[c for c in cands if re.search(r'master.?plan',c,re.I) and not re.search(r'logo|icon|favicon|emblem',c,re.I)]
        if mp: found=mp[0]; break
    if not found:
        rows.append([slug,'no-masterplan','',0,0]); print(f'{slug:24} -',flush=True); continue
    try:
        raw=urllib.request.urlopen(urllib.request.Request(found,headers=UA),timeout=45).read()
        im=Image.open(io.BytesIO(raw)); w,hh=im.size
        im.convert('RGB').save(f'_peet/masterplans/{slug}.png','PNG')
        n=im.copy(); n.thumbnail((2200,2200)); n.convert('RGB').save(f'_peet/masterplans/normalised/{slug}.png','PNG')
        rows.append([slug,'masterplan',found,w,hh]); print(f'{slug:24} OK {w}x{hh}',flush=True)
    except Exception as e:
        rows.append([slug,'err '+str(e)[:30],found,0,0]); print(f'{slug:24} ERR {str(e)[:40]}',flush=True)
json.dump(rows,open('_peet/masterplan_manifest.json','w'),indent=1)
print('with masterplan:',sum(1 for r in rows if r[1]=='masterplan'),'of',len(rows))
