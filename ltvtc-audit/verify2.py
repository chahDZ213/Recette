import json,time,urllib.request,urllib.parse,unicodedata,re,os
D="/tmp/claude-0/-home-user-Recette/008f1584-3a72-52a0-9133-36cd50921fd9/scratchpad/ltvtc/"
recs=json.load(open(D+'dataset.json',encoding='utf-8'))
OUT=D+'verified.json'
done=json.load(open(OUT,encoding='utf-8')) if os.path.exists(OUT) else []
start=len(done)
EP=["https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter"]
def norm(s):
    if not s: return ""
    s=unicodedata.normalize('NFD',s.lower())
    s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())
def q(b,e):
    body=('[out:json][timeout:60];way(around:35,%f,%f)["highway"]["name"];out tags;out count;'
          'way(around:35,%f,%f)["highway"]["name"];out tags;')%(b[0],b[1],e[0],e[1])
    last=None
    for attempt in range(6):
        url=EP[attempt%len(EP)]
        try:
            r=urllib.request.Request(url,data=urllib.parse.urlencode({"data":body}).encode(),
                                     headers={"User-Agent":"ltvtc-audit/1.0"})
            with urllib.request.urlopen(r,timeout=120) as f: return json.load(f)
        except Exception as ex:
            last=ex; time.sleep(4+6*attempt)
    print("  echec:",last,flush=True); return None
for i in range(start,len(recs)):
    r=recs[i]
    if not r.get('beginPoint') or not r.get('endPoint'):
        done.append({**r,'_check':'no_points'})
    else:
        d=q(r['beginPoint'],r['endPoint'])
        if d is None: done.append({**r,'_check':'overpass_fail'})
        else:
            A,B,cur=[],[],0
            for el in d['elements']:
                if el.get('type')=='count': cur=1; continue
                n=el.get('tags',{}).get('name')
                if n: (A if cur==0 else B).append(n)
            done.append({**r,'_check':'done','_osmAtBegin':sorted(set(A)),'_osmAtEnd':sorted(set(B)),
                         '_beginOK':norm(r['beginStreet']) in {norm(x) for x in A},
                         '_endOK':norm(r['endStreet']) in {norm(x) for x in B}})
    if (i+1)%10==0:
        json.dump(done,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
        print("progression",i+1,"/",len(recs),flush=True)
    time.sleep(1.3)
json.dump(done,open(OUT,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
ok=[o for o in done if o.get('_check')=='done']
print("TERMINE. verifies:",len(ok),"/",len(done),flush=True)
print("debut OK:",sum(1 for o in ok if o['_beginOK']),"| fin OK:",sum(1 for o in ok if o['_endOK']),flush=True)
print("les deux OK:",sum(1 for o in ok if o['_beginOK'] and o['_endOK']),flush=True)
