# Dépose tes photos de questions ici

C'est le dossier de destination des 100 photos.

## Comment déposer (interface web GitHub)

1. Ouvre ce dossier sur GitHub, branche `claude/transfert-100-photos-jcgepf`
2. **Add file → Upload files**
3. Glisse tes photos (par paquets de ~50 si l'upload est lent)
4. **Commit directly to the branch `claude/transfert-100-photos-jcgepf`**
5. Reviens me dire « c'est poussé »

## Formats acceptés

`.jpg` `.jpeg` `.png` `.webp` `.heic`

Les photos prises au téléphone (2–5 Mo) passent sans problème.
GitHub refuse les fichiers de plus de 25 Mo via l'interface web.

## Conseils pour que la lecture soit fiable

- Photo bien à plat, page entière dans le cadre
- Éviter les ombres portées et les reflets
- Une page par photo (plutôt que deux pages en biais)
- Si l'ordre des questions compte, nomme les fichiers `01.jpg`, `02.jpg`, …

## Ce qui se passe ensuite

Je lis chaque photo, j'extrais les questions, je recherche et rédige les
réponses, puis je génère `qcm/questions.json` qui alimente l'appli de
révision `qcm/index.html`.

Ce dossier sert d'archive source : l'appli n'a pas besoin des photos pour
fonctionner une fois les questions extraites.
