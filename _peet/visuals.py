import urllib.request, re, os, json, time
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
urls=[u.strip() for u in open('_peet/community_urls.txt') if u.strip()]
IMG=re.compile(r'https://www\.peet\.com\.au/[^"\'\s)]+?\.(?:png|jpg|jpeg|webp)', re.I)
rows=[]
for u in urls:
    slug=u.rstrip('/').split('/')[-1]
    p=f'_peet/pages/{slug}.html'
    if not os.path.exists(p):
        try:
            h=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40).read().decode('utf-8','replace')
        except Exception as e:
            rows.append((slug,'ERR',str(e)[:40],'',0)); continue
        open(p,'w').write(h); time.sleep(0.2)
    h=open(p,encoding='utf-8',errors='replace').read()
    imgs=sorted(set(IMG.findall(h)))
    mp=[i for i in imgs if re.search(r'master.?plan|site.?plan|estate.?plan|masterplan', i, re.I)]
    og=re.findall(r'property="og:image" content="([^"]+)"',h)
    rows.append((slug, len(imgs), mp[0] if mp else '', og[0] if og else '', len(mp)))
for r in rows: print(f'{r[0]:24} imgs={r[1]:3} masterplans={r[4]} :: {r[2][-60:] if r[2] else "-"}')
json.dump(rows,open('_peet/visual_rows.json','w'))
