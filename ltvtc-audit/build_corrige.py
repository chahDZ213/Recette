import json,os
app=json.load(open('dataset_full.json',encoding='utf-8'))
# 1. corrections de contenu certaines
FIX={("Avenue Appia","end"):"Chemin des Geais",
     ("Rue Boissonnas","begin"):"Route des Acacias",
     ("Chemin du Champ-Baron","begin"):"Chemin de la Rochette",
     ("Route de Meyrin","begin"):"Rue de la Servette",
     ("Avenue des Tilleuls","begin"):"Voie couverte de Saint-Jean"}
# 2. extremites reelles (croisement intermediaire -> bout de rue)
EXT={("Rue du Grand-Pré","end"):"Rue Chandieu",
     ("Chemin Moïse-Duboule","end"):"Chemin du Pommier",
     ("Route de La-Capite","end"):"Route de Thonon",
     ("Route de Jussy","end"):"Route de Monniaz"}
log=[]
for a in app:
    for (rue,side),val in list(FIX.items())+list(EXT.items()):
        if a['rueDisplay']==rue:
            k=side+'Street'
            if a.get(k)!=val:
                log.append((rue,side,a.get(k),val)); a[k]=val
    # 3. renommage officiel
    if a['rueOfficial']=='LA RUE CEARD':
        a['rueOfficial']='LA RUE ROBERT-CEARD'; a['rueDisplay']='Rue Robert-Céard'
        log.append(('Rue Céard','nom','LA RUE CEARD','LA RUE ROBERT-CEARD'))
# 4. ajout des 3 rues officielles manquantes
if os.path.exists('nouvelles.json'):
    new=json.load(open('nouvelles.json',encoding='utf-8'))
    have={a['rueOfficial'] for a in app}
    for n in new:
        if n['rueOfficial'] not in have:
            app.append(n); log.append((n['rueDisplay'],'AJOUT','-',n['referenceOfficial']))
json.dump(app,open('dataset_corrige.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print("fiches finales:",len(app))
print("modifications appliquees:",len(log))
for l in log: print("  ",l)
