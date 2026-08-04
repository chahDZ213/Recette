# Vérifications Permis B — appli de révision

Appli web pour réviser les **100 fiches de vérification** de l'épreuve pratique
du permis B. Chaque fiche contient les trois questions que pose l'inspecteur :
**vérification**, **sécurité routière**, **premiers secours**.

Aucune dépendance, aucun build, fonctionne hors ligne une fois chargée.

## Ouvrir l'appli

En ligne : `/qcm/` une fois le site déployé.
En local : `python3 -m http.server` à la racine du dépôt, puis
`http://localhost:8000/qcm/`.

Installable sur téléphone (« Ajouter à l'écran d'accueil ») : elle devient une
PWA autonome, utilisable sans connexion.

## Les quatre modes

| Onglet | Ce qu'il fait |
|---|---|
| **Examen** | Tire une fiche au hasard, comme le jour J. Les trois questions, réponse masquée, auto-évaluation « Je savais » / « Pas su ». |
| **QCM** | Une question, quatre propositions. Les mauvaises réponses sont de vraies réponses empruntées à d'autres fiches — donc plausibles. |
| **Les 100 fiches** | Consultation et recherche plein texte sur les 100 fiches. |
| **Progrès** | Compteur d'acquis et liste des points faibles. |

La progression est enregistrée dans le `localStorage` du navigateur
(clé `permisb-verif-v1`) : rien n'est envoyé sur un serveur. Les questions
ratées sont retirées plus souvent (système de boîtes à la Leitner, 5 niveaux).

## Fichiers

```
qcm/
  index.html      l'appli entière (structure, style, logique)
  questions.js    les 100 fiches, embarquées comme const QUESTIONS
  questions.json  les mêmes données, pour réutilisation ailleurs
  parse.py        script d'extraction depuis le PDF source
  manifest.json   PWA
  sw.js           service worker, cache-first
  photos/         photos sources (archive, non utilisées par l'appli)
```

## Format des données

```json
{
  "n": "00",
  "verification": { "q": "Montrez où se situent les gicleurs…", "a": "Ils se trouvent sur le capot…" },
  "securite":     { "q": "Conséquence d'un dispositif défaillant ?", "a": "Impossible de nettoyer…" },
  "secours":      { "q": "Qu'est-ce qu'un DAE ?", "a": "Un appareil portable qui…" }
}
```

## Régénérer les données

Les fiches viennent du PDF `verificationspermisBCOMPLET.pdf`. Pour les
reconstruire après modification du PDF :

```bash
pip install pypdf
python3 -c "
from pypdf import PdfReader
r = PdfReader('verificationspermisBCOMPLET.pdf')
open('pdf.txt','w').write('\n'.join(p.extract_text() for p in r.pages))
"
python3 parse.py     # -> questions.json
```

`parse.py` découpe chaque bloc `Question n°NN` en trois volets, sépare l'énoncé
de la réponse, et signale les découpes suspectes (réponse très courte, énoncé
très long) pour relecture.

## Fiabilité du contenu

Les réponses proviennent du PDF fourni. Les valeurs chiffrées sensibles ont été
recoupées avec la réglementation en vigueur : signal SAIP (3 cycles de 1 min 41 s,
fin d'alerte continue de 30 s), triangle de présignalisation à 30 m, feux de
position visibles à 150 m, alcoolémie en permis probatoire 0,2 g/L de sang,
contrôle de la respiration pendant 10 s maximum, 30 compressions pour
2 insufflations, bornes d'appel tous les 2 km sur autoroute.

Cela reste un support de révision : en cas de doute sur un point précis, la
référence est le livret officiel de l'auto-école.
