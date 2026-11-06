import re,os,json,subprocess,urllib.request,shutil
UA={'User-Agent':'Mozilla/5.0'}
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fs=json.load(open('_peet/fs_svgs.json'))
os.makedirs('_peet/maps',exist_ok=True)
def fetch(u,p):
    if os.path.exists(p) and os.path.getsize(p)>2000: return True
    try:
        raw=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40).read()
        open(p,'wb').write(raw); return True
    except Exception as e:
        print('  dl fail',e); return False
def dims(svg):
    m=re.search(r'viewBox="([\d\.\s\-]+)"',svg)
    if m:
        v=[float(x) for x in m.group(1).split()]
        return v[2],v[3]
    w=re.search(r'width="([\d\.]+)',svg); h=re.search(r'height="([\d\.]+)',svg)
    return (float(w.group(1)),float(h.group(1))) if w and h else (1600,2000)
for slug,urls in fs.items():
    if not urls: continue
    url=sorted(urls,key=lambda x:(0 if re.search(r'_MP_|Map',x) else 1))[0]
    p=f'_peet/maps/{slug}.svg'
    if not fetch(url,p): continue
    svg=open(p,encoding='utf-8',errors='replace').read()
    w,h=dims(svg); scale=2200/max(w,h); W,H=int(w*scale),int(h*scale)
    out=f'/tmp/{slug}_mp.png'
    r=subprocess.run([CHROME,'--headless=new','--disable-gpu','--no-sandbox','--user-data-dir=/tmp/cprof',
                      f'--window-size={W},{H}',f'--screenshot={out}',f'file://{os.path.abspath(p)}'],
                     capture_output=True,text=True,timeout=120)
    ok=os.path.exists(out)
    print(f'{slug:24} {W}x{H} {"OK" if ok else "FAIL "+r.stderr[-60:]}',flush=True)
    if ok: shutil.copy(out,f'_peet/maps/{slug}.png')
