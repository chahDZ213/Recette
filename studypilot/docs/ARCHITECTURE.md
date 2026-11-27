# StudyPilot : analyse, architecture et plan

## 1. Besoins (résumé)
Un élève de première générale (maths, PC, SI), qui vise un BUT GEII en 2028, doit savoir **chaque jour quoi travailler** pendant le temps dont il dispose. Ce choix tient compte de ses devoirs, de ses contrôles, de ses notes, de ses lacunes, de l'oubli et des chapitres à venir. Les autres attentes sont un professeur IA qui fait raisonner sans donner les réponses, des exercices adaptatifs, des révisions espacées, l'import de documents, un tableau de bord et un simulateur de bac présenté comme une estimation, jamais comme une garantie.

## 2. Architecture

```
studypilot/ (PWA statique, sans build)          api/studypilot-ai.js (Vercel, Node)
 ├─ app.js        interface (9 pages)  ──fetch──▶  Claude (claude-opus-5-5) via SDK officiel
 ├─ engine/       MOTEUR PÉDAGOGIQUE (pur, testé)    · modes : tuteur, lecon, exercices,
 │   curriculum.js  programme + prérequis              correction, document (vision / PDF)
 │   srs.js         répétition espacée, statuts      · sorties JSON validées par schéma
 │   planner.js     planification de la séance       · auth Supabase obligatoire, quota/heure
 │   grades.js      moyennes, note nécessaire, bac   · renvoie tokens + coût → suivi dans l'app
 │   errors.js      typologie d'erreurs, niveaux
 │   store.js       localStorage + IndexedDB + fusion
 ├─ sw.js         hors ligne                     Supabase : auth + table studypilot_state (RLS)
 └─ tests/        node --test
```

- **Séparation moteur / interface :** `engine/` n'accède jamais au DOM. Le planning est une fonction pure `planifier(état, minutes, date)`, recalculée à chaque rendu. Ajouter un devoir, une note, un cours ou une indisponibilité suffit donc à mettre la séance à jour.
- **Données :** l'état JSON est gardé en local (fonctionne hors ligne) et synchronisé par compte dans Supabase, avec la RLS (« row level security ») qui limite chaque élève à sa propre ligne. Les fichiers (photos, PDF) restent sur l'appareil, dans IndexedDB : seuls les résultats d'analyse partent dans le cloud. Un export JSON sert de sauvegarde manuelle.
- **IA configurable :** la variable `STUDYPILOT_MODEL` règle le modèle et `STUDYPILOT_MAX_PER_HOUR` le quota par heure. La clé API reste côté serveur. Le cache de prompt est activé sur les consignes système.
- **Coût :** chaque appel renvoie ses tokens et son coût estimé. La page Paramètres en affiche le total par mois et par mode.

## 3. Règles pédagogiques implémentées
- **Statuts :** non étudiée → découverte en avance / en cours → étudiée → à consolider → maîtrisée.
- **Maîtrise :** une notion n'est « maîtrisée » qu'après au moins 3 réussites consécutives (≥ 80 %), dont une à un intervalle de J+14 ou plus.
- **Intervalles :** J+1, 3, 7, 14, 30, 60. Un score entre 50 et 80 % garde le palier, un échec recule de 2 paliers.
- **Priorités du planning :** contrôles (≤ 10 j) > devoirs (≤ 7 j) > consolidation > cours du lendemain > révisions dues (selon le risque d'oubli) > anticipation. Chaque tâche est pondérée par la matière (maths, PC et SI ×3, français ×2,5…) et par la faiblesse de la moyenne. Une même matière ne peut pas occuper plus de 2 blocs, sauf contrôle ou devoir.
- **Niveau d'exercice :** sur les 3 dernières tentatives, une moyenne ≥ 80 % fait monter d'un niveau et une moyenne < 50 % fait descendre. L'erreur dominante est ciblée.
- **Documents :** une analyse sûre (confiance ≥ 0,85 et rien d'incertain) est classée seule. Sinon, l'élève confirme ou corrige, et répond aux questions de l'IA.

## 4. Plan de développement
1. **V1 (livrée) :** moteur et tests, les 9 pages, compte et synchronisation, IA (professeur, leçons anticipées, exercices et correction, analyse de documents), suivi des coûts, PWA.
2. **V1.1 :**
   - confronter le programme de maths au BO n°14 de 2026 ;
   - ajouter une page pour éditer le programme (ajout de notions) ;
   - rendu des formules (KaTeX).
3. **V2 :**
   - notifications de révision (web-push, comme dans mise.) ;
   - sauvegarde chiffrée des documents dans Supabase Storage ;
   - import Pronote récurrent ;
   - statistiques de régularité (séries de jours).
4. **V3 :** mode examen (bac blanc chronométré), préparation à l'oral de français, suivi du dossier Parcoursup (projet motivé).

## 5. Mise en service
1. Appliquer `supabase/0002_studypilot.sql` dans l'éditeur SQL de Supabase.
2. Vérifier que `ANTHROPIC_API_KEY` est définie sur Vercel (elle est déjà utilisée par mise.).
3. Déployer. L'app est servie sur `/studypilot/`. Sur iPhone : Safari → Partager → « Sur l'écran d'accueil ».
4. Lancer les tests : `cd studypilot && npm test`.
