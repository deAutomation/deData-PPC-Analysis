import re,os,json,subprocess,urllib.request
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
have={os.path.basename(f)[:-4] for f in os.listdir('_peet/masterplans') if f.endswith('.png')}
urls={u.strip().rstrip('/').split('/')[-1]:u.strip() for u in open('_peet/community_urls.txt') if u.strip()}
os.makedirs('_peet/pdf',exist_ok=True); rows=[]
for s,u in urls.items():
    if s in have: continue
    p=f'_peet/pages/{s}.html'
    if not os.path.exists(p): continue
    h=open(p,encoding='utf-8',errors='replace').read()
    pdfs=sorted(set(re.findall(r'https://www\.peet\.com\.au/[^"\'\s)]+\.pdf',h)))
    plans=[x for x in pdfs if re.search(r'master.?plan|master.?lot.?plan|aerial.?plan|lot.?plan',x,re.I)]
    if not plans: print(f'{s:24} no plan pdf',flush=True); continue
    plans.sort(key=lambda x:(0 if 'master' in x.lower() else 1))
    url=plans[0]; local=f'_peet/pdf/{s}.pdf'
    try:
        raw=urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=60).read()
        open(local,'wb').write(raw)
        out=f'_peet/masterplans/{s}'
        subprocess.run(['pdftoppm','-png','-r','150','-f','1','-l','1','-singlefile',local,out],check=True,timeout=120)
        size=os.path.getsize(out+'.png')
        rows.append([s,url,size]); print(f'{s:24} rendered {size//1024}KB',flush=True)
    except Exception as e:
        print(f'{s:24} ERR {str(e)[:50]}',flush=True)
json.dump(rows,open('_peet/pdf_render_rows.json','w'),indent=1)
