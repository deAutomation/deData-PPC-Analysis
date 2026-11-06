import re,urllib.request,os,socket
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
SVG=re.compile(r'https://www\.peet\.com\.au/([a-z\-]+)/([a-z0-9\-]+)/wp-content/uploads/[^"\'\s)]+\.svg',re.I)
out={}
for u in [x.strip() for x in open('_peet/community_urls.txt') if x.strip()]:
    slug=u.rstrip('/').split('/')[-1]; p=f'_peet/fs/{slug}.html'
    if not os.path.exists(p) or os.path.getsize(p)<1000:
        try:
            h=urllib.request.urlopen(urllib.request.Request(u.rstrip('/')+'/for-sale/',headers=UA),timeout=15).read().decode('utf-8','replace')
            open(p,'w').write(h)
        except Exception as e:
            print(f'{slug:24} FETCH-ERR {type(e).__name__}',flush=True); out[slug]=[]; continue
    h=open(p,encoding='utf-8',errors='replace').read()
    own=sorted({m.group(0) for m in SVG.finditer(h) if m.group(2)==slug})
    out[slug]=own
    print(f'{slug:24} {len(own)} svg {[x.split("/")[-1][:36] for x in own][:2]}',flush=True)
import json; json.dump(out,open('_peet/fs_svgs.json','w'),indent=1)
print('with svg:',sum(1 for v in out.values() if v),'of',len(out),flush=True)
