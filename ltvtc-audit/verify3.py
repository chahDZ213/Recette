import json,re,unicodedata,urllib.request,urllib.parse,time
D="/tmp/claude-0/-home-user-Recette/008f1584-3a72-52a0-9133-36cd50921fd9/scratchpad/ltvtc/"
def norm(s):
    if not s: return ""
    s=re.sub(r'\s*\([^)]*\)','',s)
    s=unicodedata.normalize('NFD',s.lower())
    s=''.join(c for c in s if unicodedata.category(c)!='Mn')
    return " ".join(re.sub(r"[^a-z0-9]+"," ",s).split())
EP=["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]
def run(q):
    for a in range(6):
        try:
            r=urllib.request.Request(EP[a%2],data=urllib.parse.urlencode({"data":q}).encode(),
                                     headers={"User-Agent":"ltvtc-audit/1.0"})
            with urllib.request.urlopen(r,timeout=120) as f: return json.load(f)['elements']
        except Exception as ex:
            last=ex; time.sleep(5+5*a)
    print("   echec:",last,flush=True); return None
cases=[("Avenue Appia","FIN","Chemin des Crêts-de-Pregny"),("Rue Maurice-Barraud","DEBUT","Avenue Dumas"),
("Rue Blavignac","FIN","Avenue Vibert"),("Rue Boissonnas","DEBUT","Route des Jeunes"),
("Rue Caroline","FIN","Rue des Mouettes"),("Chemin du Champ-Baron","DEBUT","Chemin des Genêts"),
("Avenue de la Jonction","FIN","Rue de la Truite"),("Route de La-Capite","FIN","Chemin du Pré-Langard"),
("Rue Le-Corbusier","DEBUT","Route de Malagnou"),("Rue Le-Corbusier","FIN","Route de Florissant"),
("Rue Saint-Laurent","FIN","Ruelle du Midi"),("Route de Chêne","FIN","Chemin de Grange-Falquet"),
("Rue du Grand-Pré","FIN","Avenue Giuseppe-Motta"),("Rue des Bossons","FIN","Chemin de l'Avenir"),
("Rue des Charmilles","DEBUT","Rue de Lyon"),("Chemin Moïse-Duboule","FIN","Rue de Moillebeau"),
("Route de Meyrin","DEBUT","Route Einstein"),("Avenue des Tilleuls","DEBUT","Avenue De-Gallatin"),
("Rue Lombard","FIN","Boulevard des Philosophes"),("Avenue Louis-Casaï","DEBUT","Route François-Peyrot"),
("Route de Drize","DEBUT","Route d'Annecy"),("Route d'Hermance","FIN","Chemin des Bois"),
("Route de Thonon","FIN","Chemin des Coprins"),("Route de Jussy","FIN","Chemin de la Forge")]
res=[]
cache={}
for rue,side,claim in cases:
    if rue not in cache:
        q=('[out:json][timeout:120];way(46.12,5.94,46.33,6.33)["highway"]["name"="%s"]->.s;'
           'node(w.s)->.n;way(bn.n)["highway"]["name"];out tags;')%rue
        e=run(q); cache[rue]=e; time.sleep(2)
    e=cache[rue]
    if e is None: res.append((rue,side,claim,"ECHEC",[])); continue
    names={x['tags'].get('name') for x in e if x.get('tags',{}).get('name')}
    nn={norm(x) for x in names}
    verdict="TOUCHE"if norm(claim) in nn else "NE TOUCHE PAS"
    res.append((rue,side,claim,verdict,sorted(names)))
    print(f"{verdict:14s} {rue} [{side}] -> {claim}",flush=True)
json.dump(res,open(D+'croisements.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print("\nTOUCHE:",sum(1 for r in res if r[3]=="TOUCHE"),"| NE TOUCHE PAS:",sum(1 for r in res if r[3]=="NE TOUCHE PAS"))
