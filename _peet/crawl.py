import urllib.request, re, json, os, time
UA={'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36'}
os.makedirs('_peet/live',exist_ok=True)
urls=[u.strip() for u in open('_peet/community_urls.txt') if u.strip()]
ok=0; fail=[]
for u in urls:
    slug=u.rstrip('/').split('/')[-1]
    out=f'_peet/live/{slug}.json'
    if os.path.exists(out): ok+=1; continue
    try:
        h=urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=40).read().decode('utf-8','replace')
        i=h.find('var lotConfig = ')
        if i<0: fail.append((slug,'no lotConfig')); continue
        j=h.find('=',i)+1
        cfg,_=json.JSONDecoder().raw_decode(h[j:].lstrip())
        m=re.search(r'var mapConfig = (\{.*?\});',h,re.S)
        if m:
            try: cfg['mapConfig']=json.loads(m.group(1))
            except Exception: pass
        json.dump({'slug':slug,'url':u,'cfg':cfg},open(out,'w'))
        ok+=1
    except Exception as e:
        fail.append((slug,str(e)[:60]))
    time.sleep(0.3)
print('ok',ok,'fail',fail)
