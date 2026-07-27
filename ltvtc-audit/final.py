import json,re,unicodedata,urllib.request,urllib.parse,time
D="/tmp/claude-0/-home-user-Recette/008f1584-3a72-52a0-9133-36cd50921fd9/scratchpad/ltvtc/"
def norm(s):
    if not s: return ""
    s=re.sub(r'\s*\([^)]*\)','',s)
    s=unicodedata.normalize('NFD',s.lower())
    s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())
def core(s):
    return re.sub(r'^(rue|route|avenue|chemin|quai|place|boulevard|promenade|cours|cour|esplanade|ruelle|sentier|impasse|passage|pont|parc|clos|rampe|villa|voie|rondeau)( de la | de l | du | des | de | d |)','',norm(s)).strip()
EP=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]
def run(q):
    for a in range(6):
        try:
            r=urllib.request.Request(EP[a%2],data=urllib.parse.urlencode({"data":q}).encode(),headers={"User-Agent":"ltvtc-audit/1.0"})
            with urllib.request.urlopen(r,timeout=120) as f: return json.load(f)['elements']
        except Exception: time.sleep(4+4*a)
    return None
d=json.load(open(D+'verified.json',encoding='utf-8'))
todo=[]
for o in d:
    if o.get('_check')!='done': continue
    B={norm(x) for x in o['_osmAtBegin']}; E={norm(x) for x in o['_osmAtEnd']}
    if norm(o['beginStreet']) not in B: todo.append((o,'DEBUT',o['beginStreet'],o['beginPoint']))
    if norm(o['endStreet']) not in E: todo.append((o,'FIN',o['endStreet'],o['endPoint']))
print("points a recontroler a 80 m :",len(todo),flush=True)
res=[]
for o,side,claim,pt in todo:
    el=run('[out:json][timeout:60];way(around:80,%f,%f)["highway"]["name"];out tags;'%(pt[0],pt[1]))
    nm=sorted({x['tags']['name'] for x in (el or []) if x.get('tags',{}).get('name')})
    ok = norm(claim) in {norm(x) for x in nm}
    var = (not ok) and core(claim) in {core(x) for x in nm}
    res.append({'rue':o['rueDisplay'],'cote':side,'app':claim,'ok80':ok,'variante':var,
                'voies80':[x for x in nm if x!=o['rueDisplay']]})
    print(("OK   " if ok else ("VAR  " if var else "FAUX ")),o['rueDisplay'],side,"->",claim,flush=True)
    time.sleep(1.2)
json.dump(res,open(D+'final80.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print("\nrecuperes a 80m:",sum(1 for r in res if r['ok80']),"| variantes:",sum(1 for r in res if r['variante']),
      "| restent faux:",sum(1 for r in res if not r['ok80'] and not r['variante']))
