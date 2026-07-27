import json,urllib.request,urllib.parse,time,collections,math
D="/tmp/claude-0/-home-user-Recette/008f1584-3a72-52a0-9133-36cd50921fd9/scratchpad/ltvtc/"
EP=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]
def run(q):
    for a in range(6):
        try:
            r=urllib.request.Request(EP[a%2],data=urllib.parse.urlencode({"data":q}).encode(),
                                     headers={"User-Agent":"ltvtc-audit/1.0"})
            with urllib.request.urlopen(r,timeout=180) as f: return json.load(f)['elements']
        except Exception as ex: last=ex; time.sleep(5+5*a)
    print("  echec:",last,flush=True); return None
def key(p): return (round(p[0],6),round(p[1],6))
def dist(a,b):
    return math.hypot((a[0]-b[0])*111320,(a[1]-b[1])*111320*math.cos(math.radians(a[0])))
rues=["Avenue Appia","Rue Blavignac","Rue Boissonnas","Chemin du Champ-Baron","Rue Le-Corbusier",
      "Rue des Charmilles","Route de Meyrin","Avenue des Tilleuls","Rue Lombard","Route de Drize"]
out={}
for rue in rues:
    e=run('[out:json][timeout:180];way(46.12,5.94,46.33,6.33)["highway"]["name"="%s"];out geom;'%rue)
    if not e: continue
    deg=collections.Counter()
    for w in e:
        g=[(p['lat'],p['lon']) for p in (w.get('geometry') or [])]
        if len(g)<2: continue
        deg[key(g[0])]+=1; deg[key(g[-1])]+=1
    ends=[p for p,c in deg.items() if c==1]
    if len(ends)<2: print(rue,"-> extremites:",len(ends)); continue
    best=max(((dist(a,b),a,b) for i,a in enumerate(ends) for b in ends[i+1:]),key=lambda t:t[0])
    res=[]
    for p in (best[1],best[2]):
        el=run('[out:json][timeout:60];way(around:30,%f,%f)["highway"]["name"];out tags;'%p) or []
        nm=sorted({x['tags']['name'] for x in el if x.get('tags',{}).get('name') and x['tags']['name']!=rue})
        res.append({'point':[p[0],p[1]],'voies':nm}); time.sleep(1.5)
    out[rue]={'longueur_m':round(best[0]),'nb_extremites':len(ends),'ext':res}
    print(f"### {rue}  (ecart extremites {round(best[0])} m, {len(ends)} bouts libres)",flush=True)
    for r in res: print("    ",r['point'],"->",", ".join(r['voies']) or "(aucune voie nommee)",flush=True)
    time.sleep(1.5)
json.dump(out,open(D+'extremites2.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
